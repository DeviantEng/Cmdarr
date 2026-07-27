#!/usr/bin/env python3
"""API for Lidarr maintenance stats and Wanted-search ignore list."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from database.config_models import CommandConfig, CommandExecution, LidarrWantedSearchIgnore
from database.database import get_config_db

router = APIRouter()


def _serialize_ignore(row: LidarrWantedSearchIgnore) -> dict[str, Any]:
    return {
        "id": row.id,
        "lidarr_album_id": row.lidarr_album_id,
        "foreign_album_id": row.foreign_album_id,
        "artist_name": row.artist_name,
        "album_title": row.album_title,
        "album_type": row.album_type,
        "release_date": row.release_date,
        "ignored_at": row.ignored_at.isoformat() if row.ignored_at else None,
        "ignored_until": row.ignored_until.isoformat() if row.ignored_until else None,
        "reason": row.reason,
        "command_name": row.command_name,
        "search_count": row.search_count,
    }


def _command_rollups(db: Session, prefix: str) -> dict[str, Any]:
    rows = (
        db.query(CommandConfig)
        .filter(CommandConfig.command_name.like(f"{prefix}_%"))
        .filter(CommandConfig.deleted_at.is_(None))
        .all()
    )
    commands = []
    total_runs = 0
    total_success = 0
    total_failure = 0
    lifetime_searched = 0
    lifetime_found = 0
    lifetime_ignored = 0

    for row in rows:
        cfg = row.config_json or {}
        total_runs += int(row.total_execution_count or 0)
        total_success += int(row.total_success_count or 0)
        total_failure += int(row.total_failure_count or 0)
        lifetime_searched += int(cfg.get("lifetime_searched") or 0)
        lifetime_found += int(cfg.get("lifetime_downloads_found") or 0)
        lifetime_ignored += int(cfg.get("lifetime_ignored") or 0)
        commands.append(
            {
                "command_name": row.command_name,
                "display_name": row.display_name,
                "enabled": bool(row.enabled),
                "last_run": row.last_run.isoformat() if row.last_run else None,
                "last_success": row.last_success,
                "total_execution_count": row.total_execution_count or 0,
                "total_success_count": row.total_success_count or 0,
                "total_failure_count": row.total_failure_count or 0,
                "config_json": {
                    "top_x": cfg.get("top_x"),
                    "ignore_days": cfg.get("ignore_days"),
                    "sort_by": cfg.get("sort_by"),
                    "album_types": cfg.get("album_types"),
                    "lifetime_searched": cfg.get("lifetime_searched", 0),
                    "lifetime_downloads_found": cfg.get("lifetime_downloads_found", 0),
                    "lifetime_ignored": cfg.get("lifetime_ignored", 0),
                },
            }
        )

    return {
        "command_count": len(commands),
        "commands": commands,
        "total_execution_count": total_runs,
        "total_success_count": total_success,
        "total_failure_count": total_failure,
        "lifetime_searched": lifetime_searched,
        "lifetime_downloads_found": lifetime_found,
        "lifetime_ignored": lifetime_ignored,
    }


@router.get("/stats")
async def lidarr_maintenance_stats(db: Annotated[Session, Depends(get_config_db)]):
    """Aggregate stats for Lidarr maintenance commands and ignore list."""
    now = datetime.now(UTC)
    active_ignores = (
        db.query(LidarrWantedSearchIgnore)
        .filter(LidarrWantedSearchIgnore.ignored_until > now)
        .count()
    )
    total_ignores = db.query(LidarrWantedSearchIgnore).count()

    recent = (
        db.query(CommandExecution)
        .filter(
            (CommandExecution.command_name.like("lidarr_update_all_%"))
            | (CommandExecution.command_name.like("lidarr_wanted_search_%"))
        )
        .order_by(CommandExecution.started_at.desc())
        .limit(20)
        .all()
    )
    recent_runs = [
        {
            "id": e.id,
            "command_name": e.command_name,
            "success": e.success,
            "status": e.status,
            "started_at": e.started_at.isoformat() if e.started_at else None,
            "duration": e.duration,
            "output_summary": e.output_summary,
            "triggered_by": e.triggered_by,
        }
        for e in recent
    ]

    update_all = _command_rollups(db, "lidarr_update_all")
    wanted_search = _command_rollups(db, "lidarr_wanted_search")

    return {
        "update_all": update_all,
        "wanted_search": wanted_search,
        "ignore": {
            "active_count": active_ignores,
            "total_count": total_ignores,
        },
        "recent_runs": recent_runs,
    }


@router.get("/ignore")
async def list_wanted_search_ignores(
    db: Annotated[Session, Depends(get_config_db)],
    active_only: bool = Query(True),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
):
    """List Wanted-search ignore entries."""
    now = datetime.now(UTC)
    q = db.query(LidarrWantedSearchIgnore)
    if active_only:
        q = q.filter(LidarrWantedSearchIgnore.ignored_until > now)
    total = q.count()
    rows = (
        q.order_by(LidarrWantedSearchIgnore.ignored_until.asc()).offset(offset).limit(limit).all()
    )
    return {
        "total": total,
        "items": [_serialize_ignore(r) for r in rows],
    }


@router.delete("/ignore/{ignore_id}")
async def restore_wanted_search_ignore(
    ignore_id: int, db: Annotated[Session, Depends(get_config_db)]
):
    """Remove one album from the Wanted-search ignore list."""
    row = (
        db.query(LidarrWantedSearchIgnore).filter(LidarrWantedSearchIgnore.id == ignore_id).first()
    )
    if not row:
        raise HTTPException(status_code=404, detail="Ignore entry not found")
    db.delete(row)
    db.commit()
    return {"success": True}


@router.post("/ignore/restore-all")
async def restore_all_wanted_search_ignores(db: Annotated[Session, Depends(get_config_db)]):
    """Clear the entire Wanted-search ignore list."""
    deleted = db.query(LidarrWantedSearchIgnore).delete(synchronize_session=False)
    db.commit()
    return {"success": True, "deleted": deleted}
