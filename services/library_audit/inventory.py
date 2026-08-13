#!/usr/bin/env python3
"""Filesystem inventory for Library Audit."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy.orm import Session

from database.library_audit_models import LibraryAuditFile, LibraryAuditInventoryRun
from services.library_audit.formats import (
    DEFAULT_ANALYSIS_EXTENSIONS,
    DEFAULT_INVENTORY_EXTENSIONS,
    is_analyzable_extension,
    normalize_extensions,
)
from services.library_audit.paths import to_relative_posix
from utils.logger import get_logger


def _log():
    return get_logger("cmdarr.library_audit.inventory")


@dataclass
class InventoryResult:
    run_id: int
    status: str
    files_seen: int = 0
    eligible_files_seen: int = 0
    new_files: int = 0
    changed_files: int = 0
    missing_files: int = 0
    errors: int = 0
    duration_seconds: float | None = None
    error_message: str | None = None


def run_inventory(
    session: Session,
    root: str | Path,
    extensions: list[str] | None = None,
    analysis_extensions: list[str] | None = None,
) -> InventoryResult:
    """Walk root and upsert inventory rows. Mark missing only on successful completion.

    Inventory can include many audio types. Only analysis_extensions enter PENDING;
    other eligible files are marked UNSUPPORTED (tracked, not analyzed).
    """
    root_path = Path(root).resolve()
    if not root_path.exists() or not root_path.is_dir():
        raise FileNotFoundError(f"Library audit root not found or not a directory: {root_path}")

    exts = set(normalize_extensions(extensions, DEFAULT_INVENTORY_EXTENSIONS))
    analyzable = normalize_extensions(analysis_extensions, DEFAULT_ANALYSIS_EXTENSIONS)
    started = datetime.now(UTC)
    run = LibraryAuditInventoryRun(
        started_at=started,
        status="RUNNING",
        root_path=str(root_path),
    )
    session.add(run)
    session.flush()

    files_seen = 0
    eligible = 0
    new_files = 0
    changed_files = 0
    errors = 0
    seen_ids: set[int] = set()

    try:
        for path in root_path.rglob("*"):
            try:
                if not path.is_file():
                    continue
                # Skip symlink escapes outside root
                resolved = path.resolve()
                try:
                    resolved.relative_to(root_path)
                except ValueError:
                    continue
                files_seen += 1
                if resolved.suffix.lower() not in exts:
                    continue
                eligible += 1
                rel = to_relative_posix(root_path, resolved)
                st = resolved.stat()
                size = int(st.st_size)
                mtime_ns = int(getattr(st, "st_mtime_ns", int(st.st_mtime * 1_000_000_000)))
                now = datetime.now(UTC)

                row = (
                    session.query(LibraryAuditFile)
                    .filter(LibraryAuditFile.relative_path == rel)
                    .first()
                )
                ext = resolved.suffix.lower()
                can_analyze = is_analyzable_extension(ext, analyzable)
                if row is None:
                    row = LibraryAuditFile(
                        relative_path=rel,
                        file_name=resolved.name,
                        parent_path=str(Path(rel).parent.as_posix()),
                        extension=ext,
                        size_bytes=size,
                        mtime_ns=mtime_ns,
                        first_seen_at=now,
                        last_seen_at=now,
                        last_seen_inventory_id=run.id,
                        is_present=True,
                        missing_since=None,
                        analysis_state="PENDING" if can_analyze else "UNSUPPORTED",
                        analysis_queued_at=now if can_analyze else None,
                    )
                    session.add(row)
                    session.flush()
                    new_files += 1
                else:
                    row.last_seen_at = now
                    row.last_seen_inventory_id = run.id
                    row.is_present = True
                    row.missing_since = None
                    row.file_name = resolved.name
                    row.parent_path = str(Path(rel).parent.as_posix())
                    row.extension = ext
                    if row.size_bytes != size or row.mtime_ns != mtime_ns:
                        row.size_bytes = size
                        row.mtime_ns = mtime_ns
                        row.content_hash = None
                        row.current_analysis_id = None
                        row.current_review_id = None
                        row.last_analysis_error = None
                        if can_analyze:
                            row.analysis_state = "PENDING"
                            row.analysis_queued_at = now
                        else:
                            row.analysis_state = "UNSUPPORTED"
                            row.analysis_queued_at = None
                        changed_files += 1
                    elif not can_analyze and row.analysis_state in (
                        "PENDING",
                        "ERROR",
                        "STALE",
                        "ANALYZING",
                    ):
                        # Extension no longer analyzable (or never was) — don't clog queue
                        row.analysis_state = "UNSUPPORTED"
                        row.analysis_queued_at = None
                    elif can_analyze and row.analysis_state == "UNSUPPORTED":
                        row.analysis_state = "PENDING"
                        row.analysis_queued_at = now
                seen_ids.add(row.id)
            except Exception as exc:
                errors += 1
                _log().warning(f"Inventory error for {path}: {exc}")

        session.flush()

        # Mark missing only after successful walk
        missing = 0
        present_rows = (
            session.query(LibraryAuditFile).filter(LibraryAuditFile.is_present.is_(True)).all()
        )
        now = datetime.now(UTC)
        for row in present_rows:
            if row.last_seen_inventory_id != run.id:
                row.is_present = False
                row.missing_since = now
                missing += 1

        finished = datetime.now(UTC)
        duration = (finished - started).total_seconds()
        run.status = "COMPLETED"
        run.completed_at = finished
        run.files_seen = files_seen
        run.eligible_files_seen = eligible
        run.new_files = new_files
        run.changed_files = changed_files
        run.missing_files = missing
        run.errors = errors
        run.duration_seconds = duration
        session.commit()

        return InventoryResult(
            run_id=run.id,
            status="COMPLETED",
            files_seen=files_seen,
            eligible_files_seen=eligible,
            new_files=new_files,
            changed_files=changed_files,
            missing_files=missing,
            errors=errors,
            duration_seconds=duration,
        )
    except Exception as exc:
        finished = datetime.now(UTC)
        duration = (finished - started).total_seconds()
        run.status = "FAILED"
        run.completed_at = finished
        run.error_message = str(exc)
        run.files_seen = files_seen
        run.eligible_files_seen = eligible
        run.new_files = new_files
        run.changed_files = changed_files
        run.errors = errors + 1
        run.duration_seconds = duration
        try:
            session.commit()
        except Exception:
            session.rollback()
        _log().error(f"Inventory failed: {exc}")
        return InventoryResult(
            run_id=run.id,
            status="FAILED",
            files_seen=files_seen,
            eligible_files_seen=eligible,
            new_files=new_files,
            changed_files=changed_files,
            missing_files=0,
            errors=errors + 1,
            error_message=str(exc),
            duration_seconds=duration,
        )
