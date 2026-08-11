#!/usr/bin/env python3
"""SQLAlchemy models for Cmdarr library audit database."""

from __future__ import annotations

from sqlalchemy import (
    JSON,
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import declarative_base, relationship
from sqlalchemy.sql import func

LibraryAuditBase = declarative_base()


class LibraryAuditFile(LibraryAuditBase):
    """One inventory row per observed relative path."""

    __tablename__ = "library_audit_file"

    id = Column(Integer, primary_key=True, index=True)
    relative_path = Column(Text, unique=True, nullable=False, index=True)
    file_name = Column(String(500), nullable=True)
    parent_path = Column(Text, nullable=True)
    extension = Column(String(32), nullable=True)

    size_bytes = Column(Integer, nullable=False)
    mtime_ns = Column(Integer, nullable=False)
    content_hash = Column(String(64), nullable=True, index=True)

    first_seen_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    last_seen_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    last_seen_inventory_id = Column(Integer, nullable=True, index=True)

    is_present = Column(Boolean, nullable=False, default=True, index=True)
    missing_since = Column(DateTime(timezone=True), nullable=True)

    analysis_state = Column(String(32), nullable=False, default="PENDING", index=True)
    analysis_queued_at = Column(DateTime(timezone=True), nullable=True)
    analysis_attempts = Column(Integer, nullable=False, default=0)
    last_analysis_error = Column(Text, nullable=True)

    current_analysis_id = Column(Integer, nullable=True)
    current_review_id = Column(Integer, nullable=True)

    # Optional display metadata from analyzer (not used for grouping)
    artist = Column(String(500), nullable=True)
    album = Column(String(500), nullable=True)
    title = Column(String(500), nullable=True)
    track_number = Column(String(32), nullable=True)
    disc_number = Column(String(32), nullable=True)
    sample_rate = Column(Integer, nullable=True)
    bits_per_sample = Column(Integer, nullable=True)
    channels = Column(Integer, nullable=True)
    duration_seconds = Column(Float, nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    analyses = relationship(
        "LibraryAuditAnalysis",
        back_populates="file",
        cascade="all, delete-orphan",
        foreign_keys="LibraryAuditAnalysis.file_id",
    )
    reviews = relationship(
        "LibraryAuditReview",
        back_populates="file",
        cascade="all, delete-orphan",
        foreign_keys="LibraryAuditReview.file_id",
    )


class LibraryAuditAnalysis(LibraryAuditBase):
    """Immutable machine-analysis history for a file."""

    __tablename__ = "library_audit_analysis"

    id = Column(Integer, primary_key=True, index=True)
    file_id = Column(
        Integer,
        ForeignKey("library_audit_file.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    provider = Column(String(64), nullable=False)
    provider_version = Column(String(64), nullable=True)
    provider_mode = Column(String(64), nullable=True)
    analysis_schema_version = Column(Integer, nullable=False, default=1)
    analyzer_config_hash = Column(String(64), nullable=True)

    started_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    duration_seconds = Column(Float, nullable=True)

    verdict = Column(String(32), nullable=False, index=True)
    score = Column(Float, nullable=True)
    confidence = Column(String(200), nullable=True)
    cutoff_hz = Column(Float, nullable=True)
    is_hires_suspect = Column(Boolean, nullable=True)

    summary = Column(Text, nullable=True)
    evidence_json = Column(JSON, nullable=True)
    raw_result_json = Column(JSON, nullable=True)

    file_size_bytes = Column(Integer, nullable=False)
    file_mtime_ns = Column(Integer, nullable=False)
    content_hash = Column(String(64), nullable=True, index=True)

    file = relationship(
        "LibraryAuditFile",
        back_populates="analyses",
        foreign_keys=[file_id],
    )


class LibraryAuditReview(LibraryAuditBase):
    """Human disposition history for a file analysis."""

    __tablename__ = "library_audit_review"

    id = Column(Integer, primary_key=True, index=True)
    file_id = Column(
        Integer,
        ForeignKey("library_audit_file.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    analysis_id = Column(
        Integer,
        ForeignKey("library_audit_analysis.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    content_hash = Column(String(64), nullable=True, index=True)

    disposition = Column(String(32), nullable=False, index=True)
    note = Column(Text, nullable=True)

    reviewed_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    reviewed_by = Column(String(200), nullable=True)

    file = relationship(
        "LibraryAuditFile",
        back_populates="reviews",
        foreign_keys=[file_id],
    )


class LibraryAuditInventoryRun(LibraryAuditBase):
    """One filesystem inventory cycle."""

    __tablename__ = "library_audit_inventory_run"

    id = Column(Integer, primary_key=True, index=True)
    started_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    completed_at = Column(DateTime(timezone=True), nullable=True)
    status = Column(String(32), nullable=False, default="RUNNING", index=True)
    root_path = Column(Text, nullable=False)
    files_seen = Column(Integer, nullable=False, default=0)
    eligible_files_seen = Column(Integer, nullable=False, default=0)
    new_files = Column(Integer, nullable=False, default=0)
    changed_files = Column(Integer, nullable=False, default=0)
    missing_files = Column(Integer, nullable=False, default=0)
    errors = Column(Integer, nullable=False, default=0)
    duration_seconds = Column(Float, nullable=True)
    error_message = Column(Text, nullable=True)


class LibraryAuditAnalysisRun(LibraryAuditBase):
    """Batch analysis KPI history."""

    __tablename__ = "library_audit_analysis_run"

    id = Column(Integer, primary_key=True, index=True)
    started_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    completed_at = Column(DateTime(timezone=True), nullable=True)
    status = Column(String(32), nullable=False, default="RUNNING", index=True)
    requested_limit = Column(Integer, nullable=False, default=0)
    attempted = Column(Integer, nullable=False, default=0)
    completed = Column(Integer, nullable=False, default=0)
    authentic = Column(Integer, nullable=False, default=0)
    warning = Column(Integer, nullable=False, default=0)
    suspicious = Column(Integer, nullable=False, default=0)
    fake_certain = Column(Integer, nullable=False, default=0)
    inconclusive = Column(Integer, nullable=False, default=0)
    errors = Column(Integer, nullable=False, default=0)
    duration_seconds = Column(Float, nullable=True)
    provider = Column(String(64), nullable=True)
    provider_version = Column(String(64), nullable=True)
