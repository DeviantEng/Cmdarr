#!/usr/bin/env python3
"""
Status API endpoints
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import Dict, Any, List
from datetime import datetime, timedelta
import time
import psutil
import os

from database.database import get_config_db
from database.config_models import CommandConfig, CommandExecution, SystemStatus
from __version__ import __version__
from services.config_service import config_service
from utils.logger import get_logger

router = APIRouter()
# Lazy-load logger to avoid initialization issues
def get_status_logger():
    return get_logger('cmdarr.api.status')


@router.get("/system")
async def get_system_status():
    """Get system status and health information"""
    try:
        # Get system information
        system_info = {
            "app_name": "Cmdarr",
            "version": __version__,
            "uptime_seconds": time.time() - psutil.Process().create_time(),
            "timestamp": datetime.utcnow().isoformat() + 'Z',
            "python_version": f"{os.sys.version_info.major}.{os.sys.version_info.minor}.{os.sys.version_info.micro}",
            "platform": os.name
        }
        
        # Get memory usage
        memory = psutil.virtual_memory()
        system_info["memory"] = {
            "total_mb": round(memory.total / 1024 / 1024, 2),
            "available_mb": round(memory.available / 1024 / 1024, 2),
            "used_mb": round(memory.used / 1024 / 1024, 2),
            "percent_used": memory.percent
        }
        
        # Get disk usage
        disk = psutil.disk_usage('/')
        system_info["disk"] = {
            "total_gb": round(disk.total / 1024 / 1024 / 1024, 2),
            "used_gb": round(disk.used / 1024 / 1024 / 1024, 2),
            "free_gb": round(disk.free / 1024 / 1024 / 1024, 2),
            "percent_used": round((disk.used / disk.total) * 100, 2)
        }
        
        # Get CPU usage
        cpu_percent = psutil.cpu_percent(interval=1)
        system_info["cpu"] = {
            "percent_used": cpu_percent,
            "core_count": psutil.cpu_count()
        }
        
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
            "timestamp": datetime.utcnow().isoformat() + 'Z'
        }
        
        # Database health check
        try:
            from database.database import get_database_manager
            from sqlalchemy import text
            db_manager = get_database_manager()
            session = db_manager.get_session_sync()
            try:
                session.execute(text("SELECT 1"))
                health_status["checks"]["database"] = {
                    "status": "healthy",
                    "message": "Database connection successful"
                }
            finally:
                session.close()
        except Exception as e:
            get_status_logger().error(f"Database connection check failed: {e}")
            health_status["checks"]["database"] = {
                "status": "unhealthy",
                "message": "Database connection failed"
            }
            health_status["overall_status"] = "unhealthy"
        
        # Configuration health check
        try:
            missing_config = config_service.validate_required_settings()
            if missing_config:
                health_status["checks"]["configuration"] = {
                    "status": "unhealthy",
                    "message": f"Missing required configuration: {missing_config}"
                }
                health_status["overall_status"] = "unhealthy"
            else:
                health_status["checks"]["configuration"] = {
                    "status": "healthy",
                    "message": "All required configuration present"
                }
        except Exception as e:
            get_status_logger().error(f"Configuration validation check failed: {e}")
            health_status["checks"]["configuration"] = {
                "status": "unhealthy",
                "message": "Configuration validation failed"
            }
            health_status["overall_status"] = "unhealthy"
        
        # Commands health check
        try:
            from database.database import get_database_manager
            db_manager = get_database_manager()
            session = db_manager.get_session_sync()
            try:
                # Get all enabled commands, excluding helper commands
                all_enabled_commands = session.query(CommandConfig).filter(CommandConfig.enabled == True).all()
                helper_commands = {'library_cache_builder'}  # Known helper commands
                
                # Filter out helper commands
                user_enabled_commands = [cmd for cmd in all_enabled_commands if cmd.command_name not in helper_commands]
                enabled_commands_count = len(user_enabled_commands)
                
                running_commands = session.query(CommandExecution)\
                    .filter(CommandExecution.completed_at.is_(None))\
                    .count()
                
                health_status["checks"]["commands"] = {
                    "status": "healthy",
                    "message": f"{enabled_commands_count} enabled commands, {running_commands} currently running"
                }
            finally:
                session.close()
        except Exception as e:
            get_status_logger().error(f"Command status check failed: {e}")
            health_status["checks"]["commands"] = {
                "status": "unhealthy",
                "message": "Command status check failed"
            }
            health_status["overall_status"] = "unhealthy"
        
        return health_status
    except Exception as e:
        get_status_logger().error(f"Failed to get health status: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve health status")


@router.get("/commands")
async def get_commands_status(db: Session = Depends(get_config_db)):
    """Get status of all commands"""
    try:
        all_commands = db.query(CommandConfig).all()
        helper_commands = {'library_cache_builder'}  # Known helper commands
        
        # Filter out helper commands
        commands = [cmd for cmd in all_commands if cmd.command_name not in helper_commands]
        command_statuses = []
        
        for command in commands:
            # Get recent executions
            recent_executions = db.query(CommandExecution)\
                .filter(CommandExecution.command_name == command.command_name)\
                .order_by(CommandExecution.started_at.desc())\
                .limit(5)\
                .all()
            
            # Check if currently running (only the most recent execution matters)
            is_running = recent_executions[0].is_running if recent_executions else False
            
            # Get success rate for last 10 executions
            last_10_executions = db.query(CommandExecution)\
                .filter(CommandExecution.command_name == command.command_name)\
                .filter(CommandExecution.completed_at.isnot(None))\
                .order_by(CommandExecution.started_at.desc())\
                .limit(10)\
                .all()
            
            success_rate = 0
            if last_10_executions:
                successful = sum(1 for exec in last_10_executions if exec.success)
                success_rate = (successful / len(last_10_executions)) * 100
            
            command_statuses.append({
                "command_name": command.command_name,
                "display_name": command.display_name,
                "enabled": command.enabled,
                "schedule_cron": command.schedule_cron,
                "is_running": is_running,
                "last_run": command.last_run.isoformat() + 'Z' if command.last_run else None,
                "last_success": command.last_success,
                "last_duration": command.last_duration,
                "last_error": command.last_error,
                "success_rate_percent": round(success_rate, 1),
                "recent_executions": len(recent_executions)
            })
        
        return {
            "commands": command_statuses,
            "total_commands": len(commands),
            "enabled_commands": len([c for c in commands if c.enabled]),
            "running_commands": len([c for c in command_statuses if c["is_running"]]),
            "timestamp": datetime.utcnow().isoformat() + 'Z'
        }
    except Exception as e:
        get_status_logger().error(f"Failed to get commands status: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve commands status")


@router.get("/executions/recent")
async def get_recent_executions(
    limit: int = 20,
    db: Session = Depends(get_config_db)
):
    """Get recent command executions"""
    try:
        executions = db.query(CommandExecution)\
            .order_by(CommandExecution.started_at.desc())\
            .limit(limit)\
            .all()
        
        execution_list = []
        for execution in executions:
            # Determine status based on execution state
            if execution.is_running:
                status = "running"
            elif execution.completed_at is not None:
                status = "completed" if execution.success else "failed"
            else:
                status = "running"  # Fallback for incomplete executions
            
            # Get command configuration to extract target information
            command_config = db.query(CommandConfig).filter(
                CommandConfig.command_name == execution.command_name
            ).first()
            
            execution_list.append({
                "id": execution.id,
                "command_name": execution.command_name,
                "started_at": execution.started_at.isoformat() + 'Z',
                "completed_at": execution.completed_at.isoformat() + 'Z' if execution.completed_at else None,
                "success": execution.success,
                "duration": execution.duration,
                "error_message": execution.error_message,
                "triggered_by": execution.triggered_by,
                "is_running": execution.is_running,
                "status": status,
                "output_summary": execution.output_summary,
                "target": command_config.config_json.get('target', 'unknown') if command_config and command_config.config_json else 'unknown'
            })
        
        return {
            "executions": execution_list,
            "total_count": len(execution_list),
            "timestamp": datetime.utcnow().isoformat() + 'Z'
        }
    except Exception as e:
        get_status_logger().error(f"Failed to get recent executions: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve recent executions")


@router.get("/statistics")
async def get_statistics(db: Session = Depends(get_config_db)):
    """Get application statistics"""
    try:
        # Get time range for statistics (last 30 days)
        thirty_days_ago = datetime.utcnow() - timedelta(days=30)
        
        # Command execution statistics
        total_executions = db.query(CommandExecution)\
            .filter(CommandExecution.started_at >= thirty_days_ago)\
            .count()
        
        successful_executions = db.query(CommandExecution)\
            .filter(CommandExecution.started_at >= thirty_days_ago)\
            .filter(CommandExecution.success == True)\
            .count()
        
        failed_executions = db.query(CommandExecution)\
            .filter(CommandExecution.started_at >= thirty_days_ago)\
            .filter(CommandExecution.success == False)\
            .count()
        
        # Average execution time
        completed_executions = db.query(CommandExecution)\
            .filter(CommandExecution.started_at >= thirty_days_ago)\
            .filter(CommandExecution.completed_at.isnot(None))\
            .filter(CommandExecution.duration.isnot(None))\
            .all()
        
        avg_duration = 0
        if completed_executions:
            total_duration = sum(exec.duration for exec in completed_executions)
            avg_duration = total_duration / len(completed_executions)
        
        # Command-specific statistics
        command_stats = {}
        commands = db.query(CommandConfig).all()
        for command in commands:
            command_executions = db.query(CommandExecution)\
                .filter(CommandExecution.command_name == command.command_name)\
                .filter(CommandExecution.started_at >= thirty_days_ago)\
                .all()
            
            if command_executions:
                command_successful = sum(1 for exec in command_executions if exec.success)
                command_stats[command.command_name] = {
                    "total_executions": len(command_executions),
                    "successful_executions": command_successful,
                    "success_rate": (command_successful / len(command_executions)) * 100
                }
        
        return {
            "period": "last_30_days",
            "total_executions": total_executions,
            "successful_executions": successful_executions,
            "failed_executions": failed_executions,
            "success_rate_percent": round((successful_executions / total_executions) * 100, 1) if total_executions > 0 else 0,
            "average_duration_seconds": round(avg_duration, 2),
            "command_statistics": command_stats,
            "timestamp": datetime.utcnow().isoformat() + 'Z'
        }
    except Exception as e:
        get_status_logger().error(f"Failed to get statistics: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve statistics")


async def _get_cache_status_for_target(target: str, cache_manager, cache_stats):
    """Helper function to get cache status for a specific target"""
    library_cache = None
    # Get per-client cache stats
    client_stats = cache_manager.get_client_stats(target)
    
    cache_info = {
        'target': target,
        'status': 'Not available',
        'last_generated': None,
        'size_mb': 0,
        'object_count': 0,
        'cache_hits': client_stats.get('cache_hits', 0),
        'cache_misses': client_stats.get('cache_misses', 0),
        'hit_rate': client_stats.get('hit_rate', 0.0),
        'last_used': client_stats.get('last_used'),
        'memory_usage_mb': cache_stats.get('memory_usage_mb', 0)
    }
    
    try:
        # Try to get cache data directly from database (doesn't require client registration)
        library_cache = cache_manager.get_library_cache_direct(target)
        
        if library_cache:
            cache_info.update({
                'status': 'Available',
                'last_generated': library_cache.get('built_at'),
                'size_mb': round(len(str(library_cache)) / 1024 / 1024, 2),
                'object_count': library_cache.get('total_tracks', 0)
            })
        else:
            # Check if client is registered for more detailed status
            if target not in cache_manager.registered_clients:
                cache_info['status'] = 'Not built'
                cache_info['message'] = f'{target} cache not found in database'
            else:
                cache_info['status'] = 'Not built'
    except Exception as e:
        get_status_logger().warning(f"Failed to get library cache for {target}: {e}")
        cache_info['status'] = 'Error'
        cache_info['error'] = 'Failed to retrieve cache status'
    
    return cache_info


@router.get("/cache")
async def get_cache_status(target: str = None):
    """Get music library cache status for a specific target (plex/jellyfin) or all targets"""
    try:
        from utils.library_cache_manager import get_library_cache_manager
        from services.config_service import config_service
        
        # Get library cache manager
        cache_manager = get_library_cache_manager(config_service)
        
        # Get cache statistics
        cache_stats = cache_manager.get_cache_stats()
        
        # If no target specified, return both Plex and Jellyfin cache info
        if not target:
            return {
                'plex': await _get_cache_status_for_target('plex', cache_manager, cache_stats),
                'jellyfin': await _get_cache_status_for_target('jellyfin', cache_manager, cache_stats)
            }
        
        # Validate target
        if target.lower() not in ['plex', 'jellyfin']:
            raise HTTPException(status_code=400, detail="Target must be 'plex' or 'jellyfin'")
        
        return await _get_cache_status_for_target(target.lower(), cache_manager, cache_stats)
        
    except Exception as e:
        get_status_logger().error(f"Failed to get cache status: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve cache status")

@router.post("/cache/reset")
async def reset_cache_stats():
    """Reset cache statistics for all clients (for testing)"""
    try:
        from utils.library_cache_manager import get_library_cache_manager, reset_library_cache_manager
        from services.config_service import config_service
        
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
