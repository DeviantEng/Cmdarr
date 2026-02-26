#!/usr/bin/env python3
"""
Commands API endpoints
"""

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, Request
from sqlalchemy.orm import Session
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field
from datetime import datetime, timedelta

from database.database import get_config_db
from database.config_models import CommandConfig, CommandExecution
from services.command_executor import command_executor
from utils.logger import get_logger

router = APIRouter()
# Lazy-load logger to avoid initialization issues
def get_commands_logger():
    return get_logger('cmdarr.api.commands')


def utc_datetime_serializer(dt: Optional[datetime]) -> Optional[str]:
    """Serialize UTC datetime with Z suffix for proper JavaScript parsing"""
    if dt is None:
        return None
    return dt.isoformat() + 'Z'


def _get_next_run_for_command(command: CommandConfig) -> Optional[datetime]:
    """Calculate next run time for command using cron (global or per-command override)."""
    from services.scheduler import calculate_next_run_cron
    from utils.timezone import get_scheduler_timezone
    tz = get_scheduler_timezone()
    return calculate_next_run_cron(command, tz)


class CommandUpdateRequest(BaseModel):
    """Request model for updating command configuration"""
    enabled: Optional[bool] = None
    schedule_cron: Optional[str] = None
    schedule_override: Optional[bool] = None  # True = use schedule_cron, False = use global
    timeout_minutes: Optional[int] = None
    config_json: Optional[Dict[str, Any]] = None


class CommandExecutionRequest(BaseModel):
    """Request model for executing a command"""
    triggered_by: str = "api"  # 'api', 'manual', 'scheduler'


class CommandConfigResponse(BaseModel):
    """Response model for command configuration"""
    id: int
    command_name: str
    display_name: str
    description: Optional[str]
    enabled: bool
    schedule_cron: Optional[str]
    schedule_override: Optional[bool]  # True when using per-command cron
    timeout_minutes: Optional[int]
    config_json: Optional[Dict[str, Any]]
    command_type: Optional[str]
    last_run: Optional[str]
    last_success: Optional[bool]
    last_duration: Optional[float]
    last_error: Optional[str]
    next_run: Optional[str]
    created_at: str
    updated_at: str


def command_to_response(command: CommandConfig) -> CommandConfigResponse:
    """Convert CommandConfig to CommandConfigResponse with next_run calculation"""
    command_dict = command.__dict__.copy()
    next_run = _get_next_run_for_command(command)
    command_dict['schedule_override'] = bool(command.schedule_cron and command.schedule_cron.strip())
    command_dict['last_run'] = utc_datetime_serializer(command.last_run)
    command_dict['next_run'] = utc_datetime_serializer(next_run)
    command_dict['created_at'] = utc_datetime_serializer(command.created_at)
    command_dict['updated_at'] = utc_datetime_serializer(command.updated_at)
    return CommandConfigResponse(**command_dict)


class CommandExecutionResponse(BaseModel):
    """Response model for command execution"""
    id: int
    command_name: str
    started_at: str
    completed_at: Optional[str]
    success: Optional[bool]
    status: str
    duration: Optional[float]
    error_message: Optional[str]
    result_data: Optional[Dict[str, Any]]
    triggered_by: str
    is_running: bool
    target: Optional[str] = None


@router.get("/", response_model=List[CommandConfigResponse])
async def get_all_commands(db: Session = Depends(get_config_db)):
    """Get all command configurations (excluding helper commands)"""
    try:
        commands = db.query(CommandConfig).all()
        
        # Filter out helper commands
        visible_commands = []
        helper_commands = {'library_cache_builder'}  # Known helper commands
        
        for command in commands:
            if command.command_name in helper_commands:
                continue  # Skip helper commands
            
            visible_commands.append(command)
        
        return [command_to_response(command) for command in visible_commands]
    except Exception as e:
        get_commands_logger().error(f"Failed to get commands: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve commands")


@router.get("/{command_name}", response_model=CommandConfigResponse)
async def get_command(command_name: str, db: Session = Depends(get_config_db)):
    """Get a specific command configuration"""
    try:
        command = db.query(CommandConfig).filter(CommandConfig.command_name == command_name).first()
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
    command_name: str, 
    request: CommandUpdateRequest, 
    db: Session = Depends(get_config_db)
):
    """Update a command configuration"""
    try:
        command = db.query(CommandConfig).filter(CommandConfig.command_name == command_name).first()
        if not command:
            raise HTTPException(status_code=404, detail="Command not found")
        
        # Track if enabled status or schedule changed
        enabled_changed = request.enabled is not None and request.enabled != command.enabled
        schedule_changed = (
            request.schedule_cron is not None and request.schedule_cron != (command.schedule_cron or '')
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
            # Validate Spotify credentials when switching NRD to Spotify source
            if command_name == 'new_releases_discovery':
                src = (request.config_json.get('new_releases_source') or 'deezer').strip().lower()
                if src == 'spotify':
                    from commands.config_adapter import ConfigAdapter
                    config = ConfigAdapter()
                    if not config.SPOTIFY_CLIENT_ID or not config.SPOTIFY_CLIENT_SECRET:
                        raise HTTPException(
                            status_code=400,
                            detail="Spotify credentials must be set in Config → Music Sources before using Spotify as the release source.",
                        )
            command.config_json = request.config_json
        
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
                get_commands_logger().warning(f"Failed to notify scheduler of command {command_name} change: {e}")
        
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
    db: Session = Depends(get_config_db)
):
    """Execute a command"""
    try:
        # Check if command exists and is enabled
        command = db.query(CommandConfig).filter(CommandConfig.command_name == command_name).first()
        if not command:
            raise HTTPException(status_code=404, detail="Command not found")
        
        if not command.enabled:
            raise HTTPException(status_code=400, detail="Command is disabled")
        
        # Execute command using command executor
        get_commands_logger().info(f"API: Executing command {command_name} with triggered_by='{request.triggered_by}'")
        result = await command_executor.execute_command(command_name, None, request.triggered_by)
        
        if result['success']:
            # Use display_name for user-facing message
            display_name = command.display_name or command_name
            msg = result['message']
            if 'started successfully' in msg:
                msg = f'Command "{display_name}" started'
            elif 'queued' in msg:
                msg = f'Command "{display_name}" queued (will run when a slot is available)'
            return {
                "message": msg,
                "execution_id": result['execution_id']
            }
        else:
            raise HTTPException(status_code=400, detail=result['error'])
            
    except HTTPException:
        raise
    except Exception as e:
        get_commands_logger().error(f"Failed to execute command {command_name}: {e}")
        raise HTTPException(status_code=500, detail="Failed to execute command")


@router.get("/{command_name}/executions", response_model=List[CommandExecutionResponse])
async def get_command_executions(
    command_name: str, 
    limit: int = 50,
    db: Session = Depends(get_config_db)
):
    """Get execution history for a command"""
    try:
        executions = db.query(CommandExecution)\
            .filter(CommandExecution.command_name == command_name)\
            .order_by(CommandExecution.started_at.desc())\
            .limit(limit)\
            .all()
        
        result = []
        for execution in executions:
            # Get command configuration to extract target information
            command_config = db.query(CommandConfig).filter(
                CommandConfig.command_name == execution.command_name
            ).first()
            
            execution_dict = {
                'id': execution.id,
                'command_name': execution.command_name,
                'started_at': utc_datetime_serializer(execution.started_at),
                'completed_at': utc_datetime_serializer(execution.completed_at),
                'success': execution.success,
                'status': execution.status,
                'duration': execution.duration,
                'error_message': execution.error_message,
                'result_data': execution.result_data,
                'triggered_by': execution.triggered_by,
                'is_running': execution.is_running,
                'target': command_config.config_json.get('target', 'unknown') if command_config and command_config.config_json else 'unknown'
            }
            result.append(CommandExecutionResponse(**execution_dict))
        return result
    except Exception as e:
        get_commands_logger().error(f"Failed to get executions for command {command_name}: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve command executions")


@router.get("/{command_name}/status")
async def get_command_status(command_name: str, db: Session = Depends(get_config_db)):
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
            "is_running": status.get('is_running', False),
            "last_execution": status.get('last_execution')
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
async def kill_execution(execution_id: int, db: Session = Depends(get_config_db)):
    """Kill a running command execution"""
    try:
        # Get the execution
        execution = db.query(CommandExecution).filter(CommandExecution.id == execution_id).first()
        if not execution:
            raise HTTPException(status_code=404, detail="Execution not found")
        
        # Check if it's actually running
        if execution.status != 'running':
            raise HTTPException(status_code=400, detail=f"Execution is not running (status: {execution.status})")
        
        # Update the execution status to cancelled
        execution.status = 'cancelled'
        execution.completed_at = datetime.utcnow()
        execution.success = False
        execution.error_message = "Execution cancelled by user"
        
        # Calculate duration
        if execution.started_at:
            execution.duration = (execution.completed_at - execution.started_at).total_seconds()
        
        # Update command's last_run so scheduler doesn't immediately re-queue (e.g. library cache rebuild)
        command_config = db.query(CommandConfig).filter(
            CommandConfig.command_name == execution.command_name
        ).first()
        if command_config:
            command_config.last_run = datetime.utcnow()
        
        db.commit()
        
        # Try to kill the actual process if it's running
        try:
            from services.command_executor import command_executor
            command_executor.kill_execution(execution_id)
        except Exception as e:
            get_commands_logger().warning(f"Failed to kill process for execution {execution_id}: {e}")
        
        get_commands_logger().info(f"Execution {execution_id} cancelled successfully")
        return {"message": f"Execution {execution_id} cancelled successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        get_commands_logger().error(f"Failed to kill execution {execution_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to kill execution")


@router.delete("/executions/{execution_id}")
async def delete_execution(execution_id: int, db: Session = Depends(get_config_db)):
    """Delete a command execution from history"""
    try:
        # Get the execution
        execution = db.query(CommandExecution).filter(CommandExecution.id == execution_id).first()
        if not execution:
            raise HTTPException(status_code=404, detail="Execution not found")
        
        # Don't allow deleting running executions
        if execution.status == 'running':
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
        from database.database import get_database_manager
        from database.config_models import CommandExecution
        
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
    command_name: Optional[str] = None,
    keep_count: Optional[int] = None,
    db: Session = Depends(get_config_db)
):
    """Clean up old command executions, keeping only the most recent ones"""
    try:
        # Get retention count from config if not provided
        if keep_count is None:
            from services.config_service import config_service
            keep_count = config_service.get_int('COMMAND_CLEANUP_RETENTION', 50)
        
        # Build query
        query = db.query(CommandExecution)
        if command_name:
            query = query.filter(CommandExecution.command_name == command_name)
        
        # Get total count
        total_count = query.count()
        
        if total_count <= keep_count:
            return {"message": f"No cleanup needed. {total_count} executions found, keeping {keep_count}"}
        
        # Get executions to delete (oldest ones beyond keep_count)
        executions_to_delete = query.order_by(CommandExecution.started_at.desc()).offset(keep_count).all()
        
        # Delete them
        for execution in executions_to_delete:
            db.delete(execution)
        
        deleted_count = len(executions_to_delete)
        db.commit()
        
        get_commands_logger().info(f"Cleaned up {deleted_count} old executions, kept {keep_count}")
        return {
            "message": f"Cleaned up {deleted_count} old executions, kept {keep_count}",
            "deleted_count": deleted_count,
            "kept_count": keep_count
        }
        
    except Exception as e:
        get_commands_logger().error(f"Failed to cleanup executions: {e}")
        raise HTTPException(status_code=500, detail="Failed to cleanup executions")


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
            "queue_size": queue_status['queue_size'],
            "currently_running": queue_status['currently_running']
        }
    except Exception as e:
        get_commands_logger().error(f"Failed to get scheduler status: {e}")
        raise HTTPException(status_code=500, detail="Failed to get scheduler status")


@router.post("/library_cache_builder/refresh")
async def execute_cache_builder(request: Request):
    """Execute library cache builder command manually"""
    try:
        from commands.library_cache_builder import LibraryCacheBuilderCommand
        from commands.config_adapter import Config
        
        # Parse request body
        body = await request.json()
        target = body.get('target', 'all')  # 'plex', 'jellyfin', or 'all'
        force_rebuild = body.get('force_rebuild', False)  # Renamed from force_refresh
        
        get_commands_logger().info(f"Cache builder API called with target='{target}', force_rebuild={force_rebuild}")
        
        # Create and execute command
        config = Config()
        cmd = LibraryCacheBuilderCommand(config)
        
        # Execute the command with parameters
        target_filter = target if target != 'all' else None
        get_commands_logger().info(f"Executing command with target_filter='{target_filter}', force_rebuild={force_rebuild}")
        success = cmd.execute(force_rebuild=force_rebuild, target_filter=target_filter)
        
        if success:
            return {
                'success': True,
                'message': f'Cache {"rebuilt" if force_rebuild else "refreshed"} successfully for {target}',
                'force_rebuild': force_rebuild,
                'target': target
            }
        else:
            return {
                'success': False,
                'error': f'Cache operation failed for {target}',
                'force_rebuild': force_rebuild,
                'target': target
            }
        
    except Exception as e:
        get_commands_logger().error(f"Failed to execute cache builder: {e}")
        return {
            "success": False,
            "error": "Cache operation failed",
            "message": "Failed to execute cache builder"
        }


# Playlist Sync Endpoints

@router.get("/playlist-sync/validate-url")
async def validate_playlist_url(url: str):
    """Validate playlist URL and fetch metadata"""
    try:
        from utils.playlist_parser import parse_playlist_url
        from clients.client_spotify import SpotifyClient
        from clients.client_deezer import DeezerClient
        from commands.config_adapter import Config
        
        # Parse URL
        parsed = parse_playlist_url(url)
        
        if not parsed['valid']:
            return {
                "valid": False,
                "error": parsed['error'],
                "supported_sources": ["spotify", "deezer"],
                "example_url": "https://open.spotify.com/playlist/4NDXWHwYWjFmgVPkNy4YlF"
            }
        
        # Fetch metadata from source
        source = parsed['source']
        config = Config()
        
        if source == 'spotify':
            spotify_client = SpotifyClient(config)
            try:
                metadata = await spotify_client.get_playlist_info(url)
                
                if metadata.get('success'):
                    return {
                        "valid": True,
                        "source": source,
                        "playlist_id": parsed['playlist_id'],
                        "metadata": {
                            "name": metadata['name'],
                            "description": metadata['description'],
                            "track_count": metadata['track_count'],
                            "owner": metadata['owner']
                        }
                    }
                else:
                    return {
                        "valid": False,
                        "error": "Failed to fetch playlist metadata"
                    }
            finally:
                await spotify_client.close()
        elif source == 'deezer':
            deezer_client = DeezerClient(config)
            try:
                metadata = await deezer_client.get_playlist_info(url)
                
                if metadata.get('success'):
                    return {
                        "valid": True,
                        "source": source,
                        "playlist_id": parsed['playlist_id'],
                        "metadata": {
                            "name": metadata['name'],
                            "description": metadata['description'],
                            "track_count": metadata['track_count'],
                            "owner": metadata['owner']
                        }
                    }
                else:
                    return {
                        "valid": False,
                        "error": "Failed to fetch playlist metadata"
                    }
            finally:
                await deezer_client.close()
        else:
            return {
                "valid": False,
                "error": f"Source {source} not yet supported"
            }
            
    except Exception as e:
        get_commands_logger().error(f"Failed to validate playlist URL: {e}")
        return {
            "valid": False,
            "error": "Failed to validate URL"
        }


@router.post("/playlist-sync/create")
async def create_playlist_sync(request: dict, db: Session = Depends(get_config_db)):
    """Create a new playlist sync command"""
    try:
        # Get playlist type from request
        playlist_type = request.get('playlist_type', 'other')  # 'listenbrainz' or 'other'
        
        if playlist_type == 'listenbrainz':
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
        from utils.playlist_parser import parse_playlist_url
        from clients.client_spotify import SpotifyClient
        from clients.client_deezer import DeezerClient
        from commands.config_adapter import Config
        from database.config_models import CommandConfig
        
        # Validate request
        playlist_url = request.get('playlist_url')
        target = request.get('target')
        sync_mode = request.get('sync_mode', 'full')
        schedule_cron = request.get('schedule_cron')  # None = use global default
        schedule_override = bool(schedule_cron and schedule_cron.strip())
        enabled = request.get('enabled', True)
        
        if not playlist_url:
            raise HTTPException(status_code=400, detail="playlist_url is required")
        if not target:
            raise HTTPException(status_code=400, detail="target is required")
        if target not in ['plex', 'jellyfin']:
            raise HTTPException(status_code=400, detail="target must be 'plex' or 'jellyfin'")
        
        # Validate URL and get metadata
        parsed = parse_playlist_url(playlist_url)
        if not parsed['valid']:
            raise HTTPException(status_code=400, detail=parsed['error'])
        
        source = parsed['source']
        config = Config()
        
        if source == 'spotify':
            spotify_client = SpotifyClient(config)
            try:
                metadata = await spotify_client.get_playlist_info(playlist_url)
                
                get_commands_logger().info(f"Spotify metadata response: {metadata}")
                
                if not metadata or not isinstance(metadata, dict):
                    raise HTTPException(status_code=400, detail='Invalid metadata response from Spotify')
                
                if not metadata.get('success'):
                    raise HTTPException(status_code=400, detail='Failed to fetch playlist metadata from Spotify')
                
                playlist_name = metadata.get('name')
                if not playlist_name:
                    raise HTTPException(status_code=400, detail='Playlist name not found in metadata')
            finally:
                await spotify_client.close()
        elif source == 'deezer':
            deezer_client = DeezerClient(config)
            try:
                metadata = await deezer_client.get_playlist_info(playlist_url)
                
                get_commands_logger().info(f"Deezer metadata response: {metadata}")
                
                if not metadata or not isinstance(metadata, dict):
                    raise HTTPException(status_code=400, detail='Invalid metadata response from Deezer')
                
                if not metadata.get('success'):
                    raise HTTPException(status_code=400, detail='Failed to fetch playlist metadata from Deezer')
                
                playlist_name = metadata.get('name')
                if not playlist_name:
                    raise HTTPException(status_code=400, detail='Playlist name not found in metadata')
            finally:
                await deezer_client.close()
        else:
            raise HTTPException(status_code=400, detail=f"Source {source} not yet supported")
        
        # Generate unique command ID (never reuse IDs for historical consistency)
        try:
            existing_commands = db.query(CommandConfig).filter(
                CommandConfig.command_name.like('playlist_sync_%')
            ).all()
            
            # Find all used IDs from existing commands
            used_ids = set()
            for cmd in existing_commands:
                try:
                    cmd_id = int(cmd.command_name.split('_')[-1])
                    used_ids.add(cmd_id)
                except (ValueError, IndexError):
                    continue
            
            # Also check execution history for any orphaned IDs
            from database.config_models import CommandExecution
            orphaned_executions = db.query(CommandExecution).filter(
                CommandExecution.command_name.like('playlist_sync_%')
            ).all()
            
            for execution in orphaned_executions:
                try:
                    cmd_id = int(execution.command_name.split('_')[-1])
                    used_ids.add(cmd_id)
                except (ValueError, IndexError):
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
        display_name = f"[{source.title()}] {playlist_name} → {target.title()}"
        
        # Create command config
        try:
            config_json = {
                "source": source,
                "unique_id": f"{next_id:05d}",
                "playlist_url": playlist_url,
                "playlist_name": playlist_name,
                "target": target,
                "sync_mode": sync_mode,
                "enable_artist_discovery": request.get('enable_artist_discovery', False)
            }
            
            command = CommandConfig(
                command_name=command_name,
                display_name=display_name,
                description=f"Sync {source.title()} playlist '{playlist_name}' to {target.title()}",
                enabled=enabled,
                schedule_cron=schedule_cron.strip() if schedule_override and schedule_cron else None,
                timeout_minutes=30,
                command_type="playlist_sync",
                config_json=config_json
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
        cache_enabled_key = f'LIBRARY_CACHE_{target.upper()}_ENABLED'
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
            "message": "Playlist sync command created successfully"
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
        playlist_types = request.get('playlist_types', [])
        target = request.get('target')
        sync_mode = request.get('sync_mode', 'full')
        schedule_cron = request.get('schedule_cron')
        schedule_override = bool(schedule_cron and schedule_cron.strip())
        enabled = request.get('enabled', True)
        
        # Retention settings
        weekly_exploration_keep = request.get('weekly_exploration_keep', 2)
        weekly_jams_keep = request.get('weekly_jams_keep', 2)
        daily_jams_keep = request.get('daily_jams_keep', 3)
        cleanup_enabled = request.get('cleanup_enabled', True)
        
        if not playlist_types:
            raise HTTPException(status_code=400, detail="playlist_types is required")
        if not target:
            raise HTTPException(status_code=400, detail="target is required")
        if target not in ['plex', 'jellyfin']:
            raise HTTPException(status_code=400, detail="target must be 'plex' or 'jellyfin'")
        
        # Validate playlist types
        valid_types = ['weekly_exploration', 'weekly_jams', 'daily_jams']
        for playlist_type in playlist_types:
            if playlist_type not in valid_types:
                raise HTTPException(status_code=400, detail=f"Invalid playlist type: {playlist_type}")
        
        # Create config instance
        config = Config()
        
        # Generate unique command ID (never reuse IDs for historical consistency)
        try:
            existing_commands = db.query(CommandConfig).filter(
                CommandConfig.command_name.like('playlist_sync_%')
            ).all()
            
            # Find all used IDs from existing commands
            used_ids = set()
            for cmd in existing_commands:
                try:
                    cmd_id = int(cmd.command_name.split('_')[-1])
                    used_ids.add(cmd_id)
                except (ValueError, IndexError):
                    continue
            
            # Also check execution history for any orphaned IDs
            from database.config_models import CommandExecution
            orphaned_executions = db.query(CommandExecution).filter(
                CommandExecution.command_name.like('playlist_sync_%')
            ).all()
            
            for execution in orphaned_executions:
                try:
                    cmd_id = int(execution.command_name.split('_')[-1])
                    used_ids.add(cmd_id)
                except (ValueError, IndexError):
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
            playlist_name = playlist_types[0].replace('_', ' ').title()
            display_name = f"[ListenBrainz] {playlist_name} → {target.title()}"
        elif len(playlist_types) == len(valid_types):
            display_name = f"[ListenBrainz] All Curated Playlists → {target.title()}"
        else:
            playlist_names = [pt.replace('_', ' ').title() for pt in playlist_types]
            display_name = f"[ListenBrainz] {', '.join(playlist_names)} → {target.title()}"
        
        # Create command config
        try:
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
                "enable_artist_discovery": request.get('enable_artist_discovery', False)
            }
            
            command = CommandConfig(
                command_name=command_name,
                display_name=display_name,
                description=f"Sync ListenBrainz curated playlists to {target.title()}",
                enabled=enabled,
                schedule_cron=schedule_cron.strip() if schedule_override and schedule_cron else None,
                timeout_minutes=30,
                command_type="playlist_sync",
                config_json=config_json
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
        cache_enabled_key = f'LIBRARY_CACHE_{target.upper()}_ENABLED'
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
            "message": "ListenBrainz playlist sync command created successfully"
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
async def delete_command(command_name: str, db: Session = Depends(get_config_db)):
    """Delete a command (enhanced to support playlist_sync_* commands)"""
    try:
        # Validate command_name parameter
        if not command_name:
            raise HTTPException(status_code=400, detail="Command name is required")
        
        command = db.query(CommandConfig).filter(CommandConfig.command_name == command_name).first()
        if not command:
            raise HTTPException(status_code=404, detail="Command not found")
        
        # Check if it's a playlist sync command
        if command_name.startswith('playlist_sync_'):
            # Allow deletion of dynamic playlist sync commands
            pass
        elif command_name in ['discovery_lastfm', 'library_cache_builder', 'new_releases_discovery', 'playlist_sync_discovery_maintenance']:
            raise HTTPException(status_code=400, detail="Cannot delete built-in commands")
        
        db.delete(command)
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
                "config_help": "Add Spotify Client ID and Secret in Settings"
            },
            {
                "id": "deezer",
                "name": "Deezer",
                "requires_url": True,
                "example_url": "https://www.deezer.com/en/playlist/1479458365",
                "configured": True,  # Deezer doesn't require authentication for public playlists
                "config_help": "Deezer public playlists work without configuration"
            }
        ]
        
        return {"sources": sources}
        
    except Exception as e:
        get_commands_logger().error(f"Failed to get playlist sync sources: {e}")
        raise HTTPException(status_code=500, detail="Failed to get playlist sync sources")


