#!/usr/bin/env python3
"""
Background scheduler service for automatic command execution
"""

import asyncio
import time
from datetime import datetime, timedelta
from typing import Dict, Set, Optional, Any
from sqlalchemy.orm import Session

from database.database import get_database_manager
from database.models import CommandConfig, CommandExecution
from services.command_executor import command_executor
from utils.logger import get_logger


class CommandScheduler:
    """Background scheduler for automatic command execution"""
    
    def __init__(self):
        self.logger = get_logger('cmdarr.scheduler')
        self.running = False
        self.scheduled_tasks: Dict[str, asyncio.Task] = {}
        self.check_interval = 60  # Check every 60 seconds
        self._task: Optional[asyncio.Task] = None
        
        # Command queue system
        self.command_queue: Optional[asyncio.Queue] = None
        self.queue_processor_task: Optional[asyncio.Task] = None
        self.currently_running_command: Optional[str] = None
        
    async def start(self):
        """Start the background scheduler"""
        if self.running:
            self.logger.warning("Scheduler is already running")
            return
            
        self.running = True
        self.logger.info("Starting command scheduler")
        
        # Initialize command queue
        self.command_queue = asyncio.Queue()
        
        # Start the main scheduler loop
        self._task = asyncio.create_task(self._scheduler_loop())
        
        # Start the command queue processor
        self.queue_processor_task = asyncio.create_task(self._process_command_queue())
        
        # Initialize scheduled tasks for enabled commands
        await self._initialize_scheduled_tasks()
        
    async def stop(self):
        """Stop the background scheduler"""
        if not self.running:
            return
            
        self.running = False
        self.logger.info("Stopping command scheduler")
        
        # Cancel all scheduled tasks
        for task in self.scheduled_tasks.values():
            task.cancel()
        self.scheduled_tasks.clear()
        
        # Cancel queue processor task
        if self.queue_processor_task:
            self.queue_processor_task.cancel()
            try:
                await self.queue_processor_task
            except asyncio.CancelledError:
                pass
        
        # Cancel main scheduler task
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
                
    async def _scheduler_loop(self):
        """Main scheduler loop that runs continuously"""
        while self.running:
            try:
                await self._check_and_execute_commands()
                await asyncio.sleep(self.check_interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"Scheduler loop error: {e}")
                await asyncio.sleep(self.check_interval)
                
    async def _check_and_execute_commands(self):
        """Check all enabled commands and execute if scheduled time has passed"""
        try:
            manager = get_database_manager()
            session = manager.get_session_sync()
            try:
                # Get all enabled commands with schedules
                enabled_commands = session.query(CommandConfig).filter(
                    CommandConfig.enabled == True,
                    CommandConfig.schedule_hours.isnot(None)
                ).all()
                
                for command in enabled_commands:
                    await self._check_command_schedule(command)
                    
            finally:
                session.close()
                
        except Exception as e:
            self.logger.error(f"Failed to check command schedules: {e}")
            
    async def _check_command_schedule(self, command: CommandConfig):
        """Check if a specific command should be executed"""
        try:
            # Use the same calculation logic as the API
            from app.api.commands import calculate_next_run
            next_run = calculate_next_run(command.last_run, command.schedule_hours)
            
            # Check if it's time to run
            # If next_run is None, it means the command has never run and should run immediately
            # If next_run is in the past, it means the command is overdue
            # If next_run is in the future, check if it's time to run
            if next_run is None or datetime.utcnow() >= next_run:
                if next_run is None:
                    reason = "never run"
                elif next_run < datetime.utcnow():
                    reason = "overdue"
                else:
                    reason = "scheduled"
                self.logger.info(f"Command {command.command_name} is due to run ({reason})")
                await self._queue_command_execution(command.command_name)
                
        except Exception as e:
            self.logger.error(f"Failed to check schedule for {command.command_name}: {e}")
    
    async def _queue_command_execution(self, command_name: str):
        """Add a command to the execution queue"""
        try:
            # Check if command is already in queue or running
            if command_name in self.scheduled_tasks:
                self.logger.warning(f"Command {command_name} is already queued or running")
                return
            
            # Add to queue
            await self.command_queue.put(command_name)
            self.logger.info(f"Queued command {command_name} for execution")
            
        except Exception as e:
            self.logger.error(f"Failed to queue command {command_name}: {e}")
    
    async def _process_command_queue(self):
        """Process commands from the queue one at a time"""
        self.logger.info("Command queue processor started")
        while self.running:
            try:
                # Wait for a command to be queued
                self.logger.debug("Waiting for commands in queue...")
                command_name = await self.command_queue.get()
                
                # Check if we're still running
                if not self.running:
                    break
                
                self.logger.info(f"Processing command from queue: {command_name}")
                # Execute the command
                await self._execute_command_from_queue(command_name)
                
                # Mark task as done
                self.command_queue.task_done()
                
            except asyncio.CancelledError:
                self.logger.info("Command queue processor cancelled")
                break
            except Exception as e:
                self.logger.error(f"Error processing command queue: {e}")
                await asyncio.sleep(5)  # Wait before retrying
    
    async def _execute_command_from_queue(self, command_name: str):
        """Execute a command from the queue"""
        try:
            self.currently_running_command = command_name
            self.logger.info(f"Starting execution of {command_name}")
            
            # Execute command asynchronously
            task = asyncio.create_task(
                command_executor.execute_command(command_name, triggered_by='scheduler')
            )
            self.scheduled_tasks[command_name] = task
            
            # Clean up task when complete and update last_run only on success
            task.add_done_callback(lambda t: self._handle_command_completion(command_name, t))
            
            # Wait for command to complete
            await task
            
        except Exception as e:
            self.logger.error(f"Failed to execute command {command_name} from queue: {e}")
        finally:
            self.currently_running_command = None
            
    def _handle_command_completion(self, command_name: str, task: asyncio.Task):
        """Handle command completion and update last_run timestamp only on success"""
        try:
            # Remove from scheduled tasks
            self.scheduled_tasks.pop(command_name, None)
            
            # Check if command completed successfully
            if not task.cancelled() and not task.exception():
                # Command completed successfully, update last_run timestamp
                manager = get_database_manager()
                session = manager.get_session_sync()
                try:
                    command = session.query(CommandConfig).filter(
                        CommandConfig.command_name == command_name
                    ).first()
                    if command:
                        command.last_run = datetime.utcnow()
                        session.commit()
                        self.logger.info(f"Updated last_run timestamp for {command_name}")
                finally:
                    session.close()
            else:
                # Command failed or was cancelled, don't update last_run
                if task.cancelled():
                    self.logger.warning(f"Command {command_name} was cancelled, not updating last_run")
                elif task.exception():
                    self.logger.error(f"Command {command_name} failed: {task.exception()}, not updating last_run")
                    
        except Exception as e:
            self.logger.error(f"Failed to handle completion for {command_name}: {e}")
            
    async def _initialize_scheduled_tasks(self):
        """Initialize scheduled tasks for all enabled commands"""
        try:
            manager = get_database_manager()
            session = manager.get_session_sync()
            try:
                enabled_commands = session.query(CommandConfig).filter(
                    CommandConfig.enabled == True,
                    CommandConfig.schedule_hours.isnot(None)
                ).all()
                
                for command in enabled_commands:
                    self.logger.info(f"Command {command.command_name} is enabled with {command.schedule_hours}h schedule")
                    
            finally:
                session.close()
                
        except Exception as e:
            self.logger.error(f"Failed to initialize scheduled tasks: {e}")
            
    async def enable_command(self, command_name: str):
        """Enable scheduling for a command"""
        try:
            manager = get_database_manager()
            session = manager.get_session_sync()
            try:
                command = session.query(CommandConfig).filter(
                    CommandConfig.command_name == command_name
                ).first()
                
                if command and command.enabled and command.schedule_hours:
                    self.logger.info(f"Command {command_name} enabled - will run every {command.schedule_hours}h")
                    
                    # Immediately check if this command should run now
                    await self._check_command_schedule(command)
                    
            finally:
                session.close()
                
        except Exception as e:
            self.logger.error(f"Failed to enable command {command_name}: {e}")
            
    async def disable_command(self, command_name: str):
        """Disable scheduling for a command"""
        try:
            # Cancel any scheduled execution
            if command_name in self.scheduled_tasks:
                task = self.scheduled_tasks[command_name]
                task.cancel()
                del self.scheduled_tasks[command_name]
                self.logger.info(f"Cancelled scheduled execution for {command_name}")
                
            self.logger.info(f"Command {command_name} disabled - removed from scheduler")
            
        except Exception as e:
            self.logger.error(f"Failed to disable command {command_name}: {e}")
    
    async def update_command_schedule(self, command_name: str):
        """Update scheduling for a command (when schedule_hours changes)"""
        try:
            manager = get_database_manager()
            session = manager.get_session_sync()
            try:
                command = session.query(CommandConfig).filter(
                    CommandConfig.command_name == command_name
                ).first()
                
                if command and command.enabled and command.schedule_hours:
                    self.logger.info(f"Command {command_name} schedule updated - will run every {command.schedule_hours}h")
                    
                    # Immediately check if this command should run now with new schedule
                    await self._check_command_schedule(command)
                else:
                    # Command is disabled, cancel any scheduled execution
                    await self.disable_command(command_name)
                    
            finally:
                session.close()
                
        except Exception as e:
            self.logger.error(f"Failed to update command schedule {command_name}: {e}")
            
    def get_scheduled_commands(self) -> Set[str]:
        """Get list of currently scheduled commands"""
        return set(self.scheduled_tasks.keys())
        
    def is_command_scheduled(self, command_name: str) -> bool:
        """Check if a command is currently scheduled for execution"""
        return command_name in self.scheduled_tasks
    
    def get_queue_status(self) -> Dict[str, Any]:
        """Get current queue status"""
        return {
            'queue_size': self.command_queue.qsize() if self.command_queue else 0,
            'currently_running': self.currently_running_command,
            'scheduled_commands': list(self.scheduled_tasks.keys())
        }


# Global scheduler instance
scheduler = CommandScheduler()
