#!/usr/bin/env python3
"""
Command execution service for FastAPI integration
Handles running commands asynchronously and tracking their status
"""

import asyncio
import time
import traceback
from datetime import datetime
from typing import Dict, Any, Optional
from concurrent.futures import ThreadPoolExecutor

from database.database import get_database_manager
from database.config_models import CommandExecution, CommandConfig
from utils.logger import get_logger


class CommandExecutor:
    """Service for executing commands and tracking their status"""
    
    def __init__(self):
        self.logger = None
        self.config = None
        self.executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="cmdarr-cmd")
        self.running_commands: Dict[str, asyncio.Task] = {}
        self._execution_id_to_task: Dict[int, asyncio.Task] = {}  # For kill_execution
        self.command_classes = None
        self.max_parallel_commands = 1  # Default, will be updated from config
    
    def _ensure_initialized(self):
        """Lazy initialization to avoid circular imports"""
        if self.logger is None:
            self.logger = get_logger('cmdarr.command_executor')
        if self.config is None:
            from commands.config_adapter import Config
            self.config = Config()
            
        # Update max parallel commands from config
        from services.config_service import config_service
        self.max_parallel_commands = config_service.get_int('MAX_PARALLEL_COMMANDS', 1)
        
        # Import command classes
        from commands.discovery_lastfm import DiscoveryLastfmCommand
        from commands.library_cache_builder import LibraryCacheBuilderCommand
        from commands.playlist_sync import PlaylistSyncCommand
        from commands.playlist_sync_discovery_maintenance import PlaylistSyncDiscoveryMaintenanceCommand
        from commands.new_releases_discovery import NewReleasesDiscoveryCommand
        
        if self.command_classes is None:
            self.command_classes = {
                'discovery_lastfm': DiscoveryLastfmCommand,
                'library_cache_builder': LibraryCacheBuilderCommand,
                'playlist_sync_discovery_maintenance': PlaylistSyncDiscoveryMaintenanceCommand,
                'new_releases_discovery': NewReleasesDiscoveryCommand
            }
            
            # Load dynamic playlist sync commands from database
            self._load_dynamic_playlist_sync_commands()
            
            # Clean up any stuck executions on startup
            import asyncio
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    asyncio.create_task(self.cleanup_stuck_executions())
                else:
                    loop.run_until_complete(self.cleanup_stuck_executions())
            except Exception as e:
                self.logger.warning(f"Failed to cleanup stuck executions on startup: {e}")
    
    async def execute_command(self, command_name: str, config_override: Optional[Dict[str, Any]] = None, triggered_by: str = 'manual') -> Dict[str, Any]:
        """
        Execute a command asynchronously
        
        Args:
            command_name: Name of the command to execute
            config_override: Optional configuration overrides
            triggered_by: How the command was triggered ('manual', 'scheduler', 'api')
            
        Returns:
            Dictionary with execution result
        """
        self._ensure_initialized()
        
        # When at capacity, queue for later instead of failing
        if len(self.running_commands) >= self.max_parallel_commands:
            if not hasattr(self, '_pending_queue') or self._pending_queue is None:
                self._pending_queue = asyncio.Queue()
            await self._pending_queue.put((command_name, config_override, triggered_by))
            self.logger.info(f"Command {command_name} queued (at capacity)")
            return {
                'success': True,
                'execution_id': None,
                'message': f'Command {command_name} queued (will run when a slot is available)'
            }
        
        # Check in-memory running commands
        if command_name in self.running_commands:
            return {
                'success': False,
                'error': f'Command {command_name} is already running',
                'execution_id': None
            }
        
        # Check database for running commands (more reliable)
        if await self._is_command_running_in_db(command_name):
            return {
                'success': False,
                'error': f'Command {command_name} is already running (checked database)',
                'execution_id': None
            }
        
        # Verify command still exists in database (prevents execution of deleted commands)
        if not await self._command_exists_in_db(command_name):
            return {
                'success': False,
                'error': f'Command {command_name} not found in database (may have been deleted)',
                'execution_id': None
            }
        
        # Create execution record
        self.logger.info(f"About to create execution record for {command_name} with triggered_by='{triggered_by}'")
        execution_id = await self._create_execution_record(command_name, triggered_by)
        self.logger.info(f"Created execution record with ID: {execution_id}")
        
        # Start command execution in background
        task = asyncio.create_task(
            self._run_command_async(command_name, execution_id, config_override)
        )
        # Add execution_id to task for kill functionality
        task.execution_id = execution_id
        self.running_commands[command_name] = task
        self._execution_id_to_task[execution_id] = task
        
        return {
            'success': True,
            'execution_id': execution_id,
            'message': f'Command {command_name} started successfully'
        }
    
    async def _is_command_running_in_db(self, command_name: str) -> bool:
        """Check if a command is currently running in the database"""
        try:
            db_manager = get_database_manager()
            session = db_manager.get_config_session_sync()
            try:
                running_execution = session.query(CommandExecution).filter(
                    CommandExecution.command_name == command_name,
                    CommandExecution.is_running == True
                ).first()
                return running_execution is not None
            finally:
                session.close()
        except Exception as e:
            self.logger.error(f"Failed to check running commands in database: {e}")
            return False
    
    async def _command_exists_in_db(self, command_name: str) -> bool:
        """Check if a command exists in the database"""
        try:
            db_manager = get_database_manager()
            session = db_manager.get_config_session_sync()
            try:
                # Look for the command configuration
                command_config = session.query(CommandConfig).filter(
                    CommandConfig.command_name == command_name
                ).first()
                
                return command_config is not None
            finally:
                session.close()
        except Exception as e:
            self.logger.error(f"Error checking if command {command_name} exists: {e}")
            return False
    
    async def cleanup_stuck_executions(self, max_duration_hours: int = 2):
        """Clean up executions that have been running too long"""
        try:
            db_manager = get_database_manager()
            session = db_manager.get_config_session_sync()
            try:
                from datetime import datetime, timedelta
                cutoff_time = datetime.utcnow() - timedelta(hours=max_duration_hours)
                
                stuck_executions = session.query(CommandExecution).filter(
                    CommandExecution.is_running == True,
                    CommandExecution.started_at < cutoff_time
                ).all()
                
                for execution in stuck_executions:
                    execution.status = 'failed'
                    execution.completed_at = datetime.utcnow()
                    execution.success = False
                    execution.error_message = f"Command timed out after {max_duration_hours} hours"
                    self.logger.warning(f"Marked stuck execution {execution.id} as timed out")
                
                if stuck_executions:
                    session.commit()
                    self.logger.info(f"Cleaned up {len(stuck_executions)} stuck executions")
                    
            finally:
                session.close()
        except Exception as e:
            self.logger.error(f"Failed to cleanup stuck executions: {e}")
    
    async def _run_command_async(self, command_name: str, execution_id: int, config_override: Optional[Dict[str, Any]] = None):
        """Run command asynchronously and update execution record"""
        self._ensure_initialized()
        start_time = time.time()
        
        try:
            self.logger.info(f"Starting command execution: {command_name} (ID: {execution_id})")
            
            # Get command class
            if command_name not in self.command_classes:
                raise ValueError(f"Unknown command: {command_name}")
            
            command_class = self.command_classes[command_name]
            
            # Create config with overrides if provided
            config = self.config
            # Clear previous run-specific overrides so they don't persist (e.g. artists from scan-artist)
            for key in ('artists', 'source', 'album_types'):
                if hasattr(config, key):
                    delattr(config, key)
            if config_override:
                for key, value in config_override.items():
                    setattr(config, key, value)
            
            # Get command-specific configuration from database
            from database.database import get_database_manager
            manager = get_database_manager()
            session = manager.get_config_session_sync()
            self.logger.info(f"Getting command config for {command_name}")
            try:
                command_config = session.query(CommandConfig).filter(
                    CommandConfig.command_name == command_name
                ).first()
                
                self.logger.info(f"Found command config for {command_name}: {command_config is not None}")
                if command_config:
                    self.logger.info(f"Command config_json: {command_config.config_json}")
                
                # Pass command-specific configuration to config if available
                if command_config and command_config.config_json:
                    # Add command-specific config to the config object
                    for key, value in command_config.config_json.items():
                        setattr(config, f'COMMAND_{command_name.upper()}_{key.upper()}', value)
                
                # Create command instance
                command = command_class(config)
                
                # Pass command-specific configuration to the command
                if command_config and command_config.config_json:
                    command.config_json = command_config.config_json
                    self.logger.info(f"Set config_json for {command_name}: {command_config.config_json}")
                else:
                    self.logger.info(f"No config_json for {command_name}")
                    
            finally:
                session.close()
            
            # Execute command in thread pool (since commands are synchronous)
            loop = asyncio.get_event_loop()
            run_result = await loop.run_in_executor(
                self.executor, 
                self._run_sync_command, 
                command
            )
            success = run_result[0] if isinstance(run_result, tuple) else run_result
            cmd_obj = run_result[1] if isinstance(run_result, tuple) and len(run_result) > 1 else None
            
            duration = time.time() - start_time
            
            # Generate output summary from command result (no log parsing)
            output_summary = self._generate_output_summary(
                command_name, success, duration, command=cmd_obj
            )
            
            # Update execution record
            await self._update_execution_record(
                execution_id, 
                success=success, 
                duration=duration,
                output_summary=output_summary
            )
            
            self.logger.info(f"Command {command_name} completed: {'success' if success else 'failed'} in {duration:.1f}s")
            
        except Exception as e:
            duration = time.time() - start_time
            error_msg = f"Command execution failed: {str(e)}"
            self.logger.error(f"Command {command_name} failed: {error_msg}")
            self.logger.debug(f"Command {command_name} traceback: {traceback.format_exc()}")
            
            # Update execution record with error
            await self._update_execution_record(
                execution_id,
                success=False,
                duration=duration,
                error_message=error_msg
            )
        
        finally:
            # Remove from running commands
            if command_name in self.running_commands:
                task = self.running_commands.pop(command_name)
                self._execution_id_to_task.pop(getattr(task, 'execution_id', None), None)
            # Process next queued command if any
            if hasattr(self, '_pending_queue') and self._pending_queue is not None:
                if len(self.running_commands) < self.max_parallel_commands:
                    try:
                        next_cmd, next_override, next_triggered = self._pending_queue.get_nowait()
                        asyncio.create_task(
                            self.execute_command(next_cmd, next_override, next_triggered)
                        )
                    except asyncio.QueueEmpty:
                        pass
                    except Exception as e:
                        self.logger.warning(f"Failed to start queued command: {e}")
    
    def _run_sync_command(self, command) -> tuple:
        """Run a synchronous command (wrapper for thread pool). Returns (success, command)."""
        self._ensure_initialized()
        try:
            # Check if the command's execute method is async or sync
            import inspect
            execute_method = getattr(command, 'execute', None)
            if execute_method is None:
                raise ValueError("Command has no execute method")
            
            # Check if execute method is a coroutine function
            if inspect.iscoroutinefunction(execute_method):
                # Command is async, run in event loop
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                try:
                    success = loop.run_until_complete(command.execute())
                    return (success, command)
                finally:
                    loop.close()
            else:
                # Command is synchronous, call directly
                success = command.execute()
                return (success, command)
        except Exception as e:
            self.logger.error(f"Sync command execution failed: {e}")
            import traceback
            self.logger.error(f"Traceback: {traceback.format_exc()}")
            return (False, None)
    
    def _generate_output_summary(self, command_name: str, success: bool, duration: float,
                                 command: Any = None) -> str:
        """Generate a summary from command result (no log parsing)"""
        if not success:
            return f"Command failed after {duration:.1f}s"
        
        stats = getattr(command, 'last_run_stats', None) if command else None
        
        if command_name == 'discovery_lastfm' and stats:
            return self._build_lastfm_summary(stats, duration)
        elif command_name == 'library_cache_builder' and stats:
            return self._build_library_cache_summary(stats, duration)
        elif command_name.startswith('playlist_sync_') and stats:
            return self._build_playlist_sync_summary(stats, duration)
        
        return f"Command completed successfully in {duration:.1f}s"
    
    def _build_lastfm_summary(self, stats: Dict[str, Any], duration: float) -> str:
        """Build Last.fm discovery summary from command result"""
        total = stats.get('total_candidates', 0)
        already_in = stats.get('filtered_already_in_lidarr', 0)
        excluded = stats.get('filtered_in_exclusions', 0)
        output = stats.get('final_count', 0)
        
        parts = [f"Last.fm Discovery completed in {duration:.1f}s"]
        if total > 0:
            if output == 0:
                parts.append(f"✅ {total:,} artists detected: {already_in:,} already in Lidarr, {excluded:,} on exclusion list, no new artists to add")
            else:
                parts.append(f"✅ {total:,} artists detected: {already_in:,} already in Lidarr, {excluded:,} on exclusion list, {output:,} new artists ready for import")
        return " • ".join(parts)
    
    def _build_library_cache_summary(self, stats: Dict[str, Any], duration: float) -> str:
        """Build library cache summary from command result"""
        results = stats.get('results', {})
        successful = [t for t, r in results.items() if r.get('success', False)]
        failed = [t for t, r in results.items() if not r.get('success', False)]
        
        parts = [f"Library cache completed in {duration:.1f}s"]
        if successful:
            parts.append(f"Built: {', '.join(successful)}")
        if failed:
            parts.append(f"Failed: {', '.join(failed)}")
        return " • ".join(parts)
    
    def _build_playlist_sync_summary(self, stats: Dict[str, Any], duration: float) -> str:
        """Build playlist sync summary from command result"""
        parts = [f"Playlist Sync completed in {duration:.1f}s"]
        
        # Standard playlist_sync: sync_stats with found_tracks, total_tracks
        sync_stats = stats.get('sync_stats', {})
        if sync_stats:
            found = sync_stats.get('found_tracks', 0)
            total = sync_stats.get('total_tracks', 0)
            action = sync_stats.get('action', '')
            if action == 'additive_sync':
                added = sync_stats.get('added_tracks', 0)
                if added > 0:
                    parts.append(f"{added} tracks added to existing playlist")
                elif total > 0:
                    parts.append(f"{found}/{total} tracks in playlist (no new tracks)")
            elif total > 0:
                rate = (found / total * 100)
                parts.append(f"{found}/{total} tracks matched ({rate:.1f}% success rate)")
            if action and action not in ('synced', 'additive_sync'):
                parts.append(f"Action: {action}")
        else:
            # ListenBrainz: aggregate from sync_results
            found = stats.get('total_tracks_found', 0)
            total = stats.get('total_tracks_attempted', 0)
            sync_time = stats.get('total_sync_time', 0)
            playlists = stats.get('successful_syncs', 0)
            total_playlists = stats.get('total_playlists_configured', 0)
            if total > 0:
                rate = (found / total * 100)
                parts.append(f"{found}/{total} tracks matched ({rate:.1f}% success rate)")
            if total_playlists > 0:
                parts.append(f"{playlists}/{total_playlists} playlists synced in {sync_time:.1f}s")
        
        # Artist discovery
        artist_disc = stats.get('artist_discovery', {})
        if artist_disc:
            added = artist_disc.get('artists_added', 0)
            failed_count = artist_disc.get('artists_failed', 0)
            if added > 0:
                parts.append(f"{added} artists added to Lidarr")
            if failed_count > 0:
                parts.append(f"{failed_count} artists failed")
        
        result = " • ".join(parts)
        
        # Failed matches (from sync_stats or aggregated from sync_results)
        unmatched = []
        if sync_stats:
            unmatched = sync_stats.get('unmatched_tracks', [])
        elif 'sync_results' in stats:
            for r in stats.get('sync_results', {}).values():
                unmatched.extend(r.get('unmatched_tracks', []))
        
        if unmatched:
            display_limit = 25
            to_show = unmatched[:display_limit]
            result += "\n\nFailed matches:\n" + "\n".join(f"• {t}" for t in to_show)
            if len(unmatched) > display_limit:
                result += f"\n... and {len(unmatched) - display_limit} more"
        
        return result
    
    async def _create_execution_record(self, command_name: str, triggered_by: str = 'manual') -> int:
        """Create a new command execution record in the database"""
        try:
            self.logger.info(f"Creating execution record for {command_name} with triggered_by='{triggered_by}'")
            db_manager = get_database_manager()
            session = db_manager.get_config_session_sync()
            try:
                execution = CommandExecution(
                    command_name=command_name,
                    triggered_by=triggered_by,
                    status='running',
                    started_at=datetime.utcnow()
                )
                session.add(execution)
                session.commit()
                session.refresh(execution)
                return execution.id
            finally:
                session.close()
        except Exception as e:
            self.logger.error(f"Failed to create execution record: {e}")
            raise

    async def _update_execution_record(self, execution_id: int, success: bool, duration: float,
                                     output_summary: Optional[str] = None, error_message: Optional[str] = None) -> None:
        """Update command execution record with results"""
        try:
            db_manager = get_database_manager()
            session = db_manager.get_config_session_sync()
            try:
                execution = session.query(CommandExecution).filter(
                    CommandExecution.id == execution_id
                ).first()
                if execution:
                    execution.status = 'completed' if success else 'failed'
                    execution.success = success
                    execution.duration = duration
                    execution.completed_at = datetime.utcnow()
                    if output_summary:
                        execution.output_summary = output_summary
                    if error_message:
                        execution.error_message = error_message
                    
                    # Also update the CommandConfig with last run information
                    command_config = session.query(CommandConfig).filter(
                        CommandConfig.command_name == execution.command_name
                    ).first()
                    if command_config:
                        command_config.last_run = datetime.utcnow()
                        command_config.last_success = success
                        command_config.last_duration = duration
                        if error_message:
                            command_config.last_error = error_message
                        else:
                            command_config.last_error = None
                    
                    session.commit()
            finally:
                session.close()
        except Exception as e:
            self.logger.error(f"Failed to update execution record: {e}")
    
    def kill_execution(self, execution_id: int) -> bool:
        """
        Cancel a running command execution by cancelling its asyncio task.
        Returns True if the task was found and cancelled, False otherwise.
        Note: The underlying thread may continue until it checks for cancellation;
        the DB is updated by the API before this is called.
        """
        self._ensure_initialized()
        task = self._execution_id_to_task.get(execution_id)
        if task and not task.done():
            task.cancel()
            self.logger.info(f"Cancelled execution {execution_id}")
            return True
        return False
    
    async def cleanup_stuck_executions(self, max_duration_hours: int = 2):
        """Clean up executions that have been running too long"""
        try:
            db_manager = get_database_manager()
            session = db_manager.get_config_session_sync()
            try:
                from datetime import datetime, timedelta
                cutoff_time = datetime.utcnow() - timedelta(hours=max_duration_hours)
                
                stuck_executions = session.query(CommandExecution).filter(
                    CommandExecution.is_running == True,
                    CommandExecution.started_at < cutoff_time
                ).all()
                
                for execution in stuck_executions:
                    execution.status = 'failed'
                    execution.success = False
                    execution.completed_at = datetime.utcnow()
                    execution.error_message = f"Execution stuck for more than {max_duration_hours} hours"
                
                if stuck_executions:
                    session.commit()
                    self.logger.info(f"Cleaned up {len(stuck_executions)} stuck executions")
            finally:
                session.close()
        except Exception as e:
            self.logger.error(f"Failed to cleanup stuck executions: {e}")
    def _load_dynamic_playlist_sync_commands(self):
        """Load dynamic playlist sync commands from database"""
        try:
            db_manager = get_database_manager()
            session = db_manager.get_config_session_sync()
            try:
                # Get all playlist sync commands from database
                playlist_sync_commands = session.query(CommandConfig).filter(
                    CommandConfig.command_name.like('playlist_sync_%')
                ).filter(
                    CommandConfig.command_name != 'playlist_sync_discovery_maintenance'  # Exclude maintenance command
                ).all()
                
                for command_config in playlist_sync_commands:
                    command_name = command_config.command_name
                    config_json = command_config.config_json or {}
                    source = config_json.get('source', 'unknown')
                    
                    try:
                        # Determine command class based on source
                        if source == 'listenbrainz':
                            from commands.playlist_sync_listenbrainz import PlaylistSyncListenBrainzCommand
                            command_class = PlaylistSyncListenBrainzCommand
                        else:
                            # External sources (spotify, etc.)
                            from commands.playlist_sync import PlaylistSyncCommand
                            command_class = PlaylistSyncCommand
                        
                        # Create command instance
                        command = command_class(self.config)
                        command.config_json = config_json
                        
                        # Add to command classes
                        self.command_classes[command_name] = command_class
                        
                        self.logger.debug(f"Loaded dynamic playlist sync command: {command_name} (source: {source})")
                        
                    except Exception as e:
                        self.logger.error(f"Failed to load individual command {command_name}: {e}")
                        import traceback
                        self.logger.error(f"Traceback: {traceback.format_exc()}")
                        continue
                    
            finally:
                session.close()
                
        except Exception as e:
            self.logger.error(f"Failed to load dynamic playlist sync commands: {e}")
            import traceback
            self.logger.error(f"Traceback: {traceback.format_exc()}")

    async def wait_for_running_commands(self, timeout_seconds: float = 300) -> bool:
        """
        Wait for all running commands to complete (graceful shutdown).
        Returns True if all completed within timeout, False if timeout reached.
        """
        self._ensure_initialized()
        if not self.running_commands:
            return True
        tasks = list(self.running_commands.values())
        names = list(self.running_commands.keys())
        self.logger.info(f"Graceful shutdown: waiting up to {timeout_seconds}s for {len(tasks)} running command(s): {names}")
        try:
            done, pending = await asyncio.wait(tasks, timeout=timeout_seconds, return_when=asyncio.ALL_COMPLETED)
            if pending:
                self.logger.warning(f"Graceful shutdown timeout: {len(pending)} command(s) still running after {timeout_seconds}s")
                for t in pending:
                    t.cancel()
                return False
            self.logger.info("Graceful shutdown: all running commands completed")
            return True
        except Exception as e:
            self.logger.error(f"Error waiting for commands: {e}")
            return False

    async def get_command_status(self, command_name: str) -> Dict[str, Any]:
        """Get current status of a command"""
        try:
            # Check if command is currently running
            is_running = command_name in self.running_commands
            
            # Get last execution from database
            last_execution = None
            try:
                db_manager = get_database_manager()
                session = db_manager.get_config_session_sync()
                try:
                    execution = session.query(CommandExecution).filter(
                        CommandExecution.command_name == command_name
                    ).order_by(CommandExecution.started_at.desc()).first()
                    
                    if execution:
                        last_execution = {
                            "id": execution.id,
                            "started_at": execution.started_at.isoformat() + 'Z',
                            "completed_at": execution.completed_at.isoformat() + 'Z' if execution.completed_at else None,
                            "success": execution.success,
                            "status": execution.status,
                            "duration": execution.duration,
                            "error_message": execution.error_message,
                            "triggered_by": execution.triggered_by,
                            "is_running": execution.is_running
                        }
                finally:
                    session.close()
            except Exception as e:
                self.logger.warning(f"Failed to get last execution for {command_name}: {e}")
            
            return {
                "is_running": is_running,
                "last_execution": last_execution
            }
            
        except Exception as e:
            self.logger.error(f"Failed to get command status for {command_name}: {e}")
            return {
                "is_running": False,
                "last_execution": None
            }


# Global instance
command_executor = CommandExecutor()
