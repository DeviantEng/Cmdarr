#!/usr/bin/env python3
"""
Status API endpoints
"""

import asyncio
import os
import time
from datetime import datetime, timedelta
from typing import Annotated, Any

import psutil
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

from __version__ import __version__
from database.config_models import CommandConfig, CommandExecution
from database.database import get_config_db
from services.config_service import config_service
from utils.logger import get_logger

router = APIRouter()


# Lazy-load logger to avoid initialization issues
def get_status_logger():
    return get_logger("cmdarr.api.status")


_SINCE_TOKENS: dict[str, timedelta] = {
    "1d": timedelta(days=1),
    "3d": timedelta(days=3),
    "7d": timedelta(days=7),
    "14d": timedelta(days=14),
    "30d": timedelta(days=30),
    "90d": timedelta(days=90),
    "1y": timedelta(days=365),
}


def parse_execution_since(since: str | None) -> datetime | None:
    """Parse a relative since token into a UTC cutoff, or None for no lower bound."""
    if since is None or since == "all":
        return None
    token = since.strip().lower()
    if token in _SINCE_TOKENS:
        return datetime.utcnow() - _SINCE_TOKENS[token]
    try:
        parsed = datetime.fromisoformat(token.replace("Z", "+00:00"))
        if parsed.tzinfo is not None:
            parsed = parsed.replace(tzinfo=None)
        return parsed
    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid since value: {since}. Use 1d, 3d, 7d, 14d, 30d, 90d, 1y, all, or ISO datetime.",
        ) from exc


def _execution_status(execution: CommandExecution) -> str:
    if execution.is_running:
        return "running"
    if execution.completed_at is not None:
        return "completed" if execution.success else "failed"
    return "running"


def _serialize_execution(
    execution: CommandExecution, command_config: CommandConfig | None
) -> dict[str, Any]:
    status = _execution_status(execution)
    return {
        "id": execution.id,
        "command_name": execution.command_name,
        "display_name": command_config.display_name
        if command_config
        else execution.command_name.replace("_", " "),
        "started_at": execution.started_at.isoformat() + "Z",
        "completed_at": execution.completed_at.isoformat() + "Z"
        if execution.completed_at
        else None,
        "success": execution.success,
        "duration": execution.duration,
        "error_message": execution.error_message,
        "triggered_by": execution.triggered_by,
        "is_running": execution.is_running,
        "status": status,
        "output_summary": execution.output_summary,
        "target": command_config.config_json.get("target", "unknown")
        if command_config and command_config.config_json
        else "unknown",
    }


def _filtered_executions_query(
    db: Session,
    since_cutoff: datetime | None,
    command_name: str | None,
):
    query = db.query(CommandExecution)
    if since_cutoff is not None:
        query = query.filter(CommandExecution.started_at >= since_cutoff)
    if command_name and command_name.lower() != "all":
        query = query.filter(CommandExecution.command_name == command_name)
    return query


def _execution_summary(
    db: Session, since_cutoff: datetime | None, command_name: str | None
) -> dict:
    base = _filtered_executions_query(db, since_cutoff, command_name)
    total_count = base.count()
    success_count = base.filter(
        CommandExecution.status == "completed",
        CommandExecution.success.is_(True),
    ).count()
    failure_count = base.filter(
        CommandExecution.status.in_(["failed"]),
    ).count()
    running_count = base.filter(CommandExecution.status == "running").count()

    avg_duration = (
        base.filter(
            CommandExecution.completed_at.isnot(None),
            CommandExecution.duration.isnot(None),
        )
        .with_entities(func.avg(CommandExecution.duration))
        .scalar()
    )

    return {
        "total_count": total_count,
        "success_count": success_count,
        "failure_count": failure_count,
        "running_count": running_count,
        "avg_duration_seconds": round(float(avg_duration), 2) if avg_duration is not None else None,
    }


@router.get("/system")
async def get_system_status():
    """Get system status and health information"""
    try:
        # Get system information
        system_info = {
            "app_name": "Cmdarr",
            "version": __version__,
            "uptime_seconds": time.time() - psutil.Process().create_time(),
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "python_version": f"{os.sys.version_info.major}.{os.sys.version_info.minor}.{os.sys.version_info.micro}",
            "platform": os.name,
        }

        # Get memory usage
        memory = psutil.virtual_memory()
        system_info["memory"] = {
            "total_mb": round(memory.total / 1024 / 1024, 2),
            "available_mb": round(memory.available / 1024 / 1024, 2),
            "used_mb": round(memory.used / 1024 / 1024, 2),
            "percent_used": memory.percent,
        }

        # Get disk usage
        disk = psutil.disk_usage("/")
        system_info["disk"] = {
            "total_gb": round(disk.total / 1024 / 1024 / 1024, 2),
            "used_gb": round(disk.used / 1024 / 1024 / 1024, 2),
            "free_gb": round(disk.free / 1024 / 1024 / 1024, 2),
            "percent_used": round((disk.used / disk.total) * 100, 2),
        }

        # Get CPU usage
        cpu_percent = psutil.cpu_percent(interval=1)
        system_info["cpu"] = {"percent_used": cpu_percent, "core_count": psutil.cpu_count()}

        return system_info
    except Exception as e:
        get_status_logger().error(f"Failed to get system status: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve system status")


@router.get("/health")
async def get_health_status():
    """Get detailed health status"""
    try:
        health_status = {
            "overall_status": "healthy",
            "checks": {},
            "timestamp": datetime.utcnow().isoformat() + "Z",
        }

        # Database health check
        try:
            from sqlalchemy import text

            from database.database import get_database_manager

            db_manager = get_database_manager()
            session = db_manager.get_session_sync()
            try:
                session.execute(text("SELECT 1"))
                health_status["checks"]["database"] = {
                    "status": "healthy",
                    "message": "Database connection successful",
                }
            finally:
                session.close()
        except Exception as e:
            get_status_logger().error(f"Database connection check failed: {e}")
            health_status["checks"]["database"] = {
                "status": "unhealthy",
                "message": "Database connection failed",
            }
            health_status["overall_status"] = "unhealthy"

        # Configuration health check
        try:
            missing_config = config_service.validate_required_settings()
            if missing_config:
                health_status["checks"]["configuration"] = {
                    "status": "unhealthy",
                    "message": f"Missing required configuration: {missing_config}",
                }
                health_status["overall_status"] = "unhealthy"
            else:
                health_status["checks"]["configuration"] = {
                    "status": "healthy",
                    "message": "All required configuration present",
                }
        except Exception as e:
            get_status_logger().error(f"Configuration validation check failed: {e}")
            health_status["checks"]["configuration"] = {
                "status": "unhealthy",
                "message": "Configuration validation failed",
            }
            health_status["overall_status"] = "unhealthy"

        # Commands health check
        try:
            from database.database import get_database_manager

            db_manager = get_database_manager()
            session = db_manager.get_session_sync()
            try:
                # Get all enabled commands, excluding helper commands and deleted
                all_enabled_commands = (
                    session.query(CommandConfig)
                    .filter(
                        CommandConfig.enabled,
                        CommandConfig.deleted_at.is_(None),
                    )
                    .all()
                )
                helper_commands = {"library_cache_builder"}  # Known helper commands

                # Filter out helper commands
                user_enabled_commands = [
                    cmd for cmd in all_enabled_commands if cmd.command_name not in helper_commands
                ]
                enabled_commands_count = len(user_enabled_commands)

                running_commands = (
                    session.query(CommandExecution)
                    .filter(CommandExecution.completed_at.is_(None))
                    .count()
                )

                health_status["checks"]["commands"] = {
                    "status": "healthy",
                    "message": f"{enabled_commands_count} enabled commands, {running_commands} currently running",
                }
            finally:
                session.close()
        except Exception as e:
            get_status_logger().error(f"Command status check failed: {e}")
            health_status["checks"]["commands"] = {
                "status": "unhealthy",
                "message": "Command status check failed",
            }
            health_status["overall_status"] = "unhealthy"

        return health_status
    except Exception as e:
        get_status_logger().error(f"Failed to get health status: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve health status")


@router.get("/commands")
async def get_commands_status(db: Annotated[Session, Depends(get_config_db)]):
    """Get status of all commands"""
    try:
        all_commands = db.query(CommandConfig).filter(CommandConfig.deleted_at.is_(None)).all()
        helper_commands = {"library_cache_builder"}  # Known helper commands

        # Filter out helper commands
        commands = [cmd for cmd in all_commands if cmd.command_name not in helper_commands]
        command_statuses = []

        for command in commands:
            # Get recent executions
            recent_executions = (
                db.query(CommandExecution)
                .filter(CommandExecution.command_name == command.command_name)
                .order_by(CommandExecution.started_at.desc())
                .limit(5)
                .all()
            )

            # Check if currently running (only the most recent execution matters)
            is_running = recent_executions[0].is_running if recent_executions else False

            # Get success rate for last 10 executions
            last_10_executions = (
                db.query(CommandExecution)
                .filter(CommandExecution.command_name == command.command_name)
                .filter(CommandExecution.completed_at.isnot(None))
                .order_by(CommandExecution.started_at.desc())
                .limit(10)
                .all()
            )

            success_rate = 0
            if last_10_executions:
                successful = sum(1 for exec in last_10_executions if exec.success)
                success_rate = (successful / len(last_10_executions)) * 100

            command_statuses.append(
                {
                    "command_name": command.command_name,
                    "display_name": command.display_name,
                    "enabled": command.enabled,
                    "schedule_cron": command.schedule_cron,
                    "is_running": is_running,
                    "last_run": command.last_run.isoformat() + "Z" if command.last_run else None,
                    "last_success": command.last_success,
                    "last_duration": command.last_duration,
                    "last_error": command.last_error,
                    "success_rate_percent": round(success_rate, 1),
                    "recent_executions": len(recent_executions),
                }
            )

        return {
            "commands": command_statuses,
            "total_commands": len(commands),
            "enabled_commands": len([c for c in commands if c.enabled]),
            "running_commands": len([c for c in command_statuses if c["is_running"]]),
            "timestamp": datetime.utcnow().isoformat() + "Z",
        }
    except Exception as e:
        get_status_logger().error(f"Failed to get commands status: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve commands status")


@router.get("/executions/recent")
async def get_recent_executions(
    limit: int = Query(default=20, ge=1, le=500),
    since: str | None = Query(default=None),
    command_name: str | None = Query(default=None),
    db: Session = Depends(get_config_db),
):
    """Get command executions with optional time and command filters."""
    try:
        since_cutoff = parse_execution_since(since)
        query = _filtered_executions_query(db, since_cutoff, command_name)
        executions = query.order_by(CommandExecution.started_at.desc()).limit(limit).all()

        command_names = {e.command_name for e in executions}
        configs = (
            {
                c.command_name: c
                for c in db.query(CommandConfig)
                .filter(CommandConfig.command_name.in_(command_names))
                .all()
            }
            if command_names
            else {}
        )

        execution_list = [
            _serialize_execution(execution, configs.get(execution.command_name))
            for execution in executions
        ]
        summary = _execution_summary(db, since_cutoff, command_name)

        return {
            "executions": execution_list,
            "total_count": len(execution_list),
            "summary": summary,
            "filters": {
                "since": since,
                "command_name": command_name
                if command_name and command_name.lower() != "all"
                else None,
            },
            "timestamp": datetime.utcnow().isoformat() + "Z",
        }
    except HTTPException:
        raise
    except Exception as e:
        get_status_logger().error(f"Failed to get recent executions: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve recent executions")


@router.get("/statistics")
async def get_statistics(db: Annotated[Session, Depends(get_config_db)]):
    """Get application statistics"""
    try:
        # Get time range for statistics (last 30 days)
        thirty_days_ago = datetime.utcnow() - timedelta(days=30)

        # Command execution statistics
        total_executions = (
            db.query(CommandExecution)
            .filter(CommandExecution.started_at >= thirty_days_ago)
            .count()
        )

        successful_executions = (
            db.query(CommandExecution)
            .filter(CommandExecution.started_at >= thirty_days_ago)
            .filter(CommandExecution.success)
            .count()
        )

        failed_executions = (
            db.query(CommandExecution)
            .filter(CommandExecution.started_at >= thirty_days_ago)
            .filter(CommandExecution.success.is_(False))
            .count()
        )

        # Average execution time
        completed_executions = (
            db.query(CommandExecution)
            .filter(CommandExecution.started_at >= thirty_days_ago)
            .filter(CommandExecution.completed_at.isnot(None))
            .filter(CommandExecution.duration.isnot(None))
            .all()
        )

        avg_duration = 0
        if completed_executions:
            total_duration = sum(exec.duration for exec in completed_executions)
            avg_duration = total_duration / len(completed_executions)

        # Command-specific statistics
        command_stats = {}
        commands = db.query(CommandConfig).all()
        for command in commands:
            command_executions = (
                db.query(CommandExecution)
                .filter(CommandExecution.command_name == command.command_name)
                .filter(CommandExecution.started_at >= thirty_days_ago)
                .all()
            )

            if command_executions:
                command_successful = sum(1 for exec in command_executions if exec.success)
                command_stats[command.command_name] = {
                    "total_executions": len(command_executions),
                    "successful_executions": command_successful,
                    "success_rate": (command_successful / len(command_executions)) * 100,
                }

        return {
            "period": "last_30_days",
            "total_executions": total_executions,
            "successful_executions": successful_executions,
            "failed_executions": failed_executions,
            "success_rate_percent": round((successful_executions / total_executions) * 100, 1)
            if total_executions > 0
            else 0,
            "average_duration_seconds": round(avg_duration, 2),
            "command_statistics": command_stats,
            "timestamp": datetime.utcnow().isoformat() + "Z",
        }
    except Exception as e:
        get_status_logger().error(f"Failed to get statistics: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve statistics")


async def _get_cache_status_for_target(target: str, cache_manager, cache_stats):
    """Helper function to get cache status for a specific target.
    Uses lightweight metadata query (no full cache load) for fast status page."""
    client_stats = cache_manager.get_client_stats(target)

    cache_info = {
        "target": target,
        "status": "Not available",
        "last_generated": None,
        "size_mb": 0,
        "object_count": 0,
        "cache_hits": client_stats.get("cache_hits", 0),
        "cache_misses": client_stats.get("cache_misses", 0),
        "hit_rate": client_stats.get("hit_rate", 0.0),
        "last_used": client_stats.get("last_used"),
        "memory_usage_mb": cache_stats.get("memory_usage_mb", 0),
    }

    try:
        meta = cache_manager.get_library_cache_metadata(target)
        if meta:
            cache_info.update(
                {
                    "status": "Available",
                    "last_generated": meta.get("built_at"),
                    "size_mb": round((meta.get("size_bytes") or 0) / 1024 / 1024, 2),
                    "object_count": meta.get("track_count", 0),
                }
            )
        else:
            if target not in cache_manager.registered_clients:
                cache_info["status"] = "Not built"
                cache_info["message"] = f"{target} cache not found in database"
            else:
                cache_info["status"] = "Not built"
    except Exception as e:
        get_status_logger().warning(f"Failed to get library cache for {target}: {e}")
        cache_info["status"] = "Error"
        cache_info["error"] = "Failed to retrieve cache status"

    return cache_info


@router.get("/cache")
async def get_cache_status(target: str = None):
    """Get music library cache status for a specific target (plex/jellyfin) or all targets"""
    try:
        from services.config_service import config_service
        from utils.library_cache_manager import get_library_cache_manager

        # Get library cache manager
        cache_manager = get_library_cache_manager(config_service)

        # Get cache statistics
        cache_stats = cache_manager.get_cache_stats()

        # If no target specified, return both Plex and Jellyfin cache info (in parallel)
        if not target:
            plex_result, jellyfin_result = await asyncio.gather(
                _get_cache_status_for_target("plex", cache_manager, cache_stats),
                _get_cache_status_for_target("jellyfin", cache_manager, cache_stats),
            )
            return {"plex": plex_result, "jellyfin": jellyfin_result}

        # Validate target
        if target.lower() not in ["plex", "jellyfin"]:
            raise HTTPException(status_code=400, detail="Target must be 'plex' or 'jellyfin'")

        return await _get_cache_status_for_target(target.lower(), cache_manager, cache_stats)

    except Exception as e:
        get_status_logger().error(f"Failed to get cache status: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve cache status")


@router.get("/nrd-metrics")
async def get_nrd_metrics(db: Annotated[Session, Depends(get_config_db)]):
    """
    New Releases Discovery metrics: Lidarr artist count, artists scanned (fresh within TTL),
    and artists not yet scanned. Helps diagnose why NRD may show nothing.
    """
    try:
        from commands.config_adapter import ConfigAdapter
        from database.config_models import (
            ArtistScanLog,
            DismissedArtistAlbum,
            NewReleaseIgnoredArtist,
        )

        config = ConfigAdapter()
        if not config.LIDARR_API_KEY or not config.LIDARR_URL:
            return {
                "available": False,
                "error": "Lidarr not configured",
                "total_lidarr_artists": None,
                "artists_scanned_fresh": None,
                "artists_not_scanned": None,
                "dismissed_count": None,
                "ignored_count": None,
                "cache_ttl_days": None,
            }

        from clients.client_lidarr import LidarrClient

        cache_ttl_days = getattr(config, "NEW_RELEASES_CACHE_DAYS", 14)
        cutoff = datetime.utcnow() - timedelta(days=cache_ttl_days)

        async with LidarrClient(config) as lidarr_client:
            artists = await lidarr_client.get_all_artists()

        lidarr_mbids = {a.get("musicBrainzId") for a in artists if a.get("musicBrainzId")}
        total = len(lidarr_mbids)

        scan_logs = db.query(ArtistScanLog).filter(ArtistScanLog.last_scanned_at >= cutoff).all()
        scanned_fresh_mbids = {log.artist_mbid for log in scan_logs}
        artists_scanned_fresh = len(lidarr_mbids & scanned_fresh_mbids)

        all_scanned_mbids = {row.artist_mbid for row in db.query(ArtistScanLog.artist_mbid).all()}
        artists_not_scanned = len(lidarr_mbids - all_scanned_mbids)

        dismissed_count = db.query(DismissedArtistAlbum).count()
        ignored_count = db.query(NewReleaseIgnoredArtist).count()

        return {
            "available": True,
            "total_lidarr_artists": total,
            "artists_scanned_fresh": artists_scanned_fresh,
            "artists_not_scanned": artists_not_scanned,
            "dismissed_count": dismissed_count,
            "ignored_count": ignored_count,
            "cache_ttl_days": cache_ttl_days,
            "timestamp": datetime.utcnow().isoformat() + "Z",
        }
    except Exception as e:
        get_status_logger().error(f"Failed to get NRD metrics: {e}")
        return {
            "available": False,
            "error": "Failed to retrieve NRD metrics",
            "total_lidarr_artists": None,
            "artists_scanned_fresh": None,
            "artists_not_scanned": None,
            "dismissed_count": None,
            "ignored_count": None,
            "cache_ttl_days": None,
        }


@router.get("/nrd-metrics/not-scanned-artists")
async def get_nrd_not_scanned_artists(
    db: Annotated[Session, Depends(get_config_db)],
    limit: Annotated[int, Query(ge=1, le=500)] = 500,
):
    """Lidarr artists that have never been scanned for new releases."""
    try:
        from commands.config_adapter import ConfigAdapter
        from database.config_models import ArtistScanLog

        config = ConfigAdapter()
        if not config.LIDARR_API_KEY or not config.LIDARR_URL:
            raise HTTPException(status_code=503, detail="Lidarr not configured")

        from clients.client_lidarr import LidarrClient

        async with LidarrClient(config) as lidarr_client:
            artists = await lidarr_client.get_all_artists()

        scanned_mbids = {row.artist_mbid for row in db.query(ArtistScanLog.artist_mbid).all()}
        not_scanned = []
        for artist in artists:
            mbid = artist.get("musicBrainzId")
            if not mbid or mbid in scanned_mbids:
                continue
            not_scanned.append(
                {
                    "artist_mbid": mbid,
                    "artist_name": artist.get("artistName") or "",
                }
            )
            if len(not_scanned) >= limit:
                break

        return {
            "total": len(not_scanned),
            "items": not_scanned,
            "timestamp": datetime.utcnow().isoformat() + "Z",
        }
    except HTTPException:
        raise
    except Exception as e:
        get_status_logger().error(f"Failed to get not-scanned artists: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve not-scanned artists") from e


@router.get("/migrations")
async def get_db_migrations_status():
    """Schema migration status (dev builds only expose manual run)."""
    try:
        from database.version_migrations import get_migration_status

        return {"success": True, **get_migration_status()}
    except Exception as e:
        get_status_logger().error(f"Failed to get migration status: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve migration status") from e


@router.post("/migrations/run")
async def run_db_migrations_manual():
    """Re-run applicable DB migrations without bumping app version (dev builds only)."""
    if "-dev" not in __version__:
        raise HTTPException(
            status_code=403,
            detail="Manual migrations are only available on -dev builds",
        )
    try:
        from database.version_migrations import run_version_migrations_manual

        result = run_version_migrations_manual()
        if not result.get("ran") and result.get("reason") == "migration_failed":
            raise HTTPException(
                status_code=500,
                detail=f"Migration failed: {result.get('failed_migration')}",
            )
        return {"success": True, **result}
    except HTTPException:
        raise
    except Exception as e:
        get_status_logger().error(f"Manual migration run failed: {e}")
        raise HTTPException(status_code=500, detail="Failed to run migrations") from e


@router.post("/cache/reset")
async def reset_cache_stats():
    """Reset cache statistics for all clients (for testing)"""
    try:
        from services.config_service import config_service
        from utils.library_cache_manager import (
            get_library_cache_manager,
            reset_library_cache_manager,
        )

        # Reset the singleton instance
        reset_library_cache_manager()

        # Get fresh instance
        cache_manager = get_library_cache_manager(config_service)

        # Reset all client stats
        cache_manager.reset_client_stats()

        return {"message": "Cache statistics reset successfully"}

    except Exception as e:
        get_status_logger().error(f"Failed to reset cache stats: {e}")
        raise HTTPException(status_code=500, detail="Failed to reset cache statistics")
