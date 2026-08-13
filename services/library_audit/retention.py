#!/usr/bin/env python3
"""Retention cleanup for Library Audit missing-file records."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy.orm import Session

from database.library_audit_models import LibraryAuditFile
from utils.logger import get_logger


def _log():
    return get_logger("cmdarr.library_audit.retention")


def cleanup_missing_records(session: Session, retention_days: int = 90) -> int:
    """Delete missing file rows (and cascaded analyses/reviews) older than retention."""
    days = max(1, int(retention_days))
    cutoff = datetime.now(UTC) - timedelta(days=days)
    rows = (
        session.query(LibraryAuditFile)
        .filter(LibraryAuditFile.is_present.is_(False))
        .filter(LibraryAuditFile.missing_since.isnot(None))
        .filter(LibraryAuditFile.missing_since < cutoff)
        .all()
    )
    deleted = 0
    for row in rows:
        session.delete(row)
        deleted += 1
    if deleted:
        session.commit()
        _log().info(f"Library audit retention deleted {deleted} missing file record(s)")
    return deleted
