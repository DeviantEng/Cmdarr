#!/usr/bin/env python3
"""
Commands API endpoints
"""

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, Request
from sqlalchemy.orm import Session
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field
from datetime import datetime, timedelta

from database.database import get_db
from database.models import CommandConfig, CommandExecution
from services.command_executor import command_executor
from utils.logger import get_logger

router = APIRouter()
logger = get_logger('cmdarr.api.commands')


def utc_datetime_serializer(dt: Optional[datetime]) -> Optional[str]:
    """Serialize UTC datetime with Z suffix for proper JavaScript parsing"""
    if dt is None:
        return None
    return dt.isoformat() + 'Z'


def calculate_next_run(last_run: Optional[datetime], schedule_hours: Optional[int]) -> Optional[datetime]:
    """Calculate the next run time based on last run and schedule hours"""
    if not schedule_hours:
        return None
    
    if not last_run:
        # If no last run, schedule for immediate execution (next minute)
        return datetime.utcnow() + timedelta(minutes=1)
    
    # Calculate next run from last run
    next_run = last_run + timedelta(hours=schedule_hours)
    
    # If the calculated next run is in the past, schedule for immediate execution
    if next_run < datetime.utcnow():
        return datetime.utcnow() + timedelta(minutes=1)
    
    return next_run


class CommandUpdateRequest(BaseModel):
    """Request model for updating command configuration"""
    enabled: Optional[bool] = None
    schedule_hours: Optional[int] = None
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
    schedule_hours: Optional[int]
    timeout_minutes: Optional[int]
    config_json: Optional[Dict[str, Any]]
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
    
    # Calculate next_run
    next_run = calculate_next_run(command.last_run, command.schedule_hours)
    
    # Serialize datetime fields with Z suffix for proper JavaScript parsing
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
async def get_all_commands(db: Session = Depends(get_db)):
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
        logger.error(f"Failed to get commands: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve commands")


@router.get("/{command_name}", response_model=CommandConfigResponse)
async def get_command(command_name: str, db: Session = Depends(get_db)):
    """Get a specific command configuration"""
    try:
        command = db.query(CommandConfig).filter(CommandConfig.command_name == command_name).first()
        if not command:
            raise HTTPException(status_code=404, detail="Command not found")
        
        return command_to_response(command)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get command {command_name}: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve command")


@router.put("/{command_name}")
async def update_command(
    command_name: str, 
    request: CommandUpdateRequest, 
    db: Session = Depends(get_db)
):
    """Update a command configuration"""
    try:
        command = db.query(CommandConfig).filter(CommandConfig.command_name == command_name).first()
        if not command:
            raise HTTPException(status_code=404, detail="Command not found")
        
        # Track if enabled status or schedule changed
        enabled_changed = request.enabled is not None and request.enabled != command.enabled
        schedule_changed = request.schedule_hours is not None and request.schedule_hours != command.schedule_hours
        
        # Update fields if provided
        if request.enabled is not None:
            command.enabled = request.enabled
        if request.schedule_hours is not None:
            command.schedule_hours = request.schedule_hours
        if request.timeout_minutes is not None:
            command.timeout_minutes = request.timeout_minutes
        if request.config_json is not None:
            command.config_json = request.config_json
        
        command.updated_at = datetime.utcnow()
        db.commit()
        
        # Notify scheduler of changes
        if enabled_changed or schedule_changed:
            try:
                from services.scheduler import scheduler
                if command.enabled and command.schedule_hours:
                    if schedule_changed:
                        await scheduler.update_command_schedule(command_name)
                    else:
                        await scheduler.enable_command(command_name)
                else:
                    await scheduler.disable_command(command_name)
            except Exception as e:
                logger.warning(f"Failed to notify scheduler of command {command_name} change: {e}")
        
        return {"message": f"Command {command_name} updated successfully"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update command {command_name}: {e}")
        raise HTTPException(status_code=500, detail="Failed to update command")


@router.post("/{command_name}/execute")
async def execute_command(
    command_name: str, 
    request: CommandExecutionRequest,
    db: Session = Depends(get_db)
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
        logger.info(f"API: Executing command {command_name} with triggered_by='{request.triggered_by}'")
        result = await command_executor.execute_command(command_name, None, request.triggered_by)
        
        if result['success']:
            return {
                "message": result['message'],
                "execution_id": result['execution_id']
            }
        else:
            raise HTTPException(status_code=400, detail=result['error'])
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to execute command {command_name}: {e}")
        raise HTTPException(status_code=500, detail="Failed to execute command")


@router.get("/{command_name}/executions", response_model=List[CommandExecutionResponse])
async def get_command_executions(
    command_name: str, 
    limit: int = 50,
    db: Session = Depends(get_db)
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
        logger.error(f"Failed to get executions for command {command_name}: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve command executions")


@router.get("/{command_name}/status")
async def get_command_status(command_name: str, db: Session = Depends(get_db)):
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
            "schedule_hours": command.schedule_hours,
            "is_running": status.get('is_running', False),
            "last_execution": status.get('last_execution')
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get status for command {command_name}: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve command status")


@router.post("/cleanup-stuck")
async def cleanup_stuck_executions():
    """Clean up stuck command executions"""
    try:
        await command_executor.cleanup_stuck_executions()
        return {"message": "Stuck executions cleaned up successfully"}
    except Exception as e:
        logger.error(f"Failed to cleanup stuck executions: {e}")
        raise HTTPException(status_code=500, detail="Failed to cleanup stuck executions")


@router.post("/executions/{execution_id}/kill")
async def kill_execution(execution_id: int, db: Session = Depends(get_db)):
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
        
        db.commit()
        
        # Try to kill the actual process if it's running
        try:
            from services.command_executor import command_executor
            command_executor.kill_execution(execution_id)
        except Exception as e:
            logger.warning(f"Failed to kill process for execution {execution_id}: {e}")
        
        logger.info(f"Execution {execution_id} cancelled successfully")
        return {"message": f"Execution {execution_id} cancelled successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to kill execution {execution_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to kill execution")


@router.delete("/executions/{execution_id}")
async def delete_execution(execution_id: int, db: Session = Depends(get_db)):
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
        
        logger.info(f"Execution {execution_id} deleted successfully")
        return {"message": f"Execution {execution_id} deleted successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete execution {execution_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to delete execution")


@router.delete("/executions")
async def clear_execution_history():
    """Clear all command execution history"""
    try:
        from database.database import get_database_manager
        from database.models import CommandExecution
        
        db_manager = get_database_manager()
        session = db_manager.get_session_sync()
        try:
            # Delete all execution records
            deleted_count = session.query(CommandExecution).delete()
            session.commit()
            
            logger.info(f"Cleared {deleted_count} execution records")
            return {"message": f"Cleared {deleted_count} execution records"}
        finally:
            session.close()
    except Exception as e:
        logger.error(f"Failed to clear execution history: {e}")
        raise HTTPException(status_code=500, detail="Failed to clear execution history")


@router.post("/executions/cleanup")
async def cleanup_executions(
    command_name: Optional[str] = None,
    keep_count: Optional[int] = None,
    db: Session = Depends(get_db)
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
        
        logger.info(f"Cleaned up {deleted_count} old executions, kept {keep_count}")
        return {
            "message": f"Cleaned up {deleted_count} old executions, kept {keep_count}",
            "deleted_count": deleted_count,
            "kept_count": keep_count
        }
        
    except Exception as e:
        logger.error(f"Failed to cleanup executions: {e}")
        raise HTTPException(status_code=500, detail="Failed to cleanup executions")


@router.get("/status/scheduler")
async def get_scheduler_status():
    """Get scheduler status and information"""
    try:
        from services.scheduler import scheduler
        
        return {
            "running": scheduler.running,
            "scheduled_commands": list(scheduler.get_scheduled_commands()),
            "check_interval_seconds": scheduler.check_interval
        }
    except Exception as e:
        logger.error(f"Failed to get scheduler status: {e}")
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
        
        logger.info(f"Cache builder API called with target='{target}', force_rebuild={force_rebuild}")
        
        # Create and execute command
        config = Config()
        cmd = LibraryCacheBuilderCommand(config)
        
        # Execute the command with parameters
        target_filter = target if target != 'all' else None
        logger.info(f"Executing command with target_filter='{target_filter}', force_rebuild={force_rebuild}")
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
        logger.error(f"Failed to execute cache builder: {e}")
        return {
            "success": False,
            "error": str(e),
            "message": "Failed to execute cache builder"
        }


