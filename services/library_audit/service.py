#!/usr/bin/env python3
"""Library Audit orchestration service."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from sqlalchemy import func
from sqlalchemy.orm import Session

from database.library_audit_models import (
    LibraryAuditAnalysis,
    LibraryAuditAnalysisRun,
    LibraryAuditFile,
    LibraryAuditInventoryRun,
    LibraryAuditReview,
)
from services.library_audit.formats import (
    DEFAULT_ANALYSIS_EXTENSIONS,
    DEFAULT_INVENTORY_EXTENSIONS,
    format_kind_for_extension,
    is_analyzable_extension,
    normalize_extensions,
)
from services.library_audit.hashing import sha256_file
from services.library_audit.inventory import InventoryResult, run_inventory
from services.library_audit.jsonutil import to_jsonable
from services.library_audit.paths import resolve_under_root
from services.library_audit.provider import (
    REVIEW_THRESHOLD_ORDER,
    AnalyzerProvider,
    ProviderAnalysisResult,
)
from services.library_audit.retention import cleanup_missing_records
from services.library_audit.router import get_composite_provider
from utils.logger import get_logger


def _log():
    return get_logger("cmdarr.library_audit.service")


ANALYZING_STALE_MINUTES = 60
NEEDS_REVIEW_VERDICTS = frozenset(
    {"WARNING", "SUSPICIOUS", "FAKE_CERTAIN", "INCONCLUSIVE", "ERROR"}
)
DISPOSITIONS = frozenset(
    {
        "FALSE_POSITIVE",
        "BEST_AVAILABLE",
        "CONFIRMED_TRANSCODE",
        "REPLACE",
        "IGNORE",
        "UNSURE",
    }
)
# Legacy disposition stored before rename
_LEGACY_DISPOSITION_MAP = {"ACCEPTED": "FALSE_POSITIVE"}


def normalize_disposition(disposition: str | None) -> str | None:
    if not disposition:
        return None
    upper = disposition.upper()
    return _LEGACY_DISPOSITION_MAP.get(upper, upper)


def effective_verdict(scan_verdict: str | None, disposition: str | None) -> str | None:
    """Human disposition can clear a false-positive scan result for display/stats."""
    if normalize_disposition(disposition) == "FALSE_POSITIVE":
        return "AUTHENTIC"
    return scan_verdict


@dataclass
class AnalysisBatchResult:
    run_id: int | None = None
    attempted: int = 0
    completed: int = 0
    authentic: int = 0
    warning: int = 0
    suspicious: int = 0
    fake_certain: int = 0
    inconclusive: int = 0
    errors: int = 0
    duration_seconds: float | None = None
    provider: str | None = None
    provider_version: str | None = None


@dataclass
class AuditRunSummary:
    inventory: InventoryResult | None = None
    inventory_skipped: bool = False
    analysis: AnalysisBatchResult = field(default_factory=AnalysisBatchResult)
    triage: AnalysisBatchResult = field(default_factory=AnalysisBatchResult)
    deep: AnalysisBatchResult = field(default_factory=AnalysisBatchResult)
    retention_deleted: int = 0
    pending_queue: int = 0
    pending_deep: int = 0
    needs_review: int = 0
    triage_progress_pct: float | None = None
    deep_skipped: bool = False
    deep_skip_reason: str | None = None


def is_feature_enabled(_config_get=None) -> bool:
    """Library Audit UI/API are available when the library_audit command is enabled."""
    from database.config_models import CommandConfig
    from database.database import get_database_manager

    session = get_database_manager().get_config_session_sync()
    try:
        row = (
            session.query(CommandConfig.enabled)
            .filter(
                CommandConfig.command_name == "library_audit",
                CommandConfig.deleted_at.is_(None),
            )
            .first()
        )
        return bool(row and row[0])
    finally:
        session.close()


def get_music_root(config_get) -> Path:
    root = config_get("LIBRARY_AUDIT_ROOT", "/music") or "/music"
    return Path(str(root)).expanduser()


def validate_root(root: Path) -> tuple[bool, str]:
    if not root.exists():
        return False, f"Root does not exist: {root}"
    if not root.is_dir():
        return False, f"Root is not a directory: {root}"
    if not os_access_readable(root):
        return False, f"Root is not readable: {root}"
    return True, "ok"


def os_access_readable(path: Path) -> bool:
    import os

    return os.access(path, os.R_OK)


def inventory_due(session: Session, interval_hours: int) -> bool:
    hours = max(1, int(interval_hours))
    last = (
        session.query(LibraryAuditInventoryRun)
        .filter(LibraryAuditInventoryRun.status == "COMPLETED")
        .order_by(LibraryAuditInventoryRun.completed_at.desc())
        .first()
    )
    if last is None or last.completed_at is None:
        return True
    completed = last.completed_at
    if completed.tzinfo is None:
        completed = completed.replace(tzinfo=UTC)
    return datetime.now(UTC) - completed >= timedelta(hours=hours)


def recover_stale_analyzing(session: Session, stale_minutes: int = ANALYZING_STALE_MINUTES) -> int:
    cutoff = datetime.now(UTC) - timedelta(minutes=max(1, stale_minutes))
    rows = (
        session.query(LibraryAuditFile).filter(LibraryAuditFile.analysis_state == "ANALYZING").all()
    )
    recovered = 0
    for row in rows:
        queued = row.analysis_queued_at or row.updated_at or row.first_seen_at
        if queued is None:
            continue
        if queued.tzinfo is None:
            queued = queued.replace(tzinfo=UTC)
        # Also recover rows with no useful timestamp older than anything — use updated_at
        marker = row.updated_at or queued
        if marker.tzinfo is None:
            marker = marker.replace(tzinfo=UTC)
        if marker < cutoff or queued < cutoff:
            # Prefer PENDING_DEEP if a prior triage analysis asked for deep.
            prior_needs_deep = False
            if row.current_analysis_id:
                prior = session.get(LibraryAuditAnalysis, row.current_analysis_id)
                ev = (prior.evidence_json if prior else None) or {}
                if isinstance(ev, dict) and ev.get("needs_deep"):
                    prior_needs_deep = True
            row.analysis_state = "PENDING_DEEP" if prior_needs_deep else "PENDING"
            row.analysis_queued_at = datetime.now(UTC)
            recovered += 1
    if recovered:
        session.commit()
        _log().info(f"Recovered {recovered} stale ANALYZING file(s)")
    return recovered


def select_pending_files(
    session: Session,
    limit: int,
    analysis_extensions: list[str] | None = None,
    *,
    states: list[str] | None = None,
) -> list[LibraryAuditFile]:
    limit = max(1, int(limit))
    analyzable = normalize_extensions(analysis_extensions, DEFAULT_ANALYSIS_EXTENSIONS)
    state_list = states or ["PENDING", "ERROR", "STALE"]
    return (
        session.query(LibraryAuditFile)
        .filter(LibraryAuditFile.is_present.is_(True))
        .filter(LibraryAuditFile.analysis_state.in_(state_list))
        .filter(LibraryAuditFile.extension.in_(analyzable))
        .order_by(
            LibraryAuditFile.analysis_queued_at.asc().nullsfirst(),
            LibraryAuditFile.parent_path.asc(),
            LibraryAuditFile.relative_path.asc(),
        )
        .limit(limit)
        .all()
    )


def _apply_metadata(row: LibraryAuditFile, result: ProviderAnalysisResult) -> None:
    md = result.metadata or {}
    if md.get("artist"):
        row.artist = str(md["artist"])[:500]
    if md.get("album"):
        row.album = str(md["album"])[:500]
    if md.get("title"):
        row.title = str(md["title"])[:500]
    if md.get("track_number") is not None:
        row.track_number = str(md["track_number"])[:32]
    if md.get("disc_number") is not None:
        row.disc_number = str(md["disc_number"])[:32]
    if md.get("sample_rate") is not None:
        try:
            row.sample_rate = int(md["sample_rate"])
        except TypeError, ValueError:
            pass
    if md.get("bits_per_sample") is not None:
        try:
            row.bits_per_sample = int(md["bits_per_sample"])
        except TypeError, ValueError:
            pass
    if md.get("channels") is not None:
        try:
            row.channels = int(md["channels"])
        except TypeError, ValueError:
            pass
    if md.get("duration_seconds") is not None:
        try:
            row.duration_seconds = float(md["duration_seconds"])
        except TypeError, ValueError:
            pass


def analyze_file(
    session: Session,
    row: LibraryAuditFile,
    root: Path,
    provider: AnalyzerProvider,
    mode: str = "standard",
) -> LibraryAuditAnalysis | None:
    started = datetime.now(UTC)
    row.analysis_state = "ANALYZING"
    row.analysis_attempts = int(row.analysis_attempts or 0) + 1
    session.commit()

    try:
        abs_path = resolve_under_root(root, row.relative_path)
        if not abs_path.is_file():
            raise FileNotFoundError(f"File not found: {row.relative_path}")

        previous_hash = row.content_hash
        content_hash = sha256_file(abs_path)
        st = abs_path.stat()
        size = int(st.st_size)
        mtime_ns = int(getattr(st, "st_mtime_ns", int(st.st_mtime * 1_000_000_000)))
        row.size_bytes = size
        row.mtime_ns = mtime_ns
        row.content_hash = content_hash

        result = provider.analyze(str(abs_path), mode=mode)
        verdict = result.normalized_verdict()
        completed = datetime.now(UTC)

        analysis = LibraryAuditAnalysis(
            file_id=row.id,
            provider=result.provider,
            provider_version=result.provider_version,
            provider_mode=result.provider_mode or mode,
            analysis_schema_version=1,
            started_at=started,
            completed_at=completed,
            duration_seconds=(completed - started).total_seconds(),
            verdict=verdict,
            score=result.score,
            confidence=result.confidence,
            cutoff_hz=result.cutoff_hz,
            is_hires_suspect=result.is_hires_suspect,
            summary=result.summary,
            evidence_json=to_jsonable(result.evidence),
            raw_result_json=to_jsonable(result.raw_result),
            file_size_bytes=size,
            file_mtime_ns=mtime_ns,
            content_hash=content_hash,
        )
        session.add(analysis)
        session.flush()

        row.current_analysis_id = analysis.id
        needs_deep = bool((result.evidence or {}).get("needs_deep"))
        if (mode or "").lower() == "triage" and needs_deep:
            row.analysis_state = "PENDING_DEEP"
            row.analysis_queued_at = datetime.now(UTC)
        else:
            row.analysis_state = "ANALYZED"
        row.last_analysis_error = None
        # Previous disposition only applies while content hash is unchanged
        if previous_hash and previous_hash != content_hash:
            row.current_review_id = None
        _apply_metadata(row, result)
        session.commit()
        return analysis
    except Exception as exc:
        rel = getattr(row, "relative_path", None) or f"id={getattr(row, 'id', '?')}"
        file_id = getattr(row, "id", None)
        _log().warning(f"Analysis failed for {rel}: {exc}")
        try:
            session.rollback()
        except Exception:
            pass
        if file_id is not None:
            try:
                fresh = session.get(LibraryAuditFile, file_id)
                if fresh is not None:
                    fresh.analysis_state = "ERROR"
                    fresh.last_analysis_error = str(exc)[:2000]
                    session.commit()
            except Exception as commit_exc:
                _log().warning(f"Failed to persist ERROR state for {rel}: {commit_exc}")
                try:
                    session.rollback()
                except Exception:
                    pass
        return None


def run_analysis_batch(
    session: Session,
    root: Path,
    limit: int,
    provider: AnalyzerProvider | None = None,
    mode: str = "standard",
    analysis_extensions: list[str] | None = None,
    *,
    states: list[str] | None = None,
) -> AnalysisBatchResult:
    provider = provider or get_composite_provider()
    recover_stale_analyzing(session)
    files = select_pending_files(
        session, limit, analysis_extensions=analysis_extensions, states=states
    )
    started = datetime.now(UTC)
    try:
        health = provider.health()
        provider_name = health.provider
        provider_version = health.provider_version
    except Exception:
        provider_name = "composite"
        provider_version = None
    run = LibraryAuditAnalysisRun(
        started_at=started,
        status="RUNNING",
        requested_limit=limit,
        provider=provider_name,
        provider_version=provider_version,
    )
    session.add(run)
    session.commit()

    result = AnalysisBatchResult(
        run_id=run.id, provider=run.provider, provider_version=run.provider_version
    )
    for row in files:
        result.attempted += 1
        analysis = analyze_file(session, row, root, provider, mode=mode)
        if analysis is None:
            result.errors += 1
            continue
        result.completed += 1
        # Count final stored verdict; triage→PENDING_DEEP still stores provisional verdict
        v = analysis.verdict
        if v == "AUTHENTIC":
            result.authentic += 1
        elif v == "WARNING":
            result.warning += 1
        elif v == "SUSPICIOUS":
            result.suspicious += 1
        elif v == "FAKE_CERTAIN":
            result.fake_certain += 1
        elif v == "INCONCLUSIVE":
            result.inconclusive += 1
        else:
            result.errors += 1

    finished = datetime.now(UTC)
    result.duration_seconds = (finished - started).total_seconds()
    run.status = "COMPLETED"
    run.completed_at = finished
    run.attempted = result.attempted
    run.completed = result.completed
    run.authentic = result.authentic
    run.warning = result.warning
    run.suspicious = result.suspicious
    run.fake_certain = result.fake_certain
    run.inconclusive = result.inconclusive
    run.errors = result.errors
    run.duration_seconds = result.duration_seconds
    session.commit()
    return result


def count_pending(session: Session) -> int:
    return (
        session.query(func.count(LibraryAuditFile.id))
        .filter(LibraryAuditFile.is_present.is_(True))
        .filter(LibraryAuditFile.analysis_state.in_(["PENDING", "ERROR", "STALE", "ANALYZING"]))
        .scalar()
        or 0
    )


def count_pending_deep(session: Session) -> int:
    return (
        session.query(func.count(LibraryAuditFile.id))
        .filter(LibraryAuditFile.is_present.is_(True))
        .filter(LibraryAuditFile.analysis_state == "PENDING_DEEP")
        .scalar()
        or 0
    )


DEFAULT_DEEP_AFTER_TRIAGE_PCT = 80.0


def triage_progress(
    session: Session,
    analysis_extensions: list[str] | None = None,
) -> tuple[float, int, int]:
    """Return (percent, triaged_count, analyzable_present_count).

    A file is "triaged" once it is no longer waiting for the first pass
    (not PENDING / ERROR / STALE / ANALYZING). PENDING_DEEP and ANALYZED both count.
    """
    analyzable = normalize_extensions(analysis_extensions, DEFAULT_ANALYSIS_EXTENSIONS)
    total = (
        session.query(func.count(LibraryAuditFile.id))
        .filter(LibraryAuditFile.is_present.is_(True))
        .filter(LibraryAuditFile.extension.in_(analyzable))
        .scalar()
        or 0
    )
    if total <= 0:
        return 100.0, 0, 0
    still_pending = (
        session.query(func.count(LibraryAuditFile.id))
        .filter(LibraryAuditFile.is_present.is_(True))
        .filter(LibraryAuditFile.extension.in_(analyzable))
        .filter(LibraryAuditFile.analysis_state.in_(["PENDING", "ERROR", "STALE", "ANALYZING"]))
        .scalar()
        or 0
    )
    triaged = max(0, total - still_pending)
    pct = 100.0 * float(triaged) / float(total)
    return pct, triaged, total


def should_run_deep_batch(
    *,
    deep_batch_size: int,
    prefer_triage_first: bool,
    triage_progress_pct: float,
    deep_after_triage_pct: float = DEFAULT_DEEP_AFTER_TRIAGE_PCT,
) -> tuple[bool, str | None]:
    """Decide whether this cycle should run the deep batch."""
    if deep_batch_size <= 0:
        return False, "deep_batch_size_zero"
    if not prefer_triage_first:
        return True, None
    if triage_progress_pct + 1e-9 >= deep_after_triage_pct:
        return True, None
    return False, "triage_below_threshold"


def count_needs_review(session: Session, threshold: str = "WARNING") -> int:
    threshold_rank = REVIEW_THRESHOLD_ORDER.get((threshold or "WARNING").upper(), 1)
    # Files with analysis at/above threshold and no applicable current review
    q = (
        session.query(LibraryAuditFile)
        .filter(LibraryAuditFile.is_present.is_(True))
        .filter(LibraryAuditFile.analysis_state == "ANALYZED")
        .filter(LibraryAuditFile.current_analysis_id.isnot(None))
        .filter(LibraryAuditFile.current_review_id.is_(None))
        .all()
    )
    count = 0
    for row in q:
        analysis = session.get(LibraryAuditAnalysis, row.current_analysis_id)
        if not analysis:
            continue
        if analysis.verdict not in NEEDS_REVIEW_VERDICTS:
            continue
        if REVIEW_THRESHOLD_ORDER.get(analysis.verdict, 0) >= threshold_rank:
            count += 1
    return count


def create_review(
    session: Session,
    file_id: int,
    disposition: str,
    note: str | None = None,
    reviewed_by: str | None = None,
) -> LibraryAuditReview:
    disposition = normalize_disposition(disposition) or ""
    if disposition not in DISPOSITIONS:
        raise ValueError(f"Invalid disposition: {disposition}")
    row = session.get(LibraryAuditFile, file_id)
    if not row:
        raise KeyError(f"File {file_id} not found")
    analysis_id = row.current_analysis_id
    content_hash = row.content_hash
    if analysis_id:
        analysis = session.get(LibraryAuditAnalysis, analysis_id)
        if analysis and analysis.content_hash:
            content_hash = analysis.content_hash
    review = LibraryAuditReview(
        file_id=file_id,
        analysis_id=analysis_id,
        content_hash=content_hash,
        disposition=disposition,
        note=note,
        reviewed_at=datetime.now(UTC),
        reviewed_by=reviewed_by,
    )
    session.add(review)
    session.flush()
    row.current_review_id = review.id
    session.commit()
    return review


def queue_reanalyze(session: Session, file_id: int) -> LibraryAuditFile:
    """Mark file PENDING for the next command batch (bulk/queue path)."""
    row = session.get(LibraryAuditFile, file_id)
    if not row:
        raise KeyError(f"File {file_id} not found")
    if not is_analyzable_extension(row.extension, DEFAULT_ANALYSIS_EXTENSIONS):
        raise ValueError(f"No analyzer available for extension {row.extension or '(none)'} yet")
    row.analysis_state = "PENDING"
    row.analysis_queued_at = datetime.now(UTC)
    row.last_analysis_error = None
    session.commit()
    return row


def reanalyze_file_now(
    session: Session,
    file_id: int,
    root: Path,
    provider: AnalyzerProvider | None = None,
    mode: str = "standard",
) -> tuple[LibraryAuditFile, LibraryAuditAnalysis | None]:
    """Run analysis immediately for one file (UI Reanalyze button)."""
    row = session.get(LibraryAuditFile, file_id)
    if not row:
        raise KeyError(f"File {file_id} not found")
    if not is_analyzable_extension(row.extension, DEFAULT_ANALYSIS_EXTENSIONS):
        raise ValueError(f"No analyzer available for extension {row.extension or '(none)'} yet")
    if not row.is_present:
        raise ValueError("File is marked missing; run inventory first")
    provider = provider or get_composite_provider()
    # Immediate UI reanalyze uses deep path for accuracy
    analysis = analyze_file(session, row, Path(root), provider, mode="deep")
    session.refresh(row)
    return row, analysis


def clear_current_review(session: Session, file_id: int) -> LibraryAuditFile:
    """Clear the active disposition so the file returns to Needs review."""
    row = session.get(LibraryAuditFile, file_id)
    if not row:
        raise KeyError(f"File {file_id} not found")
    row.current_review_id = None
    session.commit()
    return row


def build_stats(session: Session, provider: AnalyzerProvider | None = None) -> dict[str, Any]:
    provider = provider or get_composite_provider()
    health = provider.health()
    present = (
        session.query(func.count(LibraryAuditFile.id))
        .filter(LibraryAuditFile.is_present.is_(True))
        .scalar()
        or 0
    )
    missing = (
        session.query(func.count(LibraryAuditFile.id))
        .filter(LibraryAuditFile.is_present.is_(False))
        .scalar()
        or 0
    )
    analyzed = (
        session.query(func.count(LibraryAuditFile.id))
        .filter(LibraryAuditFile.is_present.is_(True))
        .filter(LibraryAuditFile.analysis_state == "ANALYZED")
        .scalar()
        or 0
    )
    pending = count_pending(session)
    pending_deep = count_pending_deep(session)
    triage_pct, triage_done, triage_total = triage_progress(session)
    unsupported = (
        session.query(func.count(LibraryAuditFile.id))
        .filter(LibraryAuditFile.is_present.is_(True))
        .filter(LibraryAuditFile.analysis_state == "UNSUPPORTED")
        .scalar()
        or 0
    )
    errors = (
        session.query(func.count(LibraryAuditFile.id))
        .filter(LibraryAuditFile.is_present.is_(True))
        .filter(LibraryAuditFile.analysis_state == "ERROR")
        .scalar()
        or 0
    )

    by_extension: dict[str, int] = {}
    by_format_kind = {"lossless": 0, "lossy": 0, "unknown": 0}
    present_rows = (
        session.query(LibraryAuditFile.extension)
        .filter(LibraryAuditFile.is_present.is_(True))
        .all()
    )
    for (ext,) in present_rows:
        key = (ext or "unknown").lower()
        by_extension[key] = by_extension.get(key, 0) + 1
        kind = format_kind_for_extension(ext)
        by_format_kind[kind] = by_format_kind.get(kind, 0) + 1

    verdict_counts = {
        "authentic": 0,
        "warning": 0,
        "suspicious": 0,
        "fake_certain": 0,
        "inconclusive": 0,
        "error": 0,
    }
    integrity_counts = {
        "duration_mismatch": 0,
        "corrupted": 0,
        "any": 0,
    }
    # Latest analysis per present analyzed file (exclude PENDING_DEEP provisional from verdict pies?
    # Include them as warning/etc so progress is visible; Fake Certain only after deep.)
    rows = (
        session.query(LibraryAuditFile)
        .filter(LibraryAuditFile.is_present.is_(True))
        .filter(LibraryAuditFile.current_analysis_id.isnot(None))
        .filter(LibraryAuditFile.analysis_state.in_(["ANALYZED", "PENDING_DEEP"]))
        .all()
    )
    for row in rows:
        analysis = session.get(LibraryAuditAnalysis, row.current_analysis_id)
        if not analysis:
            continue
        disposition = None
        if row.current_review_id:
            rev = session.get(LibraryAuditReview, row.current_review_id)
            if rev and not (
                rev.content_hash and row.content_hash and rev.content_hash != row.content_hash
            ):
                disposition = rev.disposition
        # PENDING_DEEP must not inflate Fake Certain — use stored (already demoted) verdict
        key = (effective_verdict(analysis.verdict, disposition) or "").lower()
        if key in verdict_counts:
            verdict_counts[key] += 1
        ev = analysis.evidence_json if isinstance(analysis.evidence_json, dict) else {}
        integ = ev.get("integrity") if isinstance(ev.get("integrity"), dict) else {}
        hit = False
        if integ.get("duration_mismatch"):
            integrity_counts["duration_mismatch"] += 1
            hit = True
        if integ.get("is_corrupted") or ev.get("is_corrupted"):
            integrity_counts["corrupted"] += 1
            hit = True
        if hit:
            integrity_counts["any"] += 1

    review_counts = {
        "needs_review": count_needs_review(session),
        "false_positive": 0,
        "best_available": 0,
        "confirmed_transcode": 0,
        "replace": 0,
        "ignored": 0,
        "unsure": 0,
    }
    reviewed = (
        session.query(LibraryAuditFile)
        .filter(LibraryAuditFile.is_present.is_(True))
        .filter(LibraryAuditFile.current_review_id.isnot(None))
        .all()
    )
    for row in reviewed:
        rev = session.get(LibraryAuditReview, row.current_review_id)
        if not rev:
            continue
        # Only count if review still matches current content hash
        if rev.content_hash and row.content_hash and rev.content_hash != row.content_hash:
            continue
        d = (normalize_disposition(rev.disposition) or "").lower()
        if d == "ignore":
            review_counts["ignored"] += 1
        elif d in review_counts:
            review_counts[d] += 1

    last_inv = (
        session.query(LibraryAuditInventoryRun)
        .order_by(LibraryAuditInventoryRun.started_at.desc())
        .first()
    )
    last_an = (
        session.query(LibraryAuditAnalysisRun)
        .order_by(LibraryAuditAnalysisRun.started_at.desc())
        .first()
    )

    return {
        "provider": {
            "name": health.provider,
            "version": health.provider_version,
            "healthy": health.healthy,
            "message": health.message,
        },
        "library": {
            "present": present,
            "missing": missing,
            "analyzed": analyzed,
            "pending": pending,
            "pending_deep": pending_deep,
            "unsupported": unsupported,
            "errors": errors,
            "triage_progress_pct": round(triage_pct, 1),
            "triage_done": triage_done,
            "triage_total": triage_total,
        },
        "formats": {
            "by_kind": by_format_kind,
            "by_extension": dict(sorted(by_extension.items(), key=lambda kv: (-kv[1], kv[0]))),
        },
        "verdicts": verdict_counts,
        "integrity": integrity_counts,
        "review": review_counts,
        "last_inventory_run": _serialize_inventory_run(last_inv) if last_inv else None,
        "last_analysis_run": _serialize_analysis_run(last_an) if last_an else None,
    }


def _serialize_inventory_run(run: LibraryAuditInventoryRun) -> dict[str, Any]:
    return {
        "id": run.id,
        "started_at": run.started_at.isoformat() if run.started_at else None,
        "completed_at": run.completed_at.isoformat() if run.completed_at else None,
        "status": run.status,
        "root_path": run.root_path,
        "files_seen": run.files_seen,
        "eligible_files_seen": run.eligible_files_seen,
        "new_files": run.new_files,
        "changed_files": run.changed_files,
        "missing_files": run.missing_files,
        "errors": run.errors,
        "duration_seconds": run.duration_seconds,
        "error_message": run.error_message,
    }


def _serialize_analysis_run(run: LibraryAuditAnalysisRun) -> dict[str, Any]:
    return {
        "id": run.id,
        "started_at": run.started_at.isoformat() if run.started_at else None,
        "completed_at": run.completed_at.isoformat() if run.completed_at else None,
        "status": run.status,
        "requested_limit": run.requested_limit,
        "attempted": run.attempted,
        "completed": run.completed,
        "authentic": run.authentic,
        "warning": run.warning,
        "suspicious": run.suspicious,
        "fake_certain": run.fake_certain,
        "inconclusive": run.inconclusive,
        "errors": run.errors,
        "duration_seconds": run.duration_seconds,
        "provider": run.provider,
        "provider_version": run.provider_version,
    }


def run_audit_cycle(
    session: Session,
    root: Path,
    *,
    analysis_batch_size: int | None = None,
    triage_batch_size: int = 150,
    deep_batch_size: int = 10,
    inventory_interval_hours: int = 24,
    inventory_extensions: list[str] | None = None,
    analysis_extensions: list[str] | None = None,
    extensions: list[str] | None = None,  # legacy alias for inventory_extensions
    missing_retention_days: int = 90,
    provider_mode: str = "triage",
    force_inventory: bool = False,
    provider: AnalyzerProvider | None = None,
    triage_sample_seconds: float = 20.0,
    deep_sample_seconds: float = 60.0,
    short_track_seconds: float = 10.0,
    require_deep_for_fake_certain: bool = True,
    prefer_triage_first: bool = True,
    deep_after_triage_pct: float = DEFAULT_DEEP_AFTER_TRIAGE_PCT,
) -> AuditRunSummary:
    """Run inventory (if due), triage batch, then deep batch when allowed.

    When ``prefer_triage_first`` is True (default), deep is skipped until triage
    progress reaches ``deep_after_triage_pct`` (default 80). Set
    ``prefer_triage_first=False`` to force a deep batch every run.
    ``deep_batch_size=0`` disables deep entirely.
    """
    from services.library_audit.flac_detective import FlacAnalysisOptions

    summary = AuditRunSummary()
    flac_options = FlacAnalysisOptions(
        triage_sample_seconds=triage_sample_seconds,
        deep_sample_seconds=deep_sample_seconds,
        short_track_seconds=short_track_seconds,
        require_deep_for_fake_certain=require_deep_for_fake_certain,
    )
    provider = provider or get_composite_provider(flac_options=flac_options)

    inv_exts = inventory_extensions if inventory_extensions is not None else extensions
    inv_exts = normalize_extensions(inv_exts, DEFAULT_INVENTORY_EXTENSIONS)
    an_exts = normalize_extensions(analysis_extensions, DEFAULT_ANALYSIS_EXTENSIONS)

    # Legacy single batch size → triage
    if analysis_batch_size is not None and triage_batch_size == 150:
        triage_batch_size = max(1, min(500, int(analysis_batch_size)))

    do_inventory = force_inventory or inventory_due(session, inventory_interval_hours)
    if do_inventory:
        summary.inventory = run_inventory(
            session,
            root,
            extensions=inv_exts,
            analysis_extensions=an_exts,
        )
    else:
        summary.inventory_skipped = True

    # Triage first (clear confident Authentic), then deep queue when allowed.
    # Legacy provider_mode "standard" must NOT force deep-only — that was the old
    # single-pass mode and is still present in many saved command configs.
    mode_l = (provider_mode or "triage").lower().strip()
    deep_only = mode_l == "deep"

    if not deep_only:
        summary.triage = run_analysis_batch(
            session,
            root,
            limit=max(1, min(500, int(triage_batch_size))),
            provider=provider,
            mode="triage",
            analysis_extensions=an_exts,
            states=["PENDING", "ERROR", "STALE"],
        )
        pct, _, _ = triage_progress(session, an_exts)
        summary.triage_progress_pct = pct
        run_deep, skip_reason = should_run_deep_batch(
            deep_batch_size=int(deep_batch_size),
            prefer_triage_first=prefer_triage_first,
            triage_progress_pct=pct,
            deep_after_triage_pct=deep_after_triage_pct,
        )
        if run_deep:
            summary.deep = run_analysis_batch(
                session,
                root,
                limit=max(1, min(50, int(deep_batch_size))),
                provider=provider,
                mode="deep",
                analysis_extensions=an_exts,
                states=["PENDING_DEEP"],
            )
        else:
            summary.deep_skipped = True
            summary.deep_skip_reason = skip_reason
    else:
        deep_limit = int(deep_batch_size) if int(deep_batch_size) > 0 else int(triage_batch_size)
        summary.deep = run_analysis_batch(
            session,
            root,
            limit=max(1, min(50, deep_limit)),
            provider=provider,
            mode="deep",
            analysis_extensions=an_exts,
            states=["PENDING", "PENDING_DEEP", "ERROR", "STALE"],
        )
        pct, _, _ = triage_progress(session, an_exts)
        summary.triage_progress_pct = pct

    # Combined rollup for command stats / last analysis run (deep run is latest)
    summary.analysis = AnalysisBatchResult(
        run_id=summary.deep.run_id or summary.triage.run_id,
        attempted=summary.triage.attempted + summary.deep.attempted,
        completed=summary.triage.completed + summary.deep.completed,
        authentic=summary.triage.authentic + summary.deep.authentic,
        warning=summary.triage.warning + summary.deep.warning,
        suspicious=summary.triage.suspicious + summary.deep.suspicious,
        fake_certain=summary.triage.fake_certain + summary.deep.fake_certain,
        inconclusive=summary.triage.inconclusive + summary.deep.inconclusive,
        errors=summary.triage.errors + summary.deep.errors,
        duration_seconds=(summary.triage.duration_seconds or 0)
        + (summary.deep.duration_seconds or 0),
        provider=summary.deep.provider or summary.triage.provider,
        provider_version=summary.deep.provider_version or summary.triage.provider_version,
    )

    summary.retention_deleted = cleanup_missing_records(session, missing_retention_days)
    summary.pending_queue = count_pending(session)
    summary.pending_deep = count_pending_deep(session)
    summary.needs_review = count_needs_review(session)
    if summary.triage_progress_pct is None:
        pct, _, _ = triage_progress(session, an_exts)
        summary.triage_progress_pct = pct
    return summary
