#!/usr/bin/env python3
"""
Command cleanup service for Cmdarr
Handles stuck commands, timeouts, and cleanup tasks
"""

import asyncio
from datetime import datetime, timedelta
from typing import List, Optional
from sqlalchemy.orm import Session
from database.config_models import CommandConfig, CommandExecution
from database.database import get_config_db
from utils.logger import get_logger

logger = get_logger('cmdarr.command_cleanup')


class CommandCleanupService:
    """Service for cleaning up stuck and timed-out commands"""
    
    def __init__(self):
        self.cleanup_interval = 300  # 5 minutes
        self.cleanup_task: Optional[asyncio.Task] = None
    
    async def start_cleanup_task(self):
        """Start the background cleanup task"""
        if self.cleanup_task is None or self.cleanup_task.done():
            self.cleanup_task = asyncio.create_task(self._cleanup_loop())
            logger.info("Command cleanup task started")
    
    async def stop_cleanup_task(self):
        """Stop the background cleanup task"""
        if self.cleanup_task and not self.cleanup_task.done():
            self.cleanup_task.cancel()
            try:
                await self.cleanup_task
            except asyncio.CancelledError:
                pass
            logger.info("Command cleanup task stopped")
    
    async def _cleanup_loop(self):
        """Background cleanup loop"""
        while True:
            try:
                await self.cleanup_stuck_commands()
                await self.cleanup_timed_out_commands()
                await self.cleanup_old_executions()
                await asyncio.sleep(self.cleanup_interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in cleanup loop: {e}")
                await asyncio.sleep(60)  # Wait 1 minute before retrying
    
    async def cleanup_stuck_commands(self):
        """Clean up commands that have been running for too long without a timeout"""
        try:
            from database.database import get_database_manager
            manager = get_database_manager()
            db = manager.get_session_sync()
            
            # Find commands running for more than 2 hours without a timeout
            cutoff_time = datetime.utcnow() - timedelta(hours=2)
            stuck_commands = db.query(CommandExecution).filter(
                CommandExecution.status == 'running',
                CommandExecution.started_at < cutoff_time
            ).all()
            
            for execution in stuck_commands:
                await self._mark_command_failed(
                    execution, 
                    "Command timed out after 2 hours (no timeout configured)",
                    db
                )
                logger.warning(f"Marked stuck command {execution.command_name} (ID: {execution.id}) as failed")
            
            if stuck_commands:
                db.commit()
                logger.info(f"Cleaned up {len(stuck_commands)} stuck commands")
            
        except Exception as e:
            logger.error(f"Failed to cleanup stuck commands: {e}")
        finally:
            if 'db' in locals():
                db.close()
    
    async def cleanup_timed_out_commands(self):
        """Clean up commands that have exceeded their configured timeout"""
        try:
            from database.database import get_database_manager
            manager = get_database_manager()
            db = manager.get_session_sync()
            
            # Find running commands with timeouts
            running_commands = db.query(CommandExecution).filter(
                CommandExecution.status == 'running'
            ).all()
            
            timed_out_count = 0
            for execution in running_commands:
                # Get the command config to check timeout
                command_config = db.query(CommandConfig).filter(
                    CommandConfig.command_name == execution.command_name
                ).first()
                
                if command_config and command_config.timeout_minutes:
                    timeout_delta = timedelta(minutes=command_config.timeout_minutes)
                    if execution.started_at < datetime.utcnow() - timeout_delta:
                        await self._mark_command_failed(
                            execution,
                            f"Command timed out after {command_config.timeout_minutes} minutes",
                            db
                        )
                        timed_out_count += 1
                        logger.warning(f"Command {execution.command_name} (ID: {execution.id}) timed out after {command_config.timeout_minutes} minutes")
            
            if timed_out_count > 0:
                db.commit()
                logger.info(f"Cleaned up {timed_out_count} timed out commands")
            
        except Exception as e:
            logger.error(f"Failed to cleanup timed out commands: {e}")
        finally:
            if 'db' in locals():
                db.close()
    
    async def cleanup_startup_stuck_commands(self):
        """Clean up any commands that were running when the application was shut down"""
        try:
            from database.database import get_database_manager
            manager = get_database_manager()
            db = manager.get_session_sync()
            
            # Find all commands that were running (likely from previous app instance)
            stuck_commands = db.query(CommandExecution).filter(
                CommandExecution.status == 'running'
            ).all()
            
            for execution in stuck_commands:
                await self._mark_command_failed(
                    execution,
                    "Command was running when application restarted",
                    db
                )
                logger.info(f"Marked startup stuck command {execution.command_name} (ID: {execution.id}) as failed")
            
            if stuck_commands:
                db.commit()
                logger.info(f"Cleaned up {len(stuck_commands)} startup stuck commands")
            
        except Exception as e:
            logger.error(f"Failed to cleanup startup stuck commands: {e}")
        finally:
            if 'db' in locals():
                db.close()
    
    async def _mark_command_failed(self, execution: CommandExecution, reason: str, db: Session):
        """Mark a command execution as failed"""
        execution.status = 'failed'
        execution.completed_at = datetime.utcnow()
        execution.success = False
        execution.error_message = reason
        
        if execution.started_at:
            execution.duration = (execution.completed_at - execution.started_at).total_seconds()
    
    async def get_running_commands(self) -> List[CommandExecution]:
        """Get all currently running commands"""
        try:
            from database.database import get_database_manager
            manager = get_database_manager()
            db = manager.get_session_sync()
            return db.query(CommandExecution).filter(
                CommandExecution.status == 'running'
            ).all()
        except Exception as e:
            logger.error(f"Failed to get running commands: {e}")
            return []
        finally:
            if 'db' in locals():
                db.close()
    
    async def cleanup_old_executions(self, keep_count: Optional[int] = None):
        """Clean up old command executions, keeping only the most recent ones"""
        try:
            # Get retention count from config if not provided
            if keep_count is None:
                from services.config_service import config_service
                keep_count = config_service.get_int('COMMAND_CLEANUP_RETENTION', 50)
            
            from database.database import get_database_manager
            manager = get_database_manager()
            db = manager.get_session_sync()
            
            # Get all commands and clean up each one
            commands = db.query(CommandConfig).all()
            total_deleted = 0
            
            for command in commands:
                # Get executions for this command
                executions = db.query(CommandExecution).filter(
                    CommandExecution.command_name == command.command_name
                ).order_by(CommandExecution.started_at.desc()).all()
                
                if len(executions) > keep_count:
                    # Delete old executions beyond keep_count
                    executions_to_delete = executions[keep_count:]
                    for execution in executions_to_delete:
                        db.delete(execution)
                    
                    deleted_count = len(executions_to_delete)
                    total_deleted += deleted_count
                    logger.info(f"Cleaned up {deleted_count} old executions for {command.command_name}")
            
            if total_deleted > 0:
                db.commit()
                logger.info(f"Total cleaned up {total_deleted} old executions across all commands")
            
        except Exception as e:
            logger.error(f"Failed to cleanup old executions: {e}")
        finally:
            if 'db' in locals():
                db.close()
    
    async def force_cleanup_all_running(self):
        """Force cleanup all running commands (emergency function)"""
        try:
            from database.database import get_database_manager
            manager = get_database_manager()
            db = manager.get_session_sync()
            
            running_commands = db.query(CommandExecution).filter(
                CommandExecution.status == 'running'
            ).all()
            
            for execution in running_commands:
                await self._mark_command_failed(
                    execution,
                    "Force cleaned up - all running commands cleared",
                    db
                )
            
            if running_commands:
                db.commit()
                logger.warning(f"Force cleaned up {len(running_commands)} running commands")
            
        except Exception as e:
            logger.error(f"Failed to force cleanup running commands: {e}")
        finally:
            if 'db' in locals():
                db.close()


# Global cleanup service instance
command_cleanup = CommandCleanupService()
