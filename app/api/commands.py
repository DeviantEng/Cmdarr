#!/usr/bin/env python3
"""
Commands API endpoints
"""

from datetime import datetime
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session

from database.config_models import CommandConfig, CommandExecution
from database.database import get_config_db
from services.command_executor import command_executor
from utils.logger import get_logger

router = APIRouter()


# Lazy-load logger to avoid initialization issues
def get_commands_logger():
    return get_logger("cmdarr.api.commands")


def utc_datetime_serializer(dt: datetime | None) -> str | None:
    """Serialize UTC datetime with Z suffix for proper JavaScript parsing"""
    if dt is None:
        return None
    return dt.isoformat() + "Z"


def _get_next_run_for_command(command: CommandConfig) -> datetime | None:
    """Calculate next run time for command using cron (global or per-command override)."""
    from services.scheduler import calculate_next_run_cron
    from utils.timezone import get_scheduler_timezone

    tz = get_scheduler_timezone()
    return calculate_next_run_cron(command, tz)


class CommandUpdateRequest(BaseModel):
    """Request model for updating command configuration"""

    enabled: bool | None = None
    schedule_cron: str | None = None
    schedule_override: bool | None = None  # True = use schedule_cron, False = use global
    timeout_minutes: int | None = None
    config_json: dict[str, Any] | None = None


class CommandExecutionRequest(BaseModel):
    """Request model for executing a command"""

    triggered_by: str = "api"  # 'api', 'manual', 'scheduler'


class CommandConfigResponse(BaseModel):
    """Response model for command configuration"""

    id: int
    command_name: str
    display_name: str
    description: str | None
    enabled: bool
    schedule_cron: str | None
    schedule_override: bool | None  # True when using per-command cron
    timeout_minutes: int | None
    config_json: dict[str, Any] | None
    command_type: str | None
    last_run: str | None
    last_success: bool | None
    last_duration: float | None
    last_error: str | None
    next_run: str | None
    created_at: str
    updated_at: str


def command_to_response(command: CommandConfig) -> CommandConfigResponse:
    """Convert CommandConfig to CommandConfigResponse with next_run calculation"""
    command_dict = command.__dict__.copy()
    next_run = _get_next_run_for_command(command)
    command_dict["schedule_override"] = bool(
        command.schedule_cron and command.schedule_cron.strip()
    )
    command_dict["last_run"] = utc_datetime_serializer(command.last_run)
    command_dict["next_run"] = utc_datetime_serializer(next_run)
    command_dict["created_at"] = utc_datetime_serializer(command.created_at)
    command_dict["updated_at"] = utc_datetime_serializer(command.updated_at)
    return CommandConfigResponse(**command_dict)


class CommandExecutionResponse(BaseModel):
    """Response model for command execution"""

    id: int
    command_name: str
    started_at: str
    completed_at: str | None
    success: bool | None
    status: str
    duration: float | None
    error_message: str | None
    result_data: dict[str, Any] | None
    triggered_by: str
    is_running: bool
    target: str | None = None


@router.get("/", response_model=list[CommandConfigResponse])
async def get_all_commands(db: Annotated[Session, Depends(get_config_db)]):
    """Get all command configurations (excluding helper commands and soft-deleted)"""
    try:
        commands = db.query(CommandConfig).filter(CommandConfig.deleted_at.is_(None)).all()

        # Filter out helper commands
        visible_commands = []
        helper_commands = {"library_cache_builder"}  # Known helper commands

        for command in commands:
            if command.command_name in helper_commands:
                continue  # Skip helper commands

            visible_commands.append(command)

        return [command_to_response(command) for command in visible_commands]
    except Exception as e:
        get_commands_logger().error(f"Failed to get commands: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve commands")


@router.get("/plex-accounts")
async def get_plex_accounts(
    db: Annotated[Session, Depends(get_config_db)],
    editing_command: str | None = None,
):
    """Get Plex Home managed accounts for daylist/local discovery user selection dropdown.
    Returns empty list when Plex client is not enabled (allows UI to render).
    daylist_used_ids and local_discovery_used_ids exclude users who already have a command.
    When editing_command is provided, that command's user is excluded from the used lists."""
    try:
        from clients.client_plex import PlexClient
        from commands.config_adapter import Config

        config = Config()
        if not config.get("PLEX_CLIENT_ENABLED", False):
            return {"accounts": [], "daylist_used_ids": [], "local_discovery_used_ids": []}

        plex = PlexClient(config)
        accounts = plex.get_accounts()

        daylist_used_ids: list[str] = []
        local_discovery_used_ids: list[str] = []
        for cmd in db.query(CommandConfig).filter(CommandConfig.deleted_at.is_(None)).all():
            cfg = cmd.config_json or {}
            aid = cfg.get("plex_history_account_id")
            if not aid:
                continue
            aid_str = str(aid)
            if cmd.command_name.startswith("daylist_"):
                if cmd.command_name != editing_command:
                    daylist_used_ids.append(aid_str)
            elif cmd.command_name.startswith("local_discovery_"):
                if cmd.command_name != editing_command:
                    local_discovery_used_ids.append(aid_str)

        return {
            "accounts": accounts,
            "daylist_used_ids": daylist_used_ids,
            "local_discovery_used_ids": local_discovery_used_ids,
        }
    except HTTPException:
        raise
    except Exception as e:
        get_commands_logger().error(f"Failed to get Plex accounts: {e}")
        raise HTTPException(status_code=500, detail="Failed to get Plex accounts") from None


@router.get("/daylist/exists")
async def daylist_exists(db: Annotated[Session, Depends(get_config_db)]):
    """Check if a daylist command already exists (for New Command UI grey-out)."""
    existing = (
        db.query(CommandConfig)
        .filter(CommandConfig.command_name.like("daylist_%"))
        .filter(CommandConfig.deleted_at.is_(None))
        .first()
    )
    return {"exists": existing is not None}


@router.get("/status/scheduler")
async def get_scheduler_status():
    """Get scheduler status and information"""
    try:
        from services.scheduler import scheduler

        queue_status = scheduler.get_queue_status()

        return {
            "running": scheduler.running,
            "scheduled_commands": list(scheduler.get_scheduled_commands()),
            "check_interval_seconds": scheduler.check_interval,
            "queue_size": queue_status["queue_size"],
            "currently_running": queue_status["currently_running"],
        }
    except Exception as e:
        get_commands_logger().error(f"Failed to get scheduler status: {e}")
        raise HTTPException(status_code=500, detail="Failed to get scheduler status")


@router.get("/playlist-sync/validate-url")
async def validate_playlist_url(url: str = Query(..., max_length=2048)):
    """Validate playlist URL and fetch metadata"""
    try:
        from clients.client_deezer import DeezerClient
        from clients.client_spotify import SpotifyClient
        from commands.config_adapter import Config
        from utils.playlist_parser import parse_playlist_url

        parsed = parse_playlist_url(url)

        if not parsed["valid"]:
            return {
                "valid": False,
                "error": parsed["error"],
                "supported_sources": ["spotify", "deezer"],
                "example_url": "https://open.spotify.com/playlist/4NDXWHwYWjFmgVPkNy4YlF",
            }

        source = parsed["source"]
        config = Config()

        if source == "spotify":
            spotify_client = SpotifyClient(config)
            try:
                metadata = await spotify_client.get_playlist_info(url)

                if metadata.get("success"):
                    return {
                        "valid": True,
                        "source": source,
                        "playlist_id": parsed["playlist_id"],
                        "metadata": {
                            "name": metadata["name"],
                            "description": metadata["description"],
                            "track_count": metadata["track_count"],
                            "owner": metadata["owner"],
                        },
                    }
                else:
                    return {"valid": False, "error": "Failed to fetch playlist metadata"}
            finally:
                await spotify_client.close()
        elif source == "deezer":
            deezer_client = DeezerClient(config)
            try:
                metadata = await deezer_client.get_playlist_info(url)

                if metadata.get("success"):
                    return {
                        "valid": True,
                        "source": source,
                        "playlist_id": parsed["playlist_id"],
                        "metadata": {
                            "name": metadata["name"],
                            "description": metadata["description"],
                            "track_count": metadata["track_count"],
                            "owner": metadata["owner"],
                        },
                    }
                else:
                    return {"valid": False, "error": "Failed to fetch playlist metadata"}
            finally:
                await deezer_client.close()
        else:
            return {"valid": False, "error": f"Source {source} not yet supported"}

    except Exception as e:
        get_commands_logger().error(f"Failed to validate playlist URL: {e}")
        return {"valid": False, "error": "Failed to validate URL"}


@router.get("/{command_name}", response_model=CommandConfigResponse)
async def get_command(command_name: str, db: Annotated[Session, Depends(get_config_db)]):
    """Get a specific command configuration"""
    try:
        command = (
            db.query(CommandConfig)
            .filter(
                CommandConfig.command_name == command_name,
                CommandConfig.deleted_at.is_(None),
            )
            .first()
        )
        if not command:
            raise HTTPException(status_code=404, detail="Command not found")

        return command_to_response(command)
    except HTTPException:
        raise
    except Exception as e:
        get_commands_logger().error(f"Failed to get command {command_name}: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve command")


@router.put("/{command_name}")
async def update_command(
    command_name: str, request: CommandUpdateRequest, db: Annotated[Session, Depends(get_config_db)]
):
    """Update a command configuration"""
    try:
        command = (
            db.query(CommandConfig)
            .filter(
                CommandConfig.command_name == command_name,
                CommandConfig.deleted_at.is_(None),
            )
            .first()
        )
        if not command:
            raise HTTPException(status_code=404, detail="Command not found")

        # Track if enabled status or schedule changed
        enabled_changed = request.enabled is not None and request.enabled != command.enabled
        schedule_changed = (
            request.schedule_cron is not None
            and request.schedule_cron != (command.schedule_cron or "")
        ) or (request.schedule_override is not None)

        if request.enabled is not None:
            command.enabled = request.enabled

        if request.schedule_override is not None:
            if not request.schedule_override:
                command.schedule_cron = None
            elif request.schedule_cron:
                command.schedule_cron = request.schedule_cron.strip() or None

        if request.schedule_cron is not None and request.schedule_override:
            command.schedule_cron = request.schedule_cron.strip() or None

        if request.timeout_minutes is not None:
            command.timeout_minutes = request.timeout_minutes
        if request.config_json is not None:
            prev_config_snapshot = dict(command.config_json or {})
            # Validate Spotify credentials and API access when switching NRD to Spotify source
            if command_name == "new_releases_discovery":
                src = (request.config_json.get("new_releases_source") or "deezer").strip().lower()
                if src == "spotify":
                    from clients.client_spotify import SpotifyClient
                    from commands.config_adapter import ConfigAdapter

                    config = ConfigAdapter()
                    if not config.SPOTIFY_CLIENT_ID or not config.SPOTIFY_CLIENT_SECRET:
                        raise HTTPException(
                            status_code=400,
                            detail="Spotify credentials must be set in Config → Music Sources before using Spotify as the release source.",
                        )
                    # Verify API actually works (e.g. not 403 Premium required)
                    client = SpotifyClient(config)
                    try:
                        connected = await client.test_connection()
                        if not connected:
                            raise HTTPException(
                                status_code=400,
                                detail="Spotify API requires Premium for Development Mode. Use Deezer as the release source instead.",
                            )
                    finally:
                        await client.close()
            command.config_json = request.config_json
            # Playlist generators: keep display_name in sync with playlist title on save; delete prior
            # playlist on Plex/Jellyfin when title or target changes so orphans are not left behind.
            if command_name.startswith("lfm_similar_"):
                from commands.playlist_generator_helpers import compute_lfm_similar_playlist_title
                from services.command_cleanup import CommandCleanupService

                merged = dict(command.config_json or {})
                new_title = compute_lfm_similar_playlist_title(merged)
                old_last = prev_config_snapshot.get("last_playlist_title")
                old_target = str(prev_config_snapshot.get("target", "plex")).lower()
                new_target = str(merged.get("target", "plex")).lower()
                if old_last and (old_last != new_title or old_target != new_target):
                    CommandCleanupService()._delete_playlist_if_exists(old_target, old_last)
                    merged.pop("last_playlist_title", None)
                    command.config_json = merged
                command.display_name = new_title
            elif command_name.startswith("top_tracks_"):
                from commands.playlist_generator_helpers import (
                    compute_top_tracks_playlist_title_from_config,
                )
                from services.command_cleanup import CommandCleanupService

                merged = dict(command.config_json or {})
                new_title = compute_top_tracks_playlist_title_from_config(merged)
                old_last = prev_config_snapshot.get("last_playlist_title")
                old_target = str(prev_config_snapshot.get("target", "plex")).lower()
                new_target = str(merged.get("target", "plex")).lower()
                if old_last and (old_last != new_title or old_target != new_target):
                    CommandCleanupService()._delete_playlist_if_exists(old_target, old_last)
                    merged.pop("last_playlist_title", None)
                    command.config_json = merged
                command.display_name = new_title
            # display_name for daylist/local_discovery: sync when plex_history_account_id changes
            elif command_name.startswith("daylist_") or command_name.startswith("local_discovery_"):
                plex_account_id = request.config_json.get("plex_history_account_id")
                if plex_account_id:
                    from commands.config_adapter import Config

                    config = Config()
                    from clients.client_plex import PlexClient

                    pc = PlexClient(config)
                    accounts = pc.get_accounts()
                    account_name = next(
                        (a["name"] for a in accounts if a["id"] == str(plex_account_id)),
                        str(plex_account_id),
                    )
                    account_name = account_name or str(plex_account_id)
                    if command_name.startswith("daylist_"):
                        command.display_name = f"[Cmdarr] [{account_name}] Daylist"
                    else:
                        command.display_name = f"[Cmdarr] [{account_name}] Local Discovery"
            elif (
                command_name.startswith("playlist_sync_")
                and (request.config_json.get("source") or "") != "listenbrainz"
                and (request.config_json.get("target") or "").lower() == "plex"
            ):
                plex_account_ids = request.config_json.get("plex_account_ids") or []
                if isinstance(plex_account_ids, list) and len(plex_account_ids) > 0:
                    from commands.config_adapter import Config

                    config = Config()
                    from clients.client_plex import PlexClient

                    pc = PlexClient(config)
                    accounts = pc.get_accounts()
                    source = (request.config_json.get("source") or "unknown").title()
                    playlist_name = request.config_json.get("playlist_name") or "playlist"
                    names = []
                    for aid in plex_account_ids:
                        acc = next((a for a in accounts if str(a.get("id", "")) == str(aid)), None)
                        names.append(acc["name"] if acc else str(aid))
                    user_bracket = f" [{', '.join(names)}] "
                else:
                    source = (request.config_json.get("source") or "unknown").title()
                    playlist_name = request.config_json.get("playlist_name") or "playlist"
                    user_bracket = " "
                command.display_name = f"[{source}]{user_bracket}{playlist_name} → Plex"
            elif command_name.startswith("xmplaylist_"):
                from commands.playlist_generator_xmplaylist import _build_xmplaylist_display_name

                command.display_name = _build_xmplaylist_display_name(
                    dict(command.config_json or {})
                )

        command.updated_at = datetime.utcnow()
        db.commit()

        # Refresh the command object to ensure we have the latest data
        db.refresh(command)

        # Notify scheduler of changes
        if enabled_changed or schedule_changed:
            try:
                from services.scheduler import scheduler

                if command.enabled:
                    if schedule_changed:
                        await scheduler.update_command_schedule(command_name)
                    else:
                        await scheduler.enable_command(command_name)
                else:
                    await scheduler.disable_command(command_name)
            except Exception as e:
                get_commands_logger().warning(
                    f"Failed to notify scheduler of command {command_name} change: {e}"
                )

        return {"message": f"Command {command_name} updated successfully"}
    except HTTPException:
        raise
    except Exception as e:
        get_commands_logger().error(f"Failed to update command {command_name}: {e}")
        raise HTTPException(status_code=500, detail="Failed to update command")


@router.post("/{command_name}/execute")
async def execute_command(
    command_name: str,
    request: CommandExecutionRequest,
    db: Annotated[Session, Depends(get_config_db)],
):
    """Execute a command"""
    try:
        # Check if command exists and is enabled (exclude soft-deleted)
        command = (
            db.query(CommandConfig)
            .filter(
                CommandConfig.command_name == command_name,
                CommandConfig.deleted_at.is_(None),
            )
            .first()
        )
        if not command:
            raise HTTPException(status_code=404, detail="Command not found")

        if not command.enabled:
            raise HTTPException(status_code=400, detail="Command is disabled")

        # Execute command using command executor
        get_commands_logger().info(
            f"API: Executing command {command_name} with triggered_by='{request.triggered_by}'"
        )
        result = await command_executor.execute_command(command_name, None, request.triggered_by)

        if result["success"]:
            # Use display_name for user-facing message
            display_name = command.display_name or command_name
            msg = result["message"]
            if "started successfully" in msg:
                msg = f'Command "{display_name}" started'
            elif "queued" in msg:
                msg = f'Command "{display_name}" queued (will run when a slot is available)'
            return {"message": msg, "execution_id": result["execution_id"]}
        else:
            raise HTTPException(status_code=400, detail=result["error"])

    except HTTPException:
        raise
    except Exception as e:
        get_commands_logger().error(f"Failed to execute command {command_name}: {e}")
        raise HTTPException(status_code=500, detail="Failed to execute command")


@router.post("/{command_name}/cancel")
async def cancel_command(command_name: str, db: Annotated[Session, Depends(get_config_db)]):
    """Cancel the currently running execution for a command (if any)"""
    try:
        command = (
            db.query(CommandConfig)
            .filter(
                CommandConfig.command_name == command_name,
                CommandConfig.deleted_at.is_(None),
            )
            .first()
        )
        if not command:
            raise HTTPException(status_code=404, detail="Command not found")

        # Find the running execution for this command
        execution = (
            db.query(CommandExecution)
            .filter(
                CommandExecution.command_name == command_name,
                CommandExecution.status == "running",
            )
            .order_by(CommandExecution.started_at.desc())
            .first()
        )

        if not execution:
            raise HTTPException(
                status_code=404,
                detail=f"No running execution for command {command_name}",
            )

        execution_id = execution.id

        # Update the execution status to cancelled
        execution.status = "cancelled"
        execution.completed_at = datetime.utcnow()
        execution.success = False
        execution.error_message = "Execution cancelled by user"

        if execution.started_at:
            execution.duration = (execution.completed_at - execution.started_at).total_seconds()

        command_config = (
            db.query(CommandConfig)
            .filter(CommandConfig.command_name == execution.command_name)
            .first()
        )
        if command_config:
            command_config.last_run = datetime.utcnow()
            command_config.total_execution_count = (command_config.total_execution_count or 0) + 1
            command_config.total_failure_count = (command_config.total_failure_count or 0) + 1

        db.commit()

        try:
            command_executor.kill_execution(execution_id)
        except Exception as e:
            get_commands_logger().warning(
                f"Failed to kill process for execution {execution_id}: {e}"
            )

        get_commands_logger().info(f"Execution {execution_id} cancelled successfully")
        return {"message": f"Command {command_name} cancelled successfully"}

    except HTTPException:
        raise
    except Exception as e:
        get_commands_logger().error(f"Failed to cancel command {command_name}: {e}")
        raise HTTPException(status_code=500, detail="Failed to cancel command")


@router.get("/{command_name}/executions", response_model=list[CommandExecutionResponse])
async def get_command_executions(
    command_name: str, limit: int = 50, db: Session = Depends(get_config_db)
):
    """Get execution history for a command"""
    try:
        executions = (
            db.query(CommandExecution)
            .filter(CommandExecution.command_name == command_name)
            .order_by(CommandExecution.started_at.desc())
            .limit(limit)
            .all()
        )

        result = []
        for execution in executions:
            # Get command configuration to extract target information
            command_config = (
                db.query(CommandConfig)
                .filter(CommandConfig.command_name == execution.command_name)
                .first()
            )

            execution_dict = {
                "id": execution.id,
                "command_name": execution.command_name,
                "started_at": utc_datetime_serializer(execution.started_at),
                "completed_at": utc_datetime_serializer(execution.completed_at),
                "success": execution.success,
                "status": execution.status,
                "duration": execution.duration,
                "error_message": execution.error_message,
                "result_data": execution.result_data,
                "triggered_by": execution.triggered_by,
                "is_running": execution.is_running,
                "target": command_config.config_json.get("target", "unknown")
                if command_config and command_config.config_json
                else "unknown",
            }
            result.append(CommandExecutionResponse(**execution_dict))
        return result
    except Exception as e:
        get_commands_logger().error(f"Failed to get executions for command {command_name}: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve command executions")


@router.get("/{command_name}/status")
async def get_command_status(command_name: str, db: Annotated[Session, Depends(get_config_db)]):
    """Get current status of a command"""
    try:
        command = db.query(CommandConfig).filter(CommandConfig.command_name == command_name).first()
        if not command:
            raise HTTPException(status_code=404, detail="Command not found")

        # Get status from command executor
        status = await command_executor.get_command_status(command_name)

        return {
            "command_name": command_name,
            "enabled": command.enabled,
            "schedule_cron": command.schedule_cron,
            "is_running": status.get("is_running", False),
            "last_execution": status.get("last_execution"),
        }
    except HTTPException:
        raise
    except Exception as e:
        get_commands_logger().error(f"Failed to get status for command {command_name}: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve command status")


@router.post("/cleanup-stuck")
async def cleanup_stuck_executions():
    """Clean up stuck command executions"""
    try:
        await command_executor.cleanup_stuck_executions()
        return {"message": "Stuck executions cleaned up successfully"}
    except Exception as e:
        get_commands_logger().error(f"Failed to cleanup stuck executions: {e}")
        raise HTTPException(status_code=500, detail="Failed to cleanup stuck executions")


@router.post("/executions/{execution_id}/kill")
async def kill_execution(execution_id: int, db: Annotated[Session, Depends(get_config_db)]):
    """Kill a running command execution"""
    try:
        # Get the execution
        execution = db.query(CommandExecution).filter(CommandExecution.id == execution_id).first()
        if not execution:
            raise HTTPException(status_code=404, detail="Execution not found")

        # Check if it's actually running
        if execution.status != "running":
            raise HTTPException(
                status_code=400, detail=f"Execution is not running (status: {execution.status})"
            )

        # Update the execution status to cancelled
        execution.status = "cancelled"
        execution.completed_at = datetime.utcnow()
        execution.success = False
        execution.error_message = "Execution cancelled by user"

        # Calculate duration
        if execution.started_at:
            execution.duration = (execution.completed_at - execution.started_at).total_seconds()

        # Update command's last_run and aggregate stats
        command_config = (
            db.query(CommandConfig)
            .filter(CommandConfig.command_name == execution.command_name)
            .first()
        )
        if command_config:
            command_config.last_run = datetime.utcnow()
            command_config.total_execution_count = (command_config.total_execution_count or 0) + 1
            command_config.total_failure_count = (command_config.total_failure_count or 0) + 1

        db.commit()

        # Try to kill the actual process if it's running
        try:
            command_executor.kill_execution(execution_id)
        except Exception as e:
            get_commands_logger().warning(
                f"Failed to kill process for execution {execution_id}: {e}"
            )

        get_commands_logger().info(f"Execution {execution_id} cancelled successfully")
        return {"message": f"Execution {execution_id} cancelled successfully"}

    except HTTPException:
        raise
    except Exception as e:
        get_commands_logger().error(f"Failed to kill execution {execution_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to kill execution")


@router.delete("/executions/{execution_id}")
async def delete_execution(execution_id: int, db: Annotated[Session, Depends(get_config_db)]):
    """Delete a command execution from history"""
    try:
        # Get the execution
        execution = db.query(CommandExecution).filter(CommandExecution.id == execution_id).first()
        if not execution:
            raise HTTPException(status_code=404, detail="Execution not found")

        # Don't allow deleting running executions
        if execution.status == "running":
            raise HTTPException(status_code=400, detail="Cannot delete running execution")

        # Delete the execution
        db.delete(execution)
        db.commit()

        get_commands_logger().info(f"Execution {execution_id} deleted successfully")
        return {"message": f"Execution {execution_id} deleted successfully"}

    except HTTPException:
        raise
    except Exception as e:
        get_commands_logger().error(f"Failed to delete execution {execution_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to delete execution")


@router.delete("/executions")
async def clear_execution_history():
    """Clear all command execution history"""
    try:
        from database.config_models import CommandExecution
        from database.database import get_database_manager

        db_manager = get_database_manager()
        session = db_manager.get_session_sync()
        try:
            # Delete all execution records
            deleted_count = session.query(CommandExecution).delete()
            session.commit()

            get_commands_logger().info(f"Cleared {deleted_count} execution records")
            return {"message": f"Cleared {deleted_count} execution records"}
        finally:
            session.close()
    except Exception as e:
        get_commands_logger().error(f"Failed to clear execution history: {e}")
        raise HTTPException(status_code=500, detail="Failed to clear execution history")


@router.post("/executions/cleanup")
async def cleanup_executions(
    command_name: str | None = None,
    keep_count: int | None = None,
    db: Session = Depends(get_config_db),
):
    """Clean up old command executions, keeping only the most recent ones"""
    try:
        # Get retention count from config if not provided
        if keep_count is None:
            from services.config_service import config_service

            keep_count = config_service.get_int("COMMAND_CLEANUP_RETENTION", 50)

        # Build query
        query = db.query(CommandExecution)
        if command_name:
            query = query.filter(CommandExecution.command_name == command_name)

        # Get total count
        total_count = query.count()

        if total_count <= keep_count:
            return {
                "message": f"No cleanup needed. {total_count} executions found, keeping {keep_count}"
            }

        # Get executions to delete (oldest ones beyond keep_count)
        executions_to_delete = (
            query.order_by(CommandExecution.started_at.desc()).offset(keep_count).all()
        )

        # Delete them
        for execution in executions_to_delete:
            db.delete(execution)

        deleted_count = len(executions_to_delete)
        db.commit()

        get_commands_logger().info(f"Cleaned up {deleted_count} old executions, kept {keep_count}")
        return {
            "message": f"Cleaned up {deleted_count} old executions, kept {keep_count}",
            "deleted_count": deleted_count,
            "kept_count": keep_count,
        }

    except Exception as e:
        get_commands_logger().error(f"Failed to cleanup executions: {e}")
        raise HTTPException(status_code=500, detail="Failed to cleanup executions")


@router.post("/library_cache_builder/refresh")
async def execute_cache_builder(request: Request):
    """Execute library cache builder command manually"""
    try:
        from commands.config_adapter import Config
        from commands.library_cache_builder import LibraryCacheBuilderCommand

        # Parse request body
        body = await request.json()
        target = body.get("target", "all")  # 'plex', 'jellyfin', or 'all'
        force_rebuild = body.get("force_rebuild", False)  # Renamed from force_refresh

        get_commands_logger().info(
            f"Cache builder API called with target='{target}', force_rebuild={force_rebuild}"
        )

        # Create and execute command
        config = Config()
        cmd = LibraryCacheBuilderCommand(config)

        # Execute the command with parameters
        target_filter = target if target != "all" else None
        get_commands_logger().info(
            f"Executing command with target_filter='{target_filter}', force_rebuild={force_rebuild}"
        )
        success = cmd.execute(force_rebuild=force_rebuild, target_filter=target_filter)

        if success:
            return {
                "success": True,
                "message": f"Cache {'rebuilt' if force_rebuild else 'refreshed'} successfully for {target}",
                "force_rebuild": force_rebuild,
                "target": target,
            }
        else:
            return {
                "success": False,
                "error": f"Cache operation failed for {target}",
                "force_rebuild": force_rebuild,
                "target": target,
            }

    except Exception as e:
        get_commands_logger().error(f"Failed to execute cache builder: {e}")
        return {
            "success": False,
            "error": "Cache operation failed",
            "message": "Failed to execute cache builder",
        }


@router.post("/daylist/create")
async def create_daylist(request: dict, db: Annotated[Session, Depends(get_config_db)]):
    """Create a new daylist command (supports multiple instances per user)."""
    try:
        from database.config_models import CommandConfig

        plex_account_id = request.get("plex_history_account_id")
        if not plex_account_id:
            raise HTTPException(status_code=400, detail="plex_history_account_id is required")

        # Get account name for display
        from clients.client_plex import PlexClient
        from commands.config_adapter import Config

        config = Config()
        pc = PlexClient(config)
        accounts = pc.get_accounts()
        account_name = next(
            (a["name"] for a in accounts if a["id"] == str(plex_account_id)),
            str(plex_account_id),
        )
        account_name = account_name or str(plex_account_id)
        display_name = f"[Cmdarr] [{account_name}] Daylist"

        # Dynamic command naming
        existing = (
            db.query(CommandConfig).filter(CommandConfig.command_name.like("daylist_%")).all()
        )
        used_ids = set()
        for cmd in existing:
            try:
                used_ids.add(int(cmd.command_name.split("_")[-1]))
            except ValueError, IndexError:
                pass
        next_id = 1
        while next_id in used_ids:
            next_id += 1
        command_name = f"daylist_{next_id:05d}"
        config_json = {
            "plex_history_account_id": str(plex_account_id),
            "command_name": command_name,
            "schedule_minute": int(request.get("schedule_minute", 0)),
            "exclude_played_days": int(request.get("exclude_played_days", 3)),
            "history_lookback_days": int(request.get("history_lookback_days", 45)),
            "max_tracks": int(request.get("max_tracks", 50)),
            "sonic_similar_limit": int(request.get("sonic_similar_limit", 10)),
            "sonic_similarity_limit": int(request.get("sonic_similarity_limit", 50)),
            "sonic_similarity_distance": float(request.get("sonic_similarity_distance", 0.8)),
            "historical_ratio": float(request.get("historical_ratio", 0.3)),
            "time_periods": request.get("time_periods"),
            "timezone": (request.get("timezone") or "").strip() or None,
            "use_primary_mood": bool(request.get("use_primary_mood", False)),
        }
        config_json["schedule_minute"] = max(0, min(59, config_json["schedule_minute"]))
        if request.get("expires_at"):
            config_json["expires_at"] = request.get("expires_at")
            config_json["expires_at_delete_playlist"] = request.get(
                "expires_at_delete_playlist", True
            )

        cmd = CommandConfig(
            command_name=command_name,
            display_name=display_name,
            description="Builds playlists that evolve throughout the day using Plex Sonic Analysis and listening history. Plex only. Inspired by Meloday.",
            enabled=bool(request.get("enabled", True)),
            schedule_cron=None,
            config_json=config_json,
            command_type="playlist_generator",
        )
        db.add(cmd)
        db.commit()
        db.refresh(cmd)

        command_executor._load_dynamic_daylist_commands()

        return {"message": "Daylist command created successfully", "command_name": command_name}
    except HTTPException:
        raise
    except Exception as e:
        get_commands_logger().error(f"Failed to create daylist: {e}")
        db.rollback()
        raise HTTPException(status_code=500, detail="Failed to create daylist") from None


@router.get("/local-discovery/exists")
async def local_discovery_exists(db: Annotated[Session, Depends(get_config_db)]):
    """Check if a local discovery command already exists (for New Command UI grey-out)."""
    existing = (
        db.query(CommandConfig)
        .filter(CommandConfig.command_name.like("local_discovery_%"))
        .filter(CommandConfig.deleted_at.is_(None))
        .first()
    )
    return {"exists": existing is not None}


@router.post("/local-discovery/create")
async def create_local_discovery(request: dict, db: Annotated[Session, Depends(get_config_db)]):
    """Create a new Local Discovery command (supports multiple instances per user)."""
    try:
        from database.config_models import CommandConfig

        plex_account_id = request.get("plex_history_account_id")
        if not plex_account_id:
            raise HTTPException(status_code=400, detail="plex_history_account_id is required")

        from commands.config_adapter import Config

        config = Config()
        from clients.client_plex import PlexClient

        pc = PlexClient(config)
        library_key = pc.get_resolved_library_key()
        if not library_key:
            raise HTTPException(
                status_code=400,
                detail="Could not resolve Plex library. Configure PLEX_LIBRARY_NAME or add a music library.",
            )

        accounts = pc.get_accounts()
        account_name = next(
            (a["name"] for a in accounts if a["id"] == str(plex_account_id)),
            str(plex_account_id),
        )
        account_name = account_name or str(plex_account_id)
        display_name = f"[Cmdarr] [{account_name}] Local Discovery"

        existing = (
            db.query(CommandConfig)
            .filter(CommandConfig.command_name.like("local_discovery_%"))
            .all()
        )
        used_ids = set()
        for cmd in existing:
            try:
                used_ids.add(int(cmd.command_name.split("_")[-1]))
            except ValueError, IndexError:
                pass
        next_id = 1
        while next_id in used_ids:
            next_id += 1
        command_name = f"local_discovery_{next_id:05d}"

        schedule_cron = (request.get("schedule_cron") or "").strip() or None
        schedule_override = bool(schedule_cron)

        config_json = {
            "plex_history_account_id": str(plex_account_id),
            "command_name": command_name,
            "lookback_days": int(request.get("lookback_days", 90)),
            "exclude_played_days": int(request.get("exclude_played_days", 3)),
            "top_artists_count": int(request.get("top_artists_count", 10)),
            "artist_pool_size": int(request.get("artist_pool_size", 20)),
            "max_tracks": int(request.get("max_tracks", 50)),
            "sonic_similar_limit": int(request.get("sonic_similar_limit", 15)),
            "sonic_similarity_distance": float(request.get("sonic_similarity_distance", 0.25)),
            "historical_ratio": float(request.get("historical_ratio", 0.3)),
            "target_library_key": str(library_key),
        }
        if request.get("expires_at"):
            config_json["expires_at"] = request.get("expires_at")
            config_json["expires_at_delete_playlist"] = request.get(
                "expires_at_delete_playlist", True
            )

        cmd = CommandConfig(
            command_name=command_name,
            display_name=display_name,
            description="Automated local discovery: top artists + sonically similar + lesser-played. Fresh each run. Plex only.",
            enabled=bool(request.get("enabled", True)),
            schedule_cron=schedule_cron if schedule_override else None,
            timeout_minutes=30,
            config_json=config_json,
            command_type="playlist_generator",
        )
        db.add(cmd)
        db.commit()
        db.refresh(cmd)

        command_executor._load_dynamic_local_discovery_commands()

        return {
            "message": "Local Discovery command created",
            "command_name": command_name,
        }
    except HTTPException:
        raise
    except Exception as e:
        get_commands_logger().error(f"Failed to create local discovery: {e}")
        db.rollback()
        raise HTTPException(status_code=500, detail="Failed to create local discovery") from None


@router.get("/top-tracks/exists")
async def top_tracks_exists(db: Annotated[Session, Depends(get_config_db)]):
    """Check if any top tracks command exists (for New Command UI)."""
    existing = (
        db.query(CommandConfig)
        .filter(CommandConfig.command_name.like("top_tracks_%"))
        .filter(CommandConfig.deleted_at.is_(None))
        .first()
    )
    return {"exists": existing is not None}


@router.post("/top-tracks/create")
async def create_top_tracks(request: dict, db: Annotated[Session, Depends(get_config_db)]):
    """Create a new Artist Mix generator command."""
    try:
        artists_raw = request.get("artists", [])
        if isinstance(artists_raw, str):
            artists_raw = [a.strip() for a in artists_raw.split("\n") if a.strip()]
        if not artists_raw:
            raise HTTPException(
                status_code=400, detail="artists is required (list or newline-separated)"
            )

        top_x = int(request.get("top_x", 5))
        top_x = max(1, min(20, top_x))
        source = str(request.get("source", "plex")).lower()
        if source not in ("plex", "lastfm"):
            source = "plex"
        target = str(request.get("target", "plex")).lower()
        if target not in ("plex", "jellyfin"):
            target = "plex"
        if target == "jellyfin":
            source = "lastfm"

        use_custom_playlist_name = bool(request.get("use_custom_playlist_name", False))
        custom_playlist_name = (request.get("custom_playlist_name") or "").strip()
        schedule_cron = (request.get("schedule_cron") or "").strip() or None
        schedule_override = bool(schedule_cron)
        enabled = bool(request.get("enabled", True))

        from commands.config_adapter import Config

        config = Config()
        library_key = None
        if target == "plex":
            from clients.client_plex import PlexClient

            pc = PlexClient(config)
            library_key = pc.get_resolved_library_key()
        elif target == "jellyfin":
            from clients.client_jellyfin import JellyfinClient

            jc = JellyfinClient(config)
            library_key = jc.get_resolved_library_key()

        if not library_key:
            raise HTTPException(
                status_code=400,
                detail="Could not resolve target library. Configure PLEX_LIBRARY_NAME or JELLYFIN_LIBRARY_NAME, or add a music library.",
            )

        existing = (
            db.query(CommandConfig).filter(CommandConfig.command_name.like("top_tracks_%")).all()
        )
        used_ids = set()
        for cmd in existing:
            try:
                used_ids.add(int(cmd.command_name.split("_")[-1]))
            except ValueError, IndexError:
                pass
        next_id = 1
        while next_id in used_ids:
            next_id += 1
        command_name = f"top_tracks_{next_id:05d}"

        config_json = {
            "artists": artists_raw,
            "top_x": top_x,
            "source": source,
            "target": target,
            "target_library_key": str(library_key),
            "use_custom_playlist_name": use_custom_playlist_name,
            "custom_playlist_name": custom_playlist_name,
        }
        if request.get("expires_at"):
            config_json["expires_at"] = request.get("expires_at")
            config_json["expires_at_delete_playlist"] = request.get(
                "expires_at_delete_playlist", True
            )

        cmd = CommandConfig(
            command_name=command_name,
            display_name="[Cmdarr] Artist Essentials",
            description="Generate playlist from artist list with top X tracks per artist.",
            enabled=enabled,
            schedule_cron=schedule_cron if schedule_override else None,
            timeout_minutes=30,
            config_json=config_json,
            command_type="playlist_generator",
        )
        db.add(cmd)
        db.commit()
        db.refresh(cmd)

        command_executor._load_dynamic_top_tracks_commands()

        return {"message": "Artist Essentials command created", "command_name": command_name}
    except HTTPException:
        raise
    except Exception as e:
        get_commands_logger().error(f"Failed to create top tracks: {e}")
        db.rollback()
        raise HTTPException(status_code=500, detail="Failed to create top tracks") from None


@router.get("/lfm-similar/exists")
async def lfm_similar_exists(db: Annotated[Session, Depends(get_config_db)]):
    """Check if any Last.fm Similar playlist command exists."""
    existing = (
        db.query(CommandConfig)
        .filter(CommandConfig.command_name.like("lfm_similar_%"))
        .filter(CommandConfig.deleted_at.is_(None))
        .first()
    )
    return {"exists": existing is not None}


@router.post("/lfm-similar/create")
async def create_lfm_similar(request: dict, db: Annotated[Session, Depends(get_config_db)]):
    """Create a Last.fm Similar Artists playlist generator command."""
    try:
        seeds_raw = request.get("seed_artists")
        if seeds_raw is None:
            seeds_raw = request.get("artists", [])
        if isinstance(seeds_raw, str):
            seeds_raw = [s.strip() for s in seeds_raw.split("\n") if s.strip()]
        if not seeds_raw:
            raise HTTPException(
                status_code=400,
                detail="seed_artists is required (list or newline-separated)",
            )

        similar_per_seed = int(request.get("similar_per_seed", 5))
        similar_per_seed = max(1, min(50, similar_per_seed))
        max_artists = int(request.get("max_artists", 25))
        max_artists = max(1, min(200, max_artists))
        include_seeds = bool(request.get("include_seeds", True))

        top_x = int(request.get("top_x", 5))
        top_x = max(1, min(20, top_x))
        target = str(request.get("target", "plex")).lower()
        if target not in ("plex", "jellyfin"):
            target = "plex"

        use_custom_playlist_name = bool(request.get("use_custom_playlist_name", False))
        custom_playlist_name = (request.get("custom_playlist_name") or "").strip()
        schedule_cron = (request.get("schedule_cron") or "").strip() or None
        schedule_override = bool(schedule_cron)
        enabled = bool(request.get("enabled", True))

        from commands.config_adapter import Config

        config = Config()
        library_key = None
        if target == "plex":
            from clients.client_plex import PlexClient

            pc = PlexClient(config)
            library_key = pc.get_resolved_library_key()
        elif target == "jellyfin":
            from clients.client_jellyfin import JellyfinClient

            jc = JellyfinClient(config)
            library_key = jc.get_resolved_library_key()

        if not library_key:
            raise HTTPException(
                status_code=400,
                detail="Could not resolve target library. Configure PLEX_LIBRARY_NAME or JELLYFIN_LIBRARY_NAME, or add a music library.",
            )

        existing = (
            db.query(CommandConfig).filter(CommandConfig.command_name.like("lfm_similar_%")).all()
        )
        used_ids = set()
        for cmd in existing:
            try:
                used_ids.add(int(cmd.command_name.split("_")[-1]))
            except ValueError, IndexError:
                pass
        next_id = 1
        while next_id in used_ids:
            next_id += 1
        command_name = f"lfm_similar_{next_id:05d}"

        config_json = {
            "seed_artists": seeds_raw,
            "similar_per_seed": similar_per_seed,
            "max_artists": max_artists,
            "include_seeds": include_seeds,
            "top_x": top_x,
            "source": "lastfm",
            "target": target,
            "target_library_key": str(library_key),
            "use_custom_playlist_name": use_custom_playlist_name,
            "custom_playlist_name": custom_playlist_name,
        }
        if request.get("expires_at"):
            config_json["expires_at"] = request.get("expires_at")
            config_json["expires_at_delete_playlist"] = request.get(
                "expires_at_delete_playlist", True
            )

        cmd = CommandConfig(
            command_name=command_name,
            display_name="[Cmdarr] Last.fm Similar",
            description=(
                "Generate playlist from seed artists expanded via Last.fm similar artists "
                "(top tracks per artist)."
            ),
            enabled=enabled,
            schedule_cron=schedule_cron if schedule_override else None,
            timeout_minutes=30,
            config_json=config_json,
            command_type="playlist_generator",
        )
        db.add(cmd)
        db.commit()
        db.refresh(cmd)

        command_executor._load_dynamic_lfm_similar_commands()

        return {"message": "Last.fm Similar command created", "command_name": command_name}
    except HTTPException:
        raise
    except Exception as e:
        get_commands_logger().error(f"Failed to create lfm_similar: {e}")
        db.rollback()
        raise HTTPException(
            status_code=500, detail="Failed to create Last.fm Similar command"
        ) from None


@router.get("/mood-playlist/moods")
async def mood_playlist_moods():
    """Get mood list from moodmap.json for mood playlist generator."""
    import json
    from pathlib import Path

    path = (
        Path(__file__).resolve().parent.parent.parent
        / "commands"
        / "daylist"
        / "assets"
        / "moodmap.json"
    )
    try:
        with open(path) as f:
            moodmap = json.load(f)
        return {"moods": sorted(moodmap.keys())}
    except Exception as e:
        get_commands_logger().error(f"Failed to load moodmap: {e}")
        return {"moods": []}


@router.get("/mood-playlist/exists")
async def mood_playlist_exists(db: Annotated[Session, Depends(get_config_db)]):
    """Check if any mood playlist command exists (for New Command UI)."""
    existing = (
        db.query(CommandConfig)
        .filter(CommandConfig.command_name.like("mood_playlist_%"))
        .filter(CommandConfig.deleted_at.is_(None))
        .first()
    )
    return {"exists": existing is not None}


@router.post("/mood-playlist/create")
async def create_mood_playlist(request: dict, db: Annotated[Session, Depends(get_config_db)]):
    """Create a new Mood Playlist generator command."""
    try:
        moods_raw = request.get("moods", [])
        if isinstance(moods_raw, str):
            moods_raw = [m.strip() for m in moods_raw.split(",") if m.strip()]
        moods = [m for m in moods_raw if m]
        if not moods:
            raise HTTPException(status_code=400, detail="moods is required (list of mood names)")

        use_custom = bool(request.get("use_custom_playlist_name", False))
        custom_name = (request.get("custom_playlist_name") or "").strip()
        from commands.playlist_generator_mood import _build_auto_playlist_suffix

        suffix = custom_name if (use_custom and custom_name) else _build_auto_playlist_suffix(moods)
        display_name = f"[Cmdarr] Mood: {suffix}"
        max_tracks = int(request.get("max_tracks", 50))
        max_tracks = max(1, min(200, max_tracks))
        exclude_last_run = bool(request.get("exclude_last_run", True))
        schedule_cron = (request.get("schedule_cron") or "").strip() or None
        schedule_override = bool(schedule_cron)
        enabled = bool(request.get("enabled", True))

        from commands.config_adapter import Config

        config = Config()
        from clients.client_plex import PlexClient

        pc = PlexClient(config)
        library_key = pc.get_resolved_library_key()
        if not library_key:
            raise HTTPException(
                status_code=400,
                detail="Could not resolve Plex library. Configure PLEX_LIBRARY_NAME or add a music library.",
            )

        existing = (
            db.query(CommandConfig).filter(CommandConfig.command_name.like("mood_playlist_%")).all()
        )
        used_ids = set()
        for cmd in existing:
            try:
                used_ids.add(int(cmd.command_name.split("_")[-1]))
            except ValueError, IndexError:
                pass
        next_id = 1
        while next_id in used_ids:
            next_id += 1
        command_name = f"mood_playlist_{next_id:05d}"

        limit_by_year = bool(request.get("limit_by_year", False))
        min_year = request.get("min_year")
        max_year = request.get("max_year")
        if limit_by_year:
            try:
                min_year = max(1800, min(2100, int(min_year))) if min_year is not None else None
            except TypeError, ValueError:
                min_year = None
            try:
                max_year = max(1800, min(2100, int(max_year))) if max_year is not None else None
            except TypeError, ValueError:
                max_year = None
        else:
            min_year = max_year = None

        config_json = {
            "moods": moods,
            "use_custom_playlist_name": use_custom,
            "custom_playlist_name": custom_name if use_custom else "",
            "max_tracks": max_tracks,
            "exclude_last_run": exclude_last_run,
            "limit_by_year": limit_by_year,
            "min_year": min_year,
            "max_year": max_year,
            "target_library_key": str(library_key),
        }
        if request.get("expires_at"):
            config_json["expires_at"] = request.get("expires_at")
            config_json["expires_at_delete_playlist"] = request.get(
                "expires_at_delete_playlist", True
            )

        cmd = CommandConfig(
            command_name=command_name,
            display_name=display_name,
            description="Generate playlist from selected Plex moods with freshness (exclude last run, date-seeded sampling).",
            enabled=enabled,
            schedule_cron=schedule_cron if schedule_override else None,
            timeout_minutes=30,
            config_json=config_json,
            command_type="playlist_generator",
        )
        db.add(cmd)
        db.commit()
        db.refresh(cmd)

        command_executor._load_dynamic_mood_playlist_commands()

        return {"message": "Mood Playlist command created", "command_name": command_name}
    except HTTPException:
        raise
    except Exception as e:
        get_commands_logger().error(f"Failed to create mood playlist: {e}")
        db.rollback()
        raise HTTPException(status_code=500, detail="Failed to create mood playlist") from None


def _normalize_xmplaylist_station_row(s: dict) -> dict | None:
    """Map raw API station object to UI row (deeplink, label, sort key)."""
    name = (s.get("name") or s.get("title") or "").strip()
    raw_link = (s.get("deeplink") or s.get("slug") or "").strip()
    deeplink = raw_link.lower().replace(" ", "") if raw_link else ""
    if not deeplink and s.get("id") is not None:
        deeplink = str(s.get("id")).strip().lower().replace(" ", "")
    if not deeplink or not name:
        return None
    num_raw = s.get("number")
    if num_raw is None:
        num_raw = s.get("channel")
    try:
        num = int(num_raw)
    except TypeError, ValueError:
        num = None
    label = f"Ch. {num} - {name}" if num is not None else f"{name} ({deeplink})"
    return {
        "name": name,
        "deeplink": deeplink,
        "number": num,
        "label": label,
    }


@router.get("/xmplaylist/stations")
async def xmplaylist_stations():
    """List SiriusXM stations from xmplaylist.com (sorted by channel number)."""
    try:
        from clients.client_xmplaylist import XmplaylistClient
        from commands.config_adapter import Config

        config = Config()
        async with XmplaylistClient(config) as client:
            raw = await client.list_stations()
        rows: list[dict] = []
        for s in raw:
            if not isinstance(s, dict):
                continue
            row = _normalize_xmplaylist_station_row(s)
            if row:
                rows.append(row)
        rows.sort(
            key=lambda r: (
                r["number"] if r["number"] is not None else 10**9,
                r["name"].lower(),
            )
        )
        return {"stations": rows}
    except Exception as e:
        get_commands_logger().error(f"Failed to fetch xmplaylist stations: {e}")
        raise HTTPException(
            status_code=502,
            detail="Could not load stations from xmplaylist.com (network or API error).",
        ) from None


@router.post("/xmplaylist/create")
async def create_xmplaylist(request: dict, db: Annotated[Session, Depends(get_config_db)]):
    """Create XM Playlist (xmplaylist.com) generator command."""
    try:
        from clients.client_xmplaylist import MOST_HEARD_DAYS
        from commands.config_adapter import Config
        from commands.playlist_generator_xmplaylist import _build_xmplaylist_display_name
        from database.config_models import CommandConfig

        deeplink = (request.get("station_deeplink") or "").strip().lower().replace(" ", "")
        if not deeplink:
            raise HTTPException(status_code=400, detail="station_deeplink is required")

        station_name = (request.get("station_display_name") or deeplink).strip()
        playlist_kind = str(request.get("playlist_kind", "newest")).lower()
        if playlist_kind not in ("newest", "most_heard"):
            playlist_kind = "newest"

        most_heard_days = int(request.get("most_heard_days", 30))
        if most_heard_days not in MOST_HEARD_DAYS:
            most_heard_days = 30

        max_tracks = int(request.get("max_tracks", 50))
        max_tracks = max(1, min(50, max_tracks))

        target = str(request.get("target", "plex")).lower()
        if target not in ("plex", "jellyfin"):
            target = "plex"

        config = Config()
        library_key = None
        if target == "plex":
            from clients.client_plex import PlexClient

            library_key = PlexClient(config).get_resolved_library_key()
        else:
            from clients.client_jellyfin import JellyfinClient

            library_key = JellyfinClient(config).get_resolved_library_key()

        if not library_key:
            raise HTTPException(
                status_code=400,
                detail="Could not resolve target library. Configure PLEX_LIBRARY_NAME or JELLYFIN_LIBRARY_NAME.",
            )

        existing = (
            db.query(CommandConfig).filter(CommandConfig.command_name.like("xmplaylist_%")).all()
        )
        used_ids: set[int] = set()
        for cmd in existing:
            try:
                used_ids.add(int(cmd.command_name.split("_")[-1]))
            except ValueError, IndexError:
                pass
        next_id = 1
        while next_id in used_ids:
            next_id += 1
        command_name = f"xmplaylist_{next_id:05d}"

        plex_account = request.get("plex_playlist_account_id")
        if plex_account is not None:
            plex_account = str(plex_account).strip() or None

        plex_account_ids = request.get("plex_account_ids") or []
        if not isinstance(plex_account_ids, list):
            plex_account_ids = []
        plex_account_ids = [str(a).strip() for a in plex_account_ids if str(a).strip()]

        cfg_for_title: dict = {
            "station_display_name": station_name,
            "station_deeplink": deeplink,
            "playlist_kind": playlist_kind,
            "most_heard_days": most_heard_days,
            "target": target,
        }
        if target == "plex" and plex_account_ids:
            cfg_for_title["plex_account_ids"] = plex_account_ids
        elif plex_account:
            cfg_for_title["plex_playlist_account_id"] = plex_account

        display_name = _build_xmplaylist_display_name(cfg_for_title)

        schedule_cron = (request.get("schedule_cron") or "").strip() or None
        schedule_override = bool(schedule_cron)
        enabled = bool(request.get("enabled", True))

        config_json: dict = {
            "command_name": command_name,
            "station_deeplink": deeplink,
            "station_display_name": station_name,
            "playlist_kind": playlist_kind,
            "most_heard_days": most_heard_days,
            "max_tracks": max_tracks,
            "target": target,
            "target_library_key": str(library_key),
            "enable_artist_discovery": bool(request.get("enable_artist_discovery", False)),
            "artist_discovery_max_per_run": int(request.get("artist_discovery_max_per_run", 2)),
        }
        if target == "plex" and plex_account_ids:
            config_json["plex_account_ids"] = plex_account_ids
        elif plex_account:
            config_json["plex_playlist_account_id"] = plex_account

        if request.get("expires_at"):
            config_json["expires_at"] = request.get("expires_at")
            config_json["expires_at_delete_playlist"] = request.get(
                "expires_at_delete_playlist", True
            )

        cmd = CommandConfig(
            command_name=command_name,
            display_name=display_name,
            description="SiriusXM station playlist via xmplaylist.com (newest or most played).",
            enabled=enabled,
            schedule_cron=schedule_cron if schedule_override else None,
            timeout_minutes=30,
            config_json=config_json,
            command_type="playlist_generator",
        )
        db.add(cmd)
        db.commit()
        db.refresh(cmd)

        command_executor._load_dynamic_xmplaylist_commands()

        return {"message": "XM Playlist command created", "command_name": command_name}
    except HTTPException:
        raise
    except Exception as e:
        get_commands_logger().error(f"Failed to create xmplaylist command: {e}")
        db.rollback()
        raise HTTPException(status_code=500, detail="Failed to create xmplaylist command") from None


@router.post("/playlist-sync/create")
async def create_playlist_sync(request: dict, db: Annotated[Session, Depends(get_config_db)]):
    """Create a new playlist sync command"""
    try:
        # Get playlist type from request
        playlist_type = request.get("playlist_type", "other")  # 'listenbrainz' or 'other'

        if playlist_type == "listenbrainz":
            return await create_listenbrainz_playlist_sync(request, db)
        else:
            return await create_external_playlist_sync(request, db)

    except HTTPException:
        raise
    except Exception as e:
        get_commands_logger().error(f"Failed to create playlist sync: {e}")
        raise HTTPException(status_code=500, detail="Failed to create playlist sync")


async def create_external_playlist_sync(request: dict, db: Session = Depends(get_config_db)):
    """Create a new external playlist sync command (Spotify, Deezer, etc.)"""
    try:
        from clients.client_deezer import DeezerClient
        from clients.client_spotify import SpotifyClient
        from commands.config_adapter import Config
        from database.config_models import CommandConfig
        from utils.playlist_parser import parse_playlist_url

        # Validate request
        playlist_url = request.get("playlist_url")
        target = request.get("target")
        sync_mode = request.get("sync_mode", "full")
        schedule_cron = request.get("schedule_cron")  # None = use global default
        schedule_override = bool(schedule_cron and schedule_cron.strip())
        enabled = request.get("enabled", True)

        if not playlist_url:
            raise HTTPException(status_code=400, detail="playlist_url is required")
        if not target:
            raise HTTPException(status_code=400, detail="target is required")
        if target not in ["plex", "jellyfin"]:
            raise HTTPException(status_code=400, detail="target must be 'plex' or 'jellyfin'")

        # Validate URL and get metadata
        parsed = parse_playlist_url(playlist_url)
        if not parsed["valid"]:
            raise HTTPException(status_code=400, detail=parsed["error"])

        source = parsed["source"]
        config = Config()

        if source == "spotify":
            spotify_client = SpotifyClient(config)
            try:
                metadata = await spotify_client.get_playlist_info(playlist_url)

                get_commands_logger().info(f"Spotify metadata response: {metadata}")

                if not metadata or not isinstance(metadata, dict):
                    raise HTTPException(
                        status_code=400, detail="Invalid metadata response from Spotify"
                    )

                if not metadata.get("success"):
                    raise HTTPException(
                        status_code=400, detail="Failed to fetch playlist metadata from Spotify"
                    )

                playlist_name = metadata.get("name")
                if not playlist_name:
                    raise HTTPException(
                        status_code=400, detail="Playlist name not found in metadata"
                    )
            finally:
                await spotify_client.close()
        elif source == "deezer":
            deezer_client = DeezerClient(config)
            try:
                metadata = await deezer_client.get_playlist_info(playlist_url)

                get_commands_logger().info(f"Deezer metadata response: {metadata}")

                if not metadata or not isinstance(metadata, dict):
                    raise HTTPException(
                        status_code=400, detail="Invalid metadata response from Deezer"
                    )

                if not metadata.get("success"):
                    raise HTTPException(
                        status_code=400, detail="Failed to fetch playlist metadata from Deezer"
                    )

                playlist_name = metadata.get("name")
                if not playlist_name:
                    raise HTTPException(
                        status_code=400, detail="Playlist name not found in metadata"
                    )
            finally:
                await deezer_client.close()
        else:
            raise HTTPException(status_code=400, detail=f"Source {source} not yet supported")

        # Generate unique command ID (never reuse IDs for historical consistency)
        try:
            existing_commands = (
                db.query(CommandConfig)
                .filter(CommandConfig.command_name.like("playlist_sync_%"))
                .all()
            )

            # Find all used IDs from existing commands
            used_ids = set()
            for cmd in existing_commands:
                try:
                    cmd_id = int(cmd.command_name.split("_")[-1])
                    used_ids.add(cmd_id)
                except ValueError, IndexError:
                    continue

            # Also check execution history for any orphaned IDs
            from database.config_models import CommandExecution

            orphaned_executions = (
                db.query(CommandExecution)
                .filter(CommandExecution.command_name.like("playlist_sync_%"))
                .all()
            )

            for execution in orphaned_executions:
                try:
                    cmd_id = int(execution.command_name.split("_")[-1])
                    used_ids.add(cmd_id)
                except ValueError, IndexError:
                    continue

            # Find the next available ID
            next_id = 1
            while next_id in used_ids:
                next_id += 1

            command_name = f"playlist_sync_{next_id:05d}"

        except Exception as e:
            get_commands_logger().error(f"Failed to generate unique command ID: {e}")
            raise HTTPException(status_code=500, detail="Failed to generate unique command ID")

        # Multi-user Plex: build display name with [USER] format
        plex_account_ids = request.get("plex_account_ids") or []
        if target == "plex" and isinstance(plex_account_ids, list) and len(plex_account_ids) > 0:
            from clients.client_plex import PlexClient

            plex = PlexClient(config)
            accounts = plex.get_accounts()
            names = []
            for aid in plex_account_ids:
                acc = next((a for a in accounts if str(a.get("id", "")) == str(aid)), None)
                names.append(acc["name"] if acc else str(aid))
            user_bracket = f" [{', '.join(names)}] "
        else:
            user_bracket = " "
        display_name = f"[{source.title()}]{user_bracket}{playlist_name} → {target.title()}"

        # Create command config
        try:
            enable_artist_discovery = request.get("enable_artist_discovery", False)
            config_json = {
                "source": source,
                "unique_id": f"{next_id:05d}",
                "playlist_url": playlist_url,
                "playlist_name": playlist_name,
                "target": target,
                "sync_mode": sync_mode,
                "enable_artist_discovery": enable_artist_discovery,
                "artist_discovery_max_per_run": request.get("artist_discovery_max_per_run", 2)
                if enable_artist_discovery
                else 0,
            }
            if target == "plex" and isinstance(plex_account_ids, list) and plex_account_ids:
                config_json["plex_account_ids"] = [str(aid) for aid in plex_account_ids]
            if request.get("expires_at"):
                config_json["expires_at"] = request.get("expires_at")
                config_json["expires_at_delete_playlist"] = request.get(
                    "expires_at_delete_playlist", True
                )

            command = CommandConfig(
                command_name=command_name,
                display_name=display_name,
                description=f"Sync {source.title()} playlist '{playlist_name}' to {target.title()}",
                enabled=enabled,
                schedule_cron=schedule_cron.strip()
                if schedule_override and schedule_cron
                else None,
                timeout_minutes=30,
                command_type="playlist_sync",
                config_json=config_json,
            )

            db.add(command)
            db.commit()

            # Reload command executor to pick up new command
            from services.command_executor import command_executor

            command_executor._ensure_initialized()  # Ensure logger is initialized
            command_executor._load_dynamic_playlist_sync_commands()

        except Exception as e:
            get_commands_logger().error(f"Failed to create command in database: {e}")
            import traceback

            get_commands_logger().error(f"Database creation traceback: {traceback.format_exc()}")
            db.rollback()
            raise HTTPException(status_code=500, detail="Failed to create command in database")

        # Check for cache warnings
        warnings = []
        cache_enabled_key = f"LIBRARY_CACHE_{target.upper()}_ENABLED"
        if not config.get(cache_enabled_key, False):
            get_commands_logger().warning(
                f"Creating playlist sync targeting {target} but library cache is disabled. "
                "This may cause slow performance. Consider enabling library cache."
            )
            warnings.append(
                f"Library cache for {target.title()} is disabled. "
                "Performance may be slow. Enable cache in configuration for better performance."
            )

        response = {
            "success": True,
            "command_name": command_name,
            "display_name": display_name,
            "message": "Playlist sync command created successfully",
        }

        if warnings:
            response["warnings"] = warnings

        return response

    except HTTPException:
        raise
    except Exception as e:
        get_commands_logger().error(f"Failed to create external playlist sync: {e}")
        raise HTTPException(status_code=500, detail="Failed to create external playlist sync")


async def create_listenbrainz_playlist_sync(request: dict, db: Session = Depends(get_config_db)):
    """Create a new ListenBrainz playlist sync command"""
    try:
        from commands.config_adapter import Config
        from database.config_models import CommandConfig

        # Validate request
        playlist_types = request.get("playlist_types", [])
        target = request.get("target")
        sync_mode = request.get("sync_mode", "full")
        schedule_cron = request.get("schedule_cron")
        schedule_override = bool(schedule_cron and schedule_cron.strip())
        enabled = request.get("enabled", True)

        # Retention settings
        weekly_exploration_keep = request.get("weekly_exploration_keep", 2)
        weekly_jams_keep = request.get("weekly_jams_keep", 2)
        daily_jams_keep = request.get("daily_jams_keep", 3)
        cleanup_enabled = request.get("cleanup_enabled", True)

        if not playlist_types:
            raise HTTPException(status_code=400, detail="playlist_types is required")
        if not target:
            raise HTTPException(status_code=400, detail="target is required")
        if target not in ["plex", "jellyfin"]:
            raise HTTPException(status_code=400, detail="target must be 'plex' or 'jellyfin'")

        # Validate playlist types
        valid_types = ["weekly_exploration", "weekly_jams", "daily_jams"]
        for playlist_type in playlist_types:
            if playlist_type not in valid_types:
                raise HTTPException(
                    status_code=400, detail=f"Invalid playlist type: {playlist_type}"
                )

        # Create config instance
        config = Config()

        # Generate unique command ID (never reuse IDs for historical consistency)
        try:
            existing_commands = (
                db.query(CommandConfig)
                .filter(CommandConfig.command_name.like("playlist_sync_%"))
                .all()
            )

            # Find all used IDs from existing commands
            used_ids = set()
            for cmd in existing_commands:
                try:
                    cmd_id = int(cmd.command_name.split("_")[-1])
                    used_ids.add(cmd_id)
                except ValueError, IndexError:
                    continue

            # Also check execution history for any orphaned IDs
            from database.config_models import CommandExecution

            orphaned_executions = (
                db.query(CommandExecution)
                .filter(CommandExecution.command_name.like("playlist_sync_%"))
                .all()
            )

            for execution in orphaned_executions:
                try:
                    cmd_id = int(execution.command_name.split("_")[-1])
                    used_ids.add(cmd_id)
                except ValueError, IndexError:
                    continue

            # Find the next available ID
            next_id = 1
            while next_id in used_ids:
                next_id += 1

            command_name = f"playlist_sync_{next_id:05d}"

        except Exception as e:
            get_commands_logger().error(f"Failed to generate unique command ID: {e}")
            raise HTTPException(status_code=500, detail="Failed to generate unique command ID")

        # Generate display name
        if len(playlist_types) == 1:
            playlist_name = playlist_types[0].replace("_", " ").title()
            display_name = f"[ListenBrainz] {playlist_name} → {target.title()}"
        elif len(playlist_types) == len(valid_types):
            display_name = f"[ListenBrainz] All Curated Playlists → {target.title()}"
        else:
            playlist_names = [pt.replace("_", " ").title() for pt in playlist_types]
            display_name = f"[ListenBrainz] {', '.join(playlist_names)} → {target.title()}"

        # Create command config
        try:
            enable_artist_discovery = request.get("enable_artist_discovery", False)
            config_json = {
                "source": "listenbrainz",
                "unique_id": f"{next_id:05d}",
                "playlist_types": playlist_types,
                "target": target,
                "sync_mode": sync_mode,
                "weekly_exploration_keep": weekly_exploration_keep,
                "weekly_jams_keep": weekly_jams_keep,
                "daily_jams_keep": daily_jams_keep,
                "cleanup_enabled": cleanup_enabled,
                "enable_artist_discovery": enable_artist_discovery,
                "artist_discovery_max_per_run": request.get("artist_discovery_max_per_run", 2)
                if enable_artist_discovery
                else 0,
            }
            if request.get("expires_at"):
                config_json["expires_at"] = request.get("expires_at")
                config_json["expires_at_delete_playlist"] = request.get(
                    "expires_at_delete_playlist", True
                )

            command = CommandConfig(
                command_name=command_name,
                display_name=display_name,
                description=f"Sync ListenBrainz curated playlists to {target.title()}",
                enabled=enabled,
                schedule_cron=schedule_cron.strip()
                if schedule_override and schedule_cron
                else None,
                timeout_minutes=30,
                command_type="playlist_sync",
                config_json=config_json,
            )

            db.add(command)
            db.commit()

            # Reload command executor to pick up new command
            from services.command_executor import command_executor

            command_executor._ensure_initialized()  # Ensure logger is initialized
            command_executor._load_dynamic_playlist_sync_commands()

        except Exception as e:
            get_commands_logger().error(f"Failed to create command in database: {e}")
            import traceback

            get_commands_logger().error(f"Database creation traceback: {traceback.format_exc()}")
            db.rollback()
            raise HTTPException(status_code=500, detail="Failed to create command in database")

        # Check for cache warnings
        warnings = []
        cache_enabled_key = f"LIBRARY_CACHE_{target.upper()}_ENABLED"
        if not config.get(cache_enabled_key, False):
            get_commands_logger().warning(
                f"Creating ListenBrainz playlist sync targeting {target} but library cache is disabled. "
                "This may cause slow performance. Consider enabling library cache."
            )
            warnings.append(
                f"Library cache for {target.title()} is disabled. "
                "Performance may be slow. Enable cache in configuration for better performance."
            )

        response = {
            "success": True,
            "command_name": command_name,
            "display_name": display_name,
            "message": "ListenBrainz playlist sync command created successfully",
        }

        if warnings:
            response["warnings"] = warnings

        return response

    except HTTPException:
        raise
    except Exception as e:
        get_commands_logger().error(f"Failed to create ListenBrainz playlist sync: {e}")
        raise HTTPException(status_code=500, detail="Failed to create ListenBrainz playlist sync")


@router.delete("/{command_name}")
async def delete_command(command_name: str, db: Annotated[Session, Depends(get_config_db)]):
    """Delete a command (enhanced to support playlist_sync_* commands)"""
    try:
        # Validate command_name parameter
        if not command_name:
            raise HTTPException(status_code=400, detail="Command name is required")

        command = (
            db.query(CommandConfig)
            .filter(
                CommandConfig.command_name == command_name,
                CommandConfig.deleted_at.is_(None),
            )
            .first()
        )
        if not command:
            raise HTTPException(status_code=404, detail="Command not found")

        # Check if it's a playlist sync command
        if command_name.startswith("playlist_sync_"):
            # Allow deletion of dynamic playlist sync commands
            pass
        elif command_name in [
            "discovery_lastfm",
            "library_cache_builder",
            "new_releases_discovery",
            "playlist_sync_discovery_maintenance",
        ]:
            raise HTTPException(status_code=400, detail="Cannot delete built-in commands")

        # Soft delete: keep for 7 days so execution history retains display_name
        command.deleted_at = datetime.utcnow()
        command.enabled = False
        db.commit()

        # Reload command executor to remove deleted command
        from services.command_executor import command_executor

        command_executor._ensure_initialized()  # Ensure command executor is initialized
        if command_name in command_executor.command_classes:
            del command_executor.command_classes[command_name]

        return {"message": f"Command {command_name} deleted successfully"}

    except HTTPException:
        raise
    except Exception as e:
        get_commands_logger().error(f"Failed to delete command {command_name}: {e}")
        raise HTTPException(status_code=500, detail="Failed to delete command")


@router.get("/new-releases-sources")
async def get_new_releases_sources():
    """Get available New Releases Discovery sources and their configuration status"""
    try:
        from commands.config_adapter import Config

        config = Config()

        sources = [
            {
                "id": "deezer",
                "name": "Deezer",
                "configured": True,
                "config_help": "No account required—uses public data",
            },
            {
                "id": "spotify",
                "name": "Spotify",
                "configured": bool(config.SPOTIFY_CLIENT_ID and config.SPOTIFY_CLIENT_SECRET),
                "config_help": "Requires credentials in Config → Music Sources",
            },
        ]

        return {"sources": sources}

    except Exception as e:
        get_commands_logger().error(f"Failed to get new releases sources: {e}")
        raise HTTPException(status_code=500, detail="Failed to get new releases sources")


@router.get("/playlist-sync/sources")
async def get_playlist_sync_sources():
    """Get available playlist sync sources and their configuration status"""
    try:
        from commands.config_adapter import Config

        config = Config()

        sources = [
            {
                "id": "spotify",
                "name": "Spotify",
                "requires_url": True,
                "example_url": "https://open.spotify.com/playlist/4NDXWHwYWjFmgVPkNy4YlF",
                "configured": bool(config.SPOTIFY_CLIENT_ID and config.SPOTIFY_CLIENT_SECRET),
                "config_help": "For public playlists; optional—scraper used when not configured",
            },
            {
                "id": "deezer",
                "name": "Deezer",
                "requires_url": True,
                "example_url": "https://www.deezer.com/en/playlist/1479458365",
                "configured": True,  # Deezer doesn't require authentication for public playlists
                "config_help": "Deezer public playlists work without configuration",
            },
        ]

        return {"sources": sources}

    except Exception as e:
        get_commands_logger().error(f"Failed to get playlist sync sources: {e}")
        raise HTTPException(status_code=500, detail="Failed to get playlist sync sources")
