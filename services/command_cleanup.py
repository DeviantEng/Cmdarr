#!/usr/bin/env python3
"""
Command cleanup service for Cmdarr
Handles stuck commands, timeouts, and cleanup tasks
"""

import asyncio
from datetime import datetime, timedelta, timezone

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
                await self.cleanup_expired_commands()
                # Run execution history cleanup only at 2am (scheduler timezone)
                if self._is_cleanup_hour():
                    await self.cleanup_old_executions()
                    await self.cleanup_soft_deleted_commands()
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

    async def cleanup_expired_commands(self):
        """
        Disable commands whose expires_at (in config_json) has passed.
        For playlist commands, optionally delete the playlist from target.
        """
        try:
            from database.database import get_database_manager

            manager = get_database_manager()
            db = manager.get_config_session_sync()

            try:
                now = datetime.utcnow()
                all_commands = db.query(CommandConfig).all()
                expired = []
                for cmd in all_commands:
                    cfg = cmd.config_json or {}
                    exp_str = cfg.get("expires_at")
                    if not exp_str:
                        continue
                    try:
                        s = str(exp_str).strip().replace("Z", "+00:00")
                        exp_dt = datetime.fromisoformat(s)
                        if exp_dt.tzinfo:
                            exp_dt = exp_dt.astimezone(timezone.utc).replace(tzinfo=None)
                        if exp_dt <= now:
                            expired.append(cmd)
                    except (ValueError, TypeError):
                        continue

                if not expired:
                    return

                for cmd in expired:
                    try:
                        self._run_expiry_cleanup(cmd)
                    except Exception as e:
                        logger.warning(f"Expiry cleanup for {cmd.command_name} failed: {e}")

                    cmd.enabled = False
                    if cmd.config_json:
                        cfg = dict(cmd.config_json)
                        cfg.pop("expires_at", None)
                        cmd.config_json = cfg
                    logger.info(f"Disabled expired command: {cmd.command_name}")

                db.commit()
                logger.info(f"Processed {len(expired)} expired command(s)")
            finally:
                db.close()

        except Exception as e:
            logger.error(f"Failed to cleanup expired commands: {e}")

    def _run_expiry_cleanup(self, command_config: CommandConfig):
        """
        Run command-specific cleanup on expiry (e.g. delete playlist).
        Called synchronously from cleanup_expired_commands.
        Only deletes playlist when expires_at_delete_playlist is True (default).
        """
        cfg = command_config.config_json or {}
        name = command_config.command_name or ""
        delete_playlist = cfg.get("expires_at_delete_playlist", True)

        if not delete_playlist:
            return

        if name.startswith("playlist_sync_"):
            target = str(cfg.get("target", "plex")).lower()
            playlist_name = f"[{str(cfg.get('source', 'unknown')).title()}] {cfg.get('playlist_name', '')}"
            self._delete_playlist_if_exists(target, playlist_name)
        elif name.startswith("top_tracks_"):
            target = str(cfg.get("target", "plex")).lower()
            playlist_name = f"[Cmdarr Top Tracks] {cfg.get('playlist_name', 'Artists Top Tracks')}"
            self._delete_playlist_if_exists(target, playlist_name)
        elif name.startswith("daylist_"):
            playlist_name = "Cmdarr's Daylist"
            self._delete_playlist_if_exists("plex", playlist_name)

    def _delete_playlist_if_exists(self, target: str, playlist_name: str):
        """Delete playlist from Plex or Jellyfin if it exists."""
        try:
            from commands.config_adapter import Config

            config = Config()
            if target == "plex":
                from clients.client_plex import PlexClient

                client = PlexClient(config)
                pl = client.find_playlist_by_name(playlist_name)
                if pl and pl.get("ratingKey"):
                    client.delete_playlist(pl["ratingKey"])
                    logger.info(f"Deleted expired playlist from Plex: {playlist_name}")
            elif target == "jellyfin":
                from clients.client_jellyfin import JellyfinClient

                client = JellyfinClient(config)
                pl = client.find_playlist_by_name(playlist_name)
                if pl and pl.get("Id"):
                    if hasattr(client, "delete_playlist_sync"):
                        client.delete_playlist_sync(pl["Id"])
                        logger.info(f"Deleted expired playlist from Jellyfin: {playlist_name}")
        except Exception as e:
            logger.warning(f"Could not delete playlist {playlist_name}: {e}")

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

    async def cleanup_soft_deleted_commands(self):
        """Permanently delete commands that were soft-deleted more than 7 days ago."""
        try:
            from sqlalchemy.exc import OperationalError

            from database.database import get_database_manager

            manager = get_database_manager()
            db = manager.get_config_session_sync()

            try:
                cutoff = datetime.utcnow() - timedelta(days=7)
                to_delete = (
                    db.query(CommandConfig)
                    .filter(
                        CommandConfig.deleted_at.isnot(None),
                        CommandConfig.deleted_at < cutoff,
                    )
                    .all()
                )
                for cmd in to_delete:
                    db.delete(cmd)
                if to_delete:
                    db.commit()
                    logger.info(f"Permanently deleted {len(to_delete)} soft-deleted command(s)")
            finally:
                db.close()

        except OperationalError as e:
            # Column may not exist yet if migration hasn't run (e.g. pre-0.3.7)
            if "deleted_at" in str(e).lower():
                logger.debug("Skipping soft-delete cleanup (deleted_at column not yet migrated)")
            else:
                logger.error(f"Failed to cleanup soft-deleted commands: {e}")
        except Exception as e:
            logger.error(f"Failed to cleanup soft-deleted commands: {e}")

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
                        db.query(CommandConfig)
                        .filter(
                            CommandConfig.command_name == cmd,
                            CommandConfig.deleted_at.is_(None),
                        )
                        .first()
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
