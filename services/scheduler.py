#!/usr/bin/env python3
"""
Background scheduler service for automatic command execution
"""

import asyncio
import time
from datetime import datetime, timedelta
from typing import Dict, Set, Optional
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
        
    async def start(self):
        """Start the background scheduler"""
        if self.running:
            self.logger.warning("Scheduler is already running")
            return
            
        self.running = True
        self.logger.info("Starting command scheduler")
        
        # Start the main scheduler loop
        self._task = asyncio.create_task(self._scheduler_loop())
        
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
            
            if next_run and datetime.utcnow() >= next_run:
                self.logger.info(f"Scheduling command {command.command_name} for execution")
                await self._schedule_command_execution(command.command_name)
                
        except Exception as e:
            self.logger.error(f"Failed to check schedule for {command.command_name}: {e}")
            
    async def _schedule_command_execution(self, command_name: str):
        """Schedule a command for immediate execution"""
        try:
            # Check if command is already running
            if command_name in self.scheduled_tasks:
                self.logger.warning(f"Command {command_name} is already scheduled")
                return
                
            # Create execution record
            manager = get_database_manager()
            session = manager.get_session_sync()
            try:
                execution = CommandExecution(
                    command_name=command_name,
                    started_at=datetime.utcnow(),
                    triggered_by='scheduler'
                )
                session.add(execution)
                session.commit()
                execution_id = execution.id
                
                # Update command's last_run timestamp
                command = session.query(CommandConfig).filter(
                    CommandConfig.command_name == command_name
                ).first()
                if command:
                    command.last_run = datetime.utcnow()
                    session.commit()
                    
            finally:
                session.close()
                
            # Execute command asynchronously
            task = asyncio.create_task(
                command_executor.execute_command(command_name, triggered_by='scheduler')
            )
            self.scheduled_tasks[command_name] = task
            
            # Clean up task when complete
            task.add_done_callback(lambda t: self.scheduled_tasks.pop(command_name, None))
            
            self.logger.info(f"Scheduled execution of {command_name}")
            
        except Exception as e:
            self.logger.error(f"Failed to schedule command {command_name}: {e}")
            
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


# Global scheduler instance
scheduler = CommandScheduler()
