#!/usr/bin/env python3
"""API for Library Audit status, files, reviews, and actions."""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from database.database import get_library_audit_db
from database.library_audit_models import (
    LibraryAuditAnalysis,
    LibraryAuditAnalysisRun,
    LibraryAuditFile,
    LibraryAuditInventoryRun,
    LibraryAuditReview,
)
from services.config_service import config_service
from services.library_audit.flac_detective import get_default_provider
from services.library_audit.service import (
    build_stats,
    create_review,
    get_music_root,
    is_feature_enabled,
    queue_reanalyze,
    validate_root,
)

router = APIRouter()


def _require_enabled() -> None:
    if not is_feature_enabled(config_service.get):
        raise HTTPException(status_code=400, detail="Library Audit is disabled")


class ReviewRequest(BaseModel):
    disposition: str
    note: str | None = None
    reviewed_by: str | None = None


class BulkReviewRequest(BaseModel):
    file_ids: list[int] = Field(default_factory=list)
    disposition: str
    note: str | None = None
    reviewed_by: str | None = None


class BulkReanalyzeRequest(BaseModel):
    file_ids: list[int] = Field(default_factory=list)


def _serialize_file(
    row: LibraryAuditFile,
    analysis: LibraryAuditAnalysis | None = None,
    review: LibraryAuditReview | None = None,
) -> dict[str, Any]:
    return {
        "id": row.id,
        "relative_path": row.relative_path,
        "file_name": row.file_name,
        "parent_path": row.parent_path,
        "extension": row.extension,
        "size_bytes": row.size_bytes,
        "mtime_ns": row.mtime_ns,
        "content_hash": row.content_hash,
        "is_present": row.is_present,
        "missing_since": row.missing_since.isoformat() if row.missing_since else None,
        "analysis_state": row.analysis_state,
        "analysis_queued_at": row.analysis_queued_at.isoformat()
        if row.analysis_queued_at
        else None,
        "analysis_attempts": row.analysis_attempts,
        "last_analysis_error": row.last_analysis_error,
        "current_analysis_id": row.current_analysis_id,
        "current_review_id": row.current_review_id,
        "artist": row.artist,
        "album": row.album,
        "title": row.title,
        "track_number": row.track_number,
        "disc_number": row.disc_number,
        "sample_rate": row.sample_rate,
        "bits_per_sample": row.bits_per_sample,
        "channels": row.channels,
        "duration_seconds": row.duration_seconds,
        "first_seen_at": row.first_seen_at.isoformat() if row.first_seen_at else None,
        "last_seen_at": row.last_seen_at.isoformat() if row.last_seen_at else None,
        "analysis": _serialize_analysis(analysis) if analysis else None,
        "review": _serialize_review(review) if review else None,
    }


def _serialize_analysis(a: LibraryAuditAnalysis) -> dict[str, Any]:
    return {
        "id": a.id,
        "file_id": a.file_id,
        "provider": a.provider,
        "provider_version": a.provider_version,
        "provider_mode": a.provider_mode,
        "verdict": a.verdict,
        "score": a.score,
        "confidence": a.confidence,
        "cutoff_hz": a.cutoff_hz,
        "is_hires_suspect": a.is_hires_suspect,
        "summary": a.summary,
        "evidence": a.evidence_json,
        "raw_result": a.raw_result_json,
        "content_hash": a.content_hash,
        "file_size_bytes": a.file_size_bytes,
        "file_mtime_ns": a.file_mtime_ns,
        "started_at": a.started_at.isoformat() if a.started_at else None,
        "completed_at": a.completed_at.isoformat() if a.completed_at else None,
        "duration_seconds": a.duration_seconds,
    }


def _serialize_review(r: LibraryAuditReview) -> dict[str, Any]:
    return {
        "id": r.id,
        "file_id": r.file_id,
        "analysis_id": r.analysis_id,
        "content_hash": r.content_hash,
        "disposition": r.disposition,
        "note": r.note,
        "reviewed_at": r.reviewed_at.isoformat() if r.reviewed_at else None,
        "reviewed_by": r.reviewed_by,
    }


@router.get("/status")
async def library_audit_status():
    """Feature + root + provider status (safe when disabled)."""
    enabled = is_feature_enabled(config_service.get)
    root = get_music_root(config_service.get)
    root_ok, root_msg = validate_root(root) if enabled else (False, "Feature disabled")
    provider = get_default_provider()
    health = provider.health()
    caps = provider.capabilities()
    return {
        "enabled": enabled,
        "root": str(root),
        "root_ok": bool(enabled and root_ok),
        "root_message": root_msg if enabled else "Feature disabled",
        "provider": {
            "name": health.provider,
            "version": health.provider_version,
            "healthy": health.healthy,
            "message": health.message,
            "modes": caps.modes,
            "extensions": caps.extensions,
        },
    }


@router.get("/stats")
async def library_audit_stats(db: Annotated[Session, Depends(get_library_audit_db)]):
    _require_enabled()
    stats = build_stats(db)
    status = await library_audit_status()
    return {**status, **stats}


@router.get("/runs")
async def library_audit_runs(
    db: Annotated[Session, Depends(get_library_audit_db)],
    limit: int = Query(20, ge=1, le=100),
):
    _require_enabled()
    inv = (
        db.query(LibraryAuditInventoryRun)
        .order_by(LibraryAuditInventoryRun.started_at.desc())
        .limit(limit)
        .all()
    )
    an = (
        db.query(LibraryAuditAnalysisRun)
        .order_by(LibraryAuditAnalysisRun.started_at.desc())
        .limit(limit)
        .all()
    )
    from services.library_audit.service import _serialize_analysis_run, _serialize_inventory_run

    return {
        "inventory_runs": [_serialize_inventory_run(r) for r in inv],
        "analysis_runs": [_serialize_analysis_run(r) for r in an],
    }


@router.get("/files")
async def list_files(
    db: Annotated[Session, Depends(get_library_audit_db)],
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    present: bool | None = Query(None),
    analysis_state: str | None = Query(None),
    verdict: str | None = Query(None),
    disposition: str | None = Query(None),
    needs_review: bool | None = Query(None),
    q: str | None = Query(None, description="Path search"),
):
    _require_enabled()
    query = db.query(LibraryAuditFile)
    if present is not None:
        query = query.filter(LibraryAuditFile.is_present.is_(present))
    if analysis_state:
        query = query.filter(LibraryAuditFile.analysis_state == analysis_state.upper())
    if q:
        like = f"%{q}%"
        query = query.filter(LibraryAuditFile.relative_path.ilike(like))

    rows = query.order_by(LibraryAuditFile.relative_path.asc()).all()

    items: list[dict[str, Any]] = []
    for row in rows:
        analysis = (
            db.get(LibraryAuditAnalysis, row.current_analysis_id)
            if row.current_analysis_id
            else None
        )
        review = (
            db.get(LibraryAuditReview, row.current_review_id) if row.current_review_id else None
        )
        # Invalidate stale review for filtering if content hash mismatch
        applicable_review = review
        if (
            review
            and review.content_hash
            and row.content_hash
            and review.content_hash != row.content_hash
        ):
            applicable_review = None

        if verdict:
            if not analysis or analysis.verdict.upper() != verdict.upper():
                continue
        if disposition:
            if (
                not applicable_review
                or applicable_review.disposition.upper() != disposition.upper()
            ):
                continue
        if needs_review is True:
            if applicable_review is not None:
                continue
            if not analysis or analysis.verdict not in {
                "WARNING",
                "SUSPICIOUS",
                "FAKE_CERTAIN",
                "INCONCLUSIVE",
                "ERROR",
            }:
                continue
        if needs_review is False:
            # no extra filter
            pass

        items.append(_serialize_file(row, analysis, applicable_review))

    # Sort needs_review queue by severity then oldest analysis
    if needs_review is True:
        severity = {
            "FAKE_CERTAIN": 0,
            "SUSPICIOUS": 1,
            "WARNING": 2,
            "INCONCLUSIVE": 3,
            "ERROR": 4,
        }

        def sort_key(item: dict[str, Any]):
            a = item.get("analysis") or {}
            return (
                severity.get(a.get("verdict"), 9),
                a.get("completed_at") or "",
            )

        items.sort(key=sort_key)

    total = len(items)
    page = items[offset : offset + limit]
    return {"total": total, "limit": limit, "offset": offset, "items": page}


@router.get("/files/{file_id}")
async def get_file(file_id: int, db: Annotated[Session, Depends(get_library_audit_db)]):
    _require_enabled()
    row = db.get(LibraryAuditFile, file_id)
    if not row:
        raise HTTPException(status_code=404, detail="File not found")
    analysis = (
        db.get(LibraryAuditAnalysis, row.current_analysis_id) if row.current_analysis_id else None
    )
    review = db.get(LibraryAuditReview, row.current_review_id) if row.current_review_id else None
    return _serialize_file(row, analysis, review)


@router.get("/files/{file_id}/analyses")
async def list_analyses(file_id: int, db: Annotated[Session, Depends(get_library_audit_db)]):
    _require_enabled()
    row = db.get(LibraryAuditFile, file_id)
    if not row:
        raise HTTPException(status_code=404, detail="File not found")
    rows = (
        db.query(LibraryAuditAnalysis)
        .filter(LibraryAuditAnalysis.file_id == file_id)
        .order_by(LibraryAuditAnalysis.completed_at.desc())
        .all()
    )
    return {"items": [_serialize_analysis(a) for a in rows]}


@router.get("/files/{file_id}/reviews")
async def list_reviews(file_id: int, db: Annotated[Session, Depends(get_library_audit_db)]):
    _require_enabled()
    row = db.get(LibraryAuditFile, file_id)
    if not row:
        raise HTTPException(status_code=404, detail="File not found")
    rows = (
        db.query(LibraryAuditReview)
        .filter(LibraryAuditReview.file_id == file_id)
        .order_by(LibraryAuditReview.reviewed_at.desc())
        .all()
    )
    return {"items": [_serialize_review(r) for r in rows]}


@router.post("/files/{file_id}/review")
async def post_review(
    file_id: int,
    body: ReviewRequest,
    db: Annotated[Session, Depends(get_library_audit_db)],
):
    _require_enabled()
    try:
        review = create_review(
            db,
            file_id,
            disposition=body.disposition,
            note=body.note,
            reviewed_by=body.reviewed_by,
        )
    except KeyError:
        raise HTTPException(status_code=404, detail="File not found") from None
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return _serialize_review(review)


@router.post("/files/{file_id}/reanalyze")
async def post_reanalyze(file_id: int, db: Annotated[Session, Depends(get_library_audit_db)]):
    _require_enabled()
    try:
        row = queue_reanalyze(db, file_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="File not found") from None
    return {"success": True, "file_id": row.id, "analysis_state": row.analysis_state}


@router.post("/bulk/review")
async def bulk_review(
    body: BulkReviewRequest, db: Annotated[Session, Depends(get_library_audit_db)]
):
    _require_enabled()
    updated = 0
    errors: list[dict[str, Any]] = []
    for fid in body.file_ids:
        try:
            create_review(
                db,
                fid,
                disposition=body.disposition,
                note=body.note,
                reviewed_by=body.reviewed_by,
            )
            updated += 1
        except Exception as exc:
            errors.append({"file_id": fid, "error": str(exc)})
    return {"success": True, "updated": updated, "errors": errors}


@router.post("/bulk/reanalyze")
async def bulk_reanalyze(
    body: BulkReanalyzeRequest, db: Annotated[Session, Depends(get_library_audit_db)]
):
    _require_enabled()
    updated = 0
    errors: list[dict[str, Any]] = []
    for fid in body.file_ids:
        try:
            queue_reanalyze(db, fid)
            updated += 1
        except Exception as exc:
            errors.append({"file_id": fid, "error": str(exc)})
    return {"success": True, "updated": updated, "errors": errors}


@router.post("/test")
async def test_library_audit():
    """Validate feature enablement, root, and analyzer health."""
    enabled = is_feature_enabled(config_service.get)
    root = get_music_root(config_service.get)
    checks = []
    checks.append(
        {
            "name": "feature_enabled",
            "success": enabled,
            "message": "Enabled" if enabled else "LIBRARY_AUDIT_ENABLED is false",
        }
    )
    root_ok, root_msg = validate_root(root)
    checks.append({"name": "root", "success": root_ok, "message": root_msg, "root": str(root)})
    health = get_default_provider().health()
    checks.append(
        {
            "name": "provider",
            "success": health.healthy,
            "message": health.message,
            "provider": health.provider,
            "version": health.provider_version,
        }
    )
    overall = all(c["success"] for c in checks)
    return {"success": overall, "checks": checks}
