#!/usr/bin/env python3
"""
Background scheduler service for automatic command execution (cron-based)
"""

import asyncio
import os
from datetime import datetime, timedelta, timezone
from typing import Dict, Set, Optional, Any, List, Tuple

from croniter import croniter
from database.database import get_database_manager
from database.config_models import CommandConfig
from services.command_executor import command_executor
from services.config_service import config_service
from utils.logger import get_logger
from utils.timezone import get_scheduler_timezone as _get_scheduler_timezone, get_utc_now


def _get_next_run_cron(cron_expr: str, tz) -> Optional[datetime]:
    """Get next run time from cron expression. Returns timezone-aware datetime in UTC."""
    try:
        now = datetime.now(tz)
        itr = croniter(cron_expr, now)
        next_local = itr.get_next(datetime)
        return next_local.astimezone(timezone.utc)
    except Exception:
        return None


def get_effective_cron(command: CommandConfig) -> Optional[str]:
    """Get cron expression for command: per-command override or global default."""
    if command.schedule_cron and command.schedule_cron.strip():
        return command.schedule_cron.strip()
    default = config_service.get('DEFAULT_SCHEDULE_CRON') or '0 3 * * *'
    return default.strip() if default else '0 3 * * *'


def calculate_next_run_cron(command: CommandConfig, tz) -> Optional[datetime]:
    """Calculate next run time for command using cron. Returns UTC datetime."""
    cron_expr = get_effective_cron(command)
    if not cron_expr:
        return None
    return _get_next_run_cron(cron_expr, tz)


class CommandScheduler:
    """Background scheduler for automatic command execution (cron-based)"""

    def __init__(self):
        self.logger = get_logger('cmdarr.scheduler')
        self.running = False
        self.scheduled_tasks: Dict[str, asyncio.Task] = {}
        self.check_interval = 60  # Check every 60 seconds
        self._task: Optional[asyncio.Task] = None

        # Command queue: items are (command_id, command_name) for ordering by id
        self.command_queue: Optional[asyncio.Queue] = None
        self.queue_processor_tasks: List[asyncio.Task] = []
        self.currently_running: Set[str] = set()

    def _get_max_concurrent(self) -> int:
        return max(1, config_service.get_int('MAX_PARALLEL_COMMANDS', 1))

    async def start(self):
        """Start the background scheduler"""
        if self.running:
            self.logger.warning("Scheduler is already running")
            return

        self.running = True
        self.logger.info("Starting command scheduler (cron-based)")

        self.command_queue = asyncio.Queue()

        self._task = asyncio.create_task(self._scheduler_loop())

        max_concurrent = self._get_max_concurrent()
        self.queue_processor_tasks = [
            asyncio.create_task(self._process_command_queue())
            for _ in range(max_concurrent)
        ]
        self.logger.info(f"Started {max_concurrent} queue worker(s)")

        await self._log_enabled_commands()

    async def stop(self):
        """Stop the background scheduler"""
        if not self.running:
            return

        self.running = False
        self.logger.info("Stopping command scheduler")

        for task in self.scheduled_tasks.values():
            task.cancel()
        self.scheduled_tasks.clear()

        for task in self.queue_processor_tasks:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
        self.queue_processor_tasks.clear()

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

    MAINTENANCE_COMMAND = 'playlist_sync_discovery_maintenance'
    MAINTENANCE_PREREQ_HOURS = 24  # Run maintenance before playlist sync if not run in last 24h

    async def _check_and_execute_commands(self):
        """Check all enabled commands and queue those due to run (ordered by command id)."""
        try:
            manager = get_database_manager()
            session = manager.get_config_session_sync()
            try:
                enabled_commands = session.query(CommandConfig).filter(
                    CommandConfig.enabled == True
                ).order_by(CommandConfig.id).all()

                tz = _get_scheduler_timezone()
                now_utc = get_utc_now()

                due_commands: List[Tuple[int, str]] = []  # (id, command_name)

                for command in enabled_commands:
                    cron_expr = get_effective_cron(command)
                    if not cron_expr:
                        continue
                    next_run = calculate_next_run_cron(command, tz)
                    if next_run and now_utc >= next_run:
                        due_commands.append((command.id, command.command_name))

                # If any playlist sync is due, ensure maintenance runs first if enabled and not run in 24h
                has_playlist_sync_due = any(
                    name.startswith('playlist_sync_') and name != self.MAINTENANCE_COMMAND
                    for _, name in due_commands
                )
                if has_playlist_sync_due:
                    maintenance = next(
                        (c for c in enabled_commands if c.command_name == self.MAINTENANCE_COMMAND),
                        None
                    )
                    if maintenance:
                        last_run = maintenance.last_run
                        cutoff = now_utc - timedelta(hours=self.MAINTENANCE_PREREQ_HOURS)
                        if last_run is None:
                            needs_maintenance = True
                        else:
                            last_run_utc = (
                                last_run.astimezone(timezone.utc)
                                if last_run.tzinfo
                                else last_run.replace(tzinfo=timezone.utc)
                            )
                            needs_maintenance = last_run_utc < cutoff
                        if needs_maintenance:
                            already_queued = any(name == self.MAINTENANCE_COMMAND for _, name in due_commands)
                            if not already_queued:
                                due_commands.insert(0, (maintenance.id, maintenance.command_name))
                                self.logger.info(
                                    f"Queuing {self.MAINTENANCE_COMMAND} before playlist sync "
                                    f"(last run {last_run or 'never'})"
                                )

                # Sort by id and queue in order
                due_commands.sort(key=lambda x: x[0])
                for cmd_id, cmd_name in due_commands:
                    await self._queue_command_execution(cmd_id, cmd_name)

            finally:
                session.close()

        except Exception as e:
            self.logger.error(f"Failed to check command schedules: {e}")

    async def _queue_command_execution(self, command_id: int, command_name: str):
        """Add a command to the execution queue."""
        try:
            if command_name in self.scheduled_tasks or command_name in self.currently_running:
                self.logger.debug(f"Command {command_name} already queued or running, skipping")
                return

            await self.command_queue.put((command_id, command_name))
            self.logger.info(f"Queued command {command_name} (id={command_id}) for execution")

        except Exception as e:
            self.logger.error(f"Failed to queue command {command_name}: {e}")

    async def _process_command_queue(self):
        """Worker: process commands from the queue."""
        while self.running:
            try:
                item = await self.command_queue.get()
                if not self.running:
                    break

                command_id, command_name = item
                self.logger.info(f"Worker processing command {command_name}")

                self.currently_running.add(command_name)
                try:
                    task = asyncio.create_task(
                        command_executor.execute_command(command_name, triggered_by='scheduler')
                    )
                    self.scheduled_tasks[command_name] = task
                    task.add_done_callback(lambda t, cn=command_name: self._handle_command_completion(cn, t))
                    await task
                finally:
                    self.currently_running.discard(command_name)
                    self.scheduled_tasks.pop(command_name, None)

                self.command_queue.task_done()

            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"Error processing command queue: {e}")
                await asyncio.sleep(5)

    def _handle_command_completion(self, command_name: str, task: asyncio.Task):
        """Handle command completion and update last_run only on success."""
        try:
            self.scheduled_tasks.pop(command_name, None)
            self.currently_running.discard(command_name)

            if not task.cancelled() and not task.exception():
                manager = get_database_manager()
                session = manager.get_config_session_sync()
                try:
                    command = session.query(CommandConfig).filter(
                        CommandConfig.command_name == command_name
                    ).first()
                    if command:
                        command.last_run = get_utc_now()
                        session.commit()
                        self.logger.info(f"Updated last_run for {command_name}")
                finally:
                    session.close()
            else:
                if task.cancelled():
                    self.logger.warning(f"Command {command_name} was cancelled")
                elif task.exception():
                    self.logger.error(f"Command {command_name} failed: {task.exception()}")

        except Exception as e:
            self.logger.error(f"Failed to handle completion for {command_name}: {e}")

    async def _log_enabled_commands(self):
        """Log enabled commands at startup."""
        try:
            manager = get_database_manager()
            session = manager.get_config_session_sync()
            try:
                enabled = session.query(CommandConfig).filter(
                    CommandConfig.enabled == True
                ).all()
                tz = _get_scheduler_timezone()
                default_cron = config_service.get('DEFAULT_SCHEDULE_CRON') or '0 3 * * *'
                self.logger.info(f"Scheduler timezone: {tz}, default cron: {default_cron}")
                for cmd in enabled:
                    cron = get_effective_cron(cmd)
                    next_run = calculate_next_run_cron(cmd, tz)
                    self.logger.info(f"  {cmd.display_name}: cron={cron}, next_run={next_run}")
            finally:
                session.close()
        except Exception as e:
            self.logger.error(f"Failed to log enabled commands: {e}")

    async def enable_command(self, command_name: str):
        """Enable scheduling for a command - check if it should run now."""
        try:
            manager = get_database_manager()
            session = manager.get_config_session_sync()
            try:
                command = session.query(CommandConfig).filter(
                    CommandConfig.command_name == command_name
                ).first()

                if command and command.enabled:
                    cron = get_effective_cron(command)
                    self.logger.info(f"Command {command_name} enabled, cron={cron}")
                    tz = _get_scheduler_timezone()
                    next_run = calculate_next_run_cron(command, tz)
                    now_utc = get_utc_now()
                    if next_run and now_utc >= next_run:
                        await self._queue_command_execution(command.id, command_name)
            finally:
                session.close()

        except Exception as e:
            self.logger.error(f"Failed to enable command {command_name}: {e}")

    async def disable_command(self, command_name: str):
        """Disable scheduling for a command."""
        try:
            if command_name in self.scheduled_tasks:
                task = self.scheduled_tasks[command_name]
                task.cancel()
                self.scheduled_tasks.pop(command_name, None)
                self.logger.info(f"Cancelled execution for {command_name}")
            self.logger.info(f"Command {command_name} disabled")
        except Exception as e:
            self.logger.error(f"Failed to disable command {command_name}: {e}")

    async def update_command_schedule(self, command_name: str):
        """Update scheduling when schedule_cron changes."""
        await self.enable_command(command_name)

    def get_scheduled_commands(self) -> Set[str]:
        """Get list of commands currently queued or running."""
        return set(self.scheduled_tasks.keys()) | self.currently_running

    def is_command_scheduled(self, command_name: str) -> bool:
        """Check if a command is queued or running."""
        return command_name in self.scheduled_tasks or command_name in self.currently_running

    def get_queue_status(self) -> Dict[str, Any]:
        """Get current queue status."""
        return {
            'queue_size': self.command_queue.qsize() if self.command_queue else 0,
            'currently_running': list(self.currently_running),
            'scheduled_commands': list(self.scheduled_tasks.keys()),
        }


scheduler = CommandScheduler()
