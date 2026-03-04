#!/usr/bin/env python3
"""
Command cleanup service for Cmdarr
Handles stuck commands, timeouts, and cleanup tasks
"""

import asyncio
from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from database.config_models import CommandConfig, CommandExecution
from utils.logger import get_logger

logger = get_logger("cmdarr.command_cleanup")


class CommandCleanupService:
    """Service for cleaning up stuck and timed-out commands"""

    def __init__(self):
        self.cleanup_interval = 300  # 5 minutes
        self.cleanup_task: asyncio.Task | None = None

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
                # Run execution history cleanup only at 2am (scheduler timezone)
                if self._is_cleanup_hour():
                    await self.cleanup_old_executions()
                await asyncio.sleep(self.cleanup_interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in cleanup loop: {e}")
                await asyncio.sleep(60)  # Wait 1 minute before retrying

    def _is_cleanup_hour(self) -> bool:
        """True if current hour is 2am in scheduler timezone (for daily execution cleanup)"""
        try:
            from utils.timezone import get_scheduler_timezone

            tz = get_scheduler_timezone()
            now = datetime.now(tz)
            return now.hour == 2
        except Exception:
            return False

    async def cleanup_stuck_commands(self):
        """Clean up commands that have been running for too long without a timeout"""
        try:
            from database.database import get_database_manager

            manager = get_database_manager()
            db = manager.get_session_sync()

            # Find commands running for more than 2 hours without a timeout
            cutoff_time = datetime.utcnow() - timedelta(hours=2)
            stuck_commands = (
                db.query(CommandExecution)
                .filter(
                    CommandExecution.status == "running", CommandExecution.started_at < cutoff_time
                )
                .all()
            )

            for execution in stuck_commands:
                await self._mark_command_failed(
                    execution, "Command timed out after 2 hours (no timeout configured)", db
                )
                logger.warning(
                    f"Marked stuck command {execution.command_name} (ID: {execution.id}) as failed"
                )

            if stuck_commands:
                db.commit()
                logger.info(f"Cleaned up {len(stuck_commands)} stuck commands")

        except Exception as e:
            logger.error(f"Failed to cleanup stuck commands: {e}")
        finally:
            if "db" in locals():
                db.close()

    async def cleanup_timed_out_commands(self):
        """Clean up commands that have exceeded their configured timeout"""
        try:
            from database.database import get_database_manager

            manager = get_database_manager()
            db = manager.get_session_sync()

            # Find running commands with timeouts
            running_commands = (
                db.query(CommandExecution).filter(CommandExecution.status == "running").all()
            )

            timed_out_count = 0
            for execution in running_commands:
                # Get the command config to check timeout
                command_config = (
                    db.query(CommandConfig)
                    .filter(CommandConfig.command_name == execution.command_name)
                    .first()
                )

                if command_config and command_config.timeout_minutes:
                    timeout_delta = timedelta(minutes=command_config.timeout_minutes)
                    if execution.started_at < datetime.utcnow() - timeout_delta:
                        await self._mark_command_failed(
                            execution,
                            f"Command timed out after {command_config.timeout_minutes} minutes",
                            db,
                        )
                        timed_out_count += 1
                        logger.warning(
                            f"Command {execution.command_name} (ID: {execution.id}) timed out after {command_config.timeout_minutes} minutes"
                        )

            if timed_out_count > 0:
                db.commit()
                logger.info(f"Cleaned up {timed_out_count} timed out commands")

        except Exception as e:
            logger.error(f"Failed to cleanup timed out commands: {e}")
        finally:
            if "db" in locals():
                db.close()

    async def cleanup_startup_stuck_commands(self) -> list[str]:
        """
        Clean up any commands that were running when the application was shut down.
        Returns list of unique command names to retry (for restart-retry feature).
        """
        commands_to_retry: list[str] = []
        try:
            from database.database import get_database_manager

            manager = get_database_manager()
            db = manager.get_session_sync()

            # Find all commands that were running (likely from previous app instance)
            stuck_commands = (
                db.query(CommandExecution).filter(CommandExecution.status == "running").all()
            )

            for execution in stuck_commands:
                await self._mark_command_failed(
                    execution, "Command was running when application restarted", db
                )
                logger.info(
                    f"Marked startup stuck command {execution.command_name} (ID: {execution.id}) as failed"
                )
                if execution.command_name not in commands_to_retry:
                    commands_to_retry.append(execution.command_name)

            if stuck_commands:
                db.commit()
                logger.info(f"Cleaned up {len(stuck_commands)} startup stuck commands")

        except Exception as e:
            logger.error(f"Failed to cleanup startup stuck commands: {e}")
        finally:
            if "db" in locals():
                db.close()

        return commands_to_retry

    async def _mark_command_failed(self, execution: CommandExecution, reason: str, db: Session):
        """Mark a command execution as failed"""
        execution.status = "failed"
        execution.completed_at = datetime.utcnow()
        execution.success = False
        execution.error_message = reason

        if execution.started_at:
            execution.duration = (execution.completed_at - execution.started_at).total_seconds()

        # Update aggregate stats on CommandConfig
        command_config = (
            db.query(CommandConfig)
            .filter(CommandConfig.command_name == execution.command_name)
            .first()
        )
        if command_config:
            command_config.total_execution_count = (command_config.total_execution_count or 0) + 1
            command_config.total_failure_count = (command_config.total_failure_count or 0) + 1

    async def get_running_commands(self) -> list[dict]:
        """Get all currently running commands as plain dicts (avoids detached ORM issues)"""
        try:
            from database.database import get_database_manager

            manager = get_database_manager()
            db = manager.get_session_sync()
            try:
                executions = (
                    db.query(CommandExecution).filter(CommandExecution.status == "running").all()
                )
                return [
                    {
                        "id": e.id,
                        "command_name": e.command_name,
                        "started_at": e.started_at.isoformat() if e.started_at else None,
                        "status": e.status,
                    }
                    for e in executions
                ]
            finally:
                db.close()
        except Exception as e:
            logger.error(f"Failed to get running commands: {e}")
            return []

    async def cleanup_old_executions(self, keep_count: int | None = None):
        """Clean up old command executions, keeping only the most recent ones per command"""
        try:
            # Get retention count from config if not provided
            if keep_count is None:
                from services.config_service import config_service

                keep_count = config_service.get_int("COMMAND_CLEANUP_RETENTION", 50)

            from database.database import get_database_manager

            manager = get_database_manager()
            db = manager.get_session_sync()

            try:
                # Single query: fetch all executions ordered by command_name, started_at DESC
                executions = (
                    db.query(CommandExecution)
                    .order_by(
                        CommandExecution.command_name,
                        CommandExecution.started_at.desc(),
                    )
                    .all()
                )

                # Group by command, keep top keep_count per command, collect rest for deletion
                from collections import defaultdict

                kept_per_command: dict[str, int] = defaultdict(int)
                to_delete: list[CommandExecution] = []

                for execution in executions:
                    cmd = execution.command_name
                    if kept_per_command[cmd] < keep_count:
                        kept_per_command[cmd] += 1
                    else:
                        to_delete.append(execution)

                for execution in to_delete:
                    db.delete(execution)

                if to_delete:
                    db.commit()
                    logger.info(f"Cleaned up {len(to_delete)} old executions across all commands")
            finally:
                db.close()

        except Exception as e:
            logger.error(f"Failed to cleanup old executions: {e}")

    async def force_cleanup_all_running(self):
        """Force cleanup all running commands (emergency function)"""
        try:
            from database.database import get_database_manager

            manager = get_database_manager()
            db = manager.get_session_sync()

            running_commands = (
                db.query(CommandExecution).filter(CommandExecution.status == "running").all()
            )

            for execution in running_commands:
                await self._mark_command_failed(
                    execution, "Force cleaned up - all running commands cleared", db
                )

            if running_commands:
                db.commit()
                logger.warning(f"Force cleaned up {len(running_commands)} running commands")

        except Exception as e:
            logger.error(f"Failed to force cleanup running commands: {e}")
        finally:
            if "db" in locals():
                db.close()

    async def run_restart_retries(self, command_names: list[str], delay_seconds: float = 10):
        """
        Retry commands that were interrupted by restart. Runs after a short delay to let the app stabilize.
        Executes one at a time, waiting for each to complete before starting the next.
        """
        if not command_names:
            return
        try:
            from services.config_service import config_service

            enabled = config_service.get("RESTART_RETRY_ENABLED", "true")
            if str(enabled).lower() in ("false", "0", "no"):
                logger.info("Restart retry disabled by config, skipping")
                return
        except Exception:
            pass  # Default to enabled if config fails

        # Exclude library_cache_builder: full rebuild uses significant memory and can cause OOM.
        # If interrupted, retrying immediately may trigger another OOM loop. Let next scheduled run handle it.
        if "library_cache_builder" in command_names:
            logger.info(
                "Restart retry: excluding library_cache_builder (will run on next schedule)"
            )
        command_names = [c for c in command_names if c != "library_cache_builder"]
        if not command_names:
            logger.info("Restart retry: no commands to retry")
            return

        logger.info(
            f"Restart retry: will retry {len(command_names)} command(s) in {delay_seconds}s: {command_names}"
        )
        await asyncio.sleep(delay_seconds)

        from database.database import get_database_manager
        from services.command_executor import command_executor

        for cmd in command_names:
            try:
                # Verify command still exists (could have been deleted)
                manager = get_database_manager()
                db = manager.get_config_session_sync()
                try:
                    from database.config_models import CommandConfig

                    exists = (
                        db.query(CommandConfig).filter(CommandConfig.command_name == cmd).first()
                        is not None
                    )
                finally:
                    db.close()

                if not exists:
                    logger.warning(f"Restart retry: skipping {cmd} (command no longer exists)")
                    continue

                logger.info(f"Restart retry: executing {cmd}")
                result = await command_executor.execute_command(cmd, triggered_by="restart_retry")
                if not result.get("success"):
                    logger.warning(
                        f"Restart retry: could not start {cmd}: {result.get('error', 'unknown')}"
                    )
                    continue

                # Wait for this command to complete before starting the next
                while cmd in command_executor.running_commands:
                    await asyncio.sleep(5)
                logger.info(f"Restart retry: {cmd} completed")
            except Exception as e:
                logger.error(f"Restart retry failed for {cmd}: {e}")

        logger.info("Restart retry: all retries completed")


# Global cleanup service instance
command_cleanup = CommandCleanupService()
