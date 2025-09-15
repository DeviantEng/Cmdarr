#!/usr/bin/env python3
"""
Command execution service for FastAPI integration
Handles running commands asynchronously and tracking their status
"""

import asyncio
import os
import time
import traceback
from datetime import datetime
from typing import Dict, Any, Optional
from concurrent.futures import ThreadPoolExecutor

from database.database import get_database_manager
from database.models import CommandExecution, CommandConfig
from utils.logger import get_logger


class CommandExecutor:
    """Service for executing commands and tracking their status"""
    
    def __init__(self):
        self.logger = None
        self.config = None
        self.executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="cmdarr-cmd")
        self.running_commands: Dict[str, asyncio.Task] = {}
        self.command_classes = None
    
    def _ensure_initialized(self):
        """Lazy initialization to avoid circular imports"""
        if self.logger is None:
            self.logger = get_logger('cmdarr.command_executor')
        if self.config is None:
            from commands.config_adapter import Config
            self.config = Config()
        if self.command_classes is None:
            from commands.discovery_lastfm import DiscoveryLastfmCommand
            from commands.discovery_listenbrainz import DiscoveryListenbrainzCommand
            from commands.playlist_sync_listenbrainz_curated import PlaylistSyncListenBrainzCuratedCommand
            from commands.library_cache_builder import LibraryCacheBuilderCommand
            
            self.command_classes = {
                'discovery_lastfm': DiscoveryLastfmCommand,
                'discovery_listenbrainz': DiscoveryListenbrainzCommand,
                'playlist_sync_listenbrainz_curated': PlaylistSyncListenBrainzCuratedCommand,
                'library_cache_builder': LibraryCacheBuilderCommand
            }
            
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
        
        return {
            'success': True,
            'execution_id': execution_id,
            'message': f'Command {command_name} started successfully'
        }
    
    async def _is_command_running_in_db(self, command_name: str) -> bool:
        """Check if a command is currently running in the database"""
        try:
            db_manager = get_database_manager()
            session = db_manager.get_session_sync()
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
    
    async def cleanup_stuck_executions(self, max_duration_hours: int = 2):
        """Clean up executions that have been running too long"""
        try:
            db_manager = get_database_manager()
            session = db_manager.get_session_sync()
            try:
                from datetime import datetime, timedelta
                cutoff_time = datetime.utcnow() - timedelta(hours=max_duration_hours)
                
                stuck_executions = session.query(CommandExecution).filter(
                    CommandExecution.is_running == True,
                    CommandExecution.started_at < cutoff_time
                ).all()
                
                for execution in stuck_executions:
                    execution.is_running = False
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
            if config_override:
                # Apply overrides to config
                for key, value in config_override.items():
                    setattr(config, key, value)
            
            # Get command-specific configuration from database
            from database.database import get_database_manager
            manager = get_database_manager()
            session = manager.get_session_sync()
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
            success = await loop.run_in_executor(
                self.executor, 
                self._run_sync_command, 
                command
            )
            
            duration = time.time() - start_time
            
            # Generate output summary based on command type
            output_summary = self._generate_output_summary(command_name, success, duration)
            
            # Update execution record
            await self._update_execution_record(
                execution_id, 
                success=success, 
                duration=duration,
                completed_at=datetime.utcnow(),
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
                error_message=error_msg,
                completed_at=datetime.utcnow()
            )
        
        finally:
            # Remove from running commands
            if command_name in self.running_commands:
                del self.running_commands[command_name]
    
    def _run_sync_command(self, command) -> bool:
        """Run a synchronous command (wrapper for thread pool)"""
        self._ensure_initialized()
        try:
            # Commands are async, so we need to run them in an event loop
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                return loop.run_until_complete(command.execute())
            finally:
                loop.close()
        except Exception as e:
            self.logger.error(f"Sync command execution failed: {e}")
            return False
    
    def _generate_output_summary(self, command_name: str, success: bool, duration: float) -> str:
        """Generate a summary of command output based on command type and logs"""
        if not success:
            return f"Command failed after {duration:.1f}s"
        
        # Try to read the latest log entries to extract statistics
        try:
            log_file = "data/logs/cmdarr.log"
            if os.path.exists(log_file):
                with open(log_file, 'r') as f:
                    lines = f.readlines()
                
                # Get the last 100 lines to find recent command output
                recent_lines = lines[-100:] if len(lines) > 100 else lines
                
                if command_name == 'discovery_listenbrainz':
                    return self._extract_listenbrainz_summary(recent_lines, duration)
                elif command_name == 'discovery_lastfm':
                    return self._extract_lastfm_summary(recent_lines, duration)
                elif command_name == 'playlist_sync_listenbrainz_curated':
                    return self._extract_playlist_sync_summary(recent_lines, duration)
        except Exception as e:
            self.logger.debug(f"Failed to extract command summary: {e}")
        
        # Fallback summary
        return f"Command completed successfully in {duration:.1f}s"
    
    def _extract_listenbrainz_summary(self, log_lines: list, duration: float) -> str:
        """Extract ListenBrainz discovery statistics from log lines"""
        # Extract key statistics
        stats = {}
        for line in log_lines:
            if "Total Candidates:" in line:
                stats['total_candidates'] = line.split("Total Candidates:")[1].strip()
            elif "Filtered - Already in Lidarr:" in line:
                stats['already_in_lidarr'] = line.split("Filtered - Already in Lidarr:")[1].strip()
            elif "Filtered - Import List Exclusions:" in line:
                stats['filtered_exclusions'] = line.split("Filtered - Import List Exclusions:")[1].strip()
            elif "Final Output Count:" in line:
                stats['final_output'] = line.split("Final Output Count:")[1].strip()
        
        # Create concise summary
        summary_parts = [f"ListenBrainz Discovery completed in {duration:.1f}s"]
        
        if stats:
            total = stats.get('total_candidates', '0')
            already_in = stats.get('already_in_lidarr', '0')
            excluded = stats.get('filtered_exclusions', '0')
            output = stats.get('final_output', '0')
            
            if output == '0':
                # No new artists found - explain why
                summary_parts.append(f"✅ {total} artists detected:")
                summary_parts.append(f"   • {already_in} already in Lidarr")
                summary_parts.append(f"   • {excluded} on exclusion list")
                summary_parts.append("   • No new artists to add")
            else:
                # New artists found
                summary_parts.append(f"✅ {total} artists detected:")
                summary_parts.append(f"   • {already_in} already in Lidarr")
                summary_parts.append(f"   • {excluded} on exclusion list")
                summary_parts.append(f"   • {output} new artists ready for import")
        
        return "\n".join(summary_parts)
    
    def _extract_lastfm_summary(self, log_lines: list, duration: float) -> str:
        """Extract Last.fm discovery statistics from log lines"""
        # Extract key statistics
        stats = {}
        for line in log_lines:
            if "Total Candidates:" in line:
                stats['total_candidates'] = line.split("Total Candidates:")[1].strip()
            elif "Filtered - Already in Lidarr:" in line:
                stats['already_in_lidarr'] = line.split("Filtered - Already in Lidarr:")[1].strip()
            elif "Filtered - Import List Exclusions:" in line:
                stats['filtered_exclusions'] = line.split("Filtered - Import List Exclusions:")[1].strip()
            elif "Final Output Count:" in line:
                stats['final_output'] = line.split("Final Output Count:")[1].strip()
        
        # Create concise summary
        summary_parts = [f"Last.fm Discovery completed in {duration:.1f}s"]
        
        if stats:
            total = stats.get('total_candidates', '0')
            already_in = stats.get('already_in_lidarr', '0')
            excluded = stats.get('filtered_exclusions', '0')
            output = stats.get('final_output', '0')
            
            if output == '0':
                # No new artists found - explain why
                summary_parts.append(f"✅ {total} artists detected:")
                summary_parts.append(f"   • {already_in} already in Lidarr")
                summary_parts.append(f"   • {excluded} on exclusion list")
                summary_parts.append("   • No new artists to add")
            else:
                # New artists found
                summary_parts.append(f"✅ {total} artists detected:")
                summary_parts.append(f"   • {already_in} already in Lidarr")
                summary_parts.append(f"   • {excluded} on exclusion list")
                summary_parts.append(f"   • {output} new artists ready for import")
        
        return "\n".join(summary_parts)
    
    def _extract_playlist_sync_summary(self, log_lines: list, duration: float) -> str:
        """Extract playlist sync statistics from log lines"""
        summary_parts = [f"Playlist Sync completed in {duration:.1f}s"]
        
        # Look for the most recent statistics block
        stats_found = False
        individual_playlists = []
        
        # Find the most recent statistics block by looking for the last occurrence of each stat
        target_line = None
        source_line = None
        playlists_configured_line = None
        successful_syncs_line = None
        failed_syncs_line = None
        total_tracks_found_line = None
        total_tracks_attempted_line = None
        total_sync_time_line = None
        track_success_rate_line = None
        
        # Process lines in reverse order to get the most recent values
        for line in reversed(log_lines):
            line = line.strip()
            
            if "Target:" in line and "playlist_sync.listenbrainz_curated" in line and not target_line:
                target_line = line
            elif "Source:" in line and "playlist_sync.listenbrainz_curated" in line and not source_line:
                source_line = line
            elif "Playlists Configured:" in line and "playlist_sync.listenbrainz_curated" in line and not playlists_configured_line:
                playlists_configured_line = line
            elif "Successful Syncs:" in line and "playlist_sync.listenbrainz_curated" in line and not successful_syncs_line:
                successful_syncs_line = line
            elif "Failed Syncs:" in line and "playlist_sync.listenbrainz_curated" in line and not failed_syncs_line:
                failed_syncs_line = line
            elif "Total Tracks Found:" in line and "playlist_sync.listenbrainz_curated" in line and not total_tracks_found_line:
                total_tracks_found_line = line
            elif "Total Tracks Attempted:" in line and "playlist_sync.listenbrainz_curated" in line and not total_tracks_attempted_line:
                total_tracks_attempted_line = line
            elif "Total Sync Time:" in line and "playlist_sync.listenbrainz_curated" in line and not total_sync_time_line:
                total_sync_time_line = line
            elif "Track Success Rate:" in line and "playlist_sync.listenbrainz_curated" in line and not track_success_rate_line:
                track_success_rate_line = line
            
            # Extract individual playlist results
            elif "✅ 🚀" in line and "tracks" in line:
                playlist_info = line.split("✅ 🚀")[1].strip()
                individual_playlists.append(playlist_info)
        
        # Add statistics if found
        if target_line:
            summary_parts.append(f"Target: {target_line.split('Target:')[1].strip()}")
            stats_found = True
        if source_line:
            summary_parts.append(f"Source: {source_line.split('Source:')[1].strip()}")
        if playlists_configured_line:
            summary_parts.append(f"Playlists Configured: {playlists_configured_line.split(':')[1].strip()}")
        if successful_syncs_line:
            summary_parts.append(f"Successful Syncs: {successful_syncs_line.split(':')[1].strip()}")
        if failed_syncs_line:
            summary_parts.append(f"Failed Syncs: {failed_syncs_line.split(':')[1].strip()}")
        if total_tracks_found_line:
            summary_parts.append(f"Total Tracks Found: {total_tracks_found_line.split(':')[1].strip()}")
        if total_tracks_attempted_line:
            summary_parts.append(f"Total Tracks Attempted: {total_tracks_attempted_line.split(':')[1].strip()}")
        if total_sync_time_line:
            summary_parts.append(f"Total Sync Time: {total_sync_time_line.split(':')[1].strip()}")
        if track_success_rate_line:
            summary_parts.append(f"Track Success Rate: {track_success_rate_line.split(':')[1].strip()}")
        
        # Add individual playlist results if found
        if individual_playlists:
            summary_parts.append("")
            summary_parts.append("Individual Playlist Results:")
            for playlist in individual_playlists:
                summary_parts.append(f"  • {playlist}")
        
        # If no detailed stats found, fall back to basic summary
        if not stats_found:
            summary_parts = [f"Playlist Sync completed in {duration:.1f}s"]
            for line in log_lines:
                if "playlists processed" in line.lower():
                    summary_parts.append(line.strip())
                elif "tracks added" in line.lower():
                    summary_parts.append(line.strip())
                elif "playlists updated" in line.lower():
                    summary_parts.append(line.strip())
        
        return "\n".join(summary_parts)
    
    async def _create_execution_record(self, command_name: str, triggered_by: str = 'manual') -> int:
        """Create a new command execution record in the database"""
        try:
            self.logger.info(f"Creating execution record for {command_name} with triggered_by='{triggered_by}'")
            db_manager = get_database_manager()
            session = db_manager.get_session_sync()
            try:
                execution = CommandExecution(
                    command_name=command_name,
                    started_at=datetime.utcnow(),
                    triggered_by=triggered_by
                )
                session.add(execution)
                session.commit()
                
                # Broadcast command started
                await self._broadcast_update(command_name, {
                    'status': 'started',
                    'execution_id': execution.id,
                    'started_at': execution.started_at.isoformat() + 'Z',
                    'triggered_by': execution.triggered_by
                })
                
                return execution.id
            finally:
                session.close()
        except Exception as e:
            self.logger.error(f"Failed to create execution record: {e}")
            return 0
    
    async def _update_execution_record(self, execution_id: int, success: bool, duration: float, 
                                     completed_at: datetime, error_message: str = None, output_summary: str = None):
        """Update command execution record with results"""
        self._ensure_initialized()
        try:
            db_manager = get_database_manager()
            session = db_manager.get_session_sync()
            try:
                execution = session.query(CommandExecution).filter(
                    CommandExecution.id == execution_id
                ).first()
                
                if execution:
                    execution.completed_at = completed_at
                    execution.success = success
                    execution.status = 'completed' if success else 'failed'
                    execution.duration = duration
                    execution.error_message = error_message
                    execution.output_summary = output_summary
                    
                    # Update the command config's last_run and related fields
                    command_config = session.query(CommandConfig).filter(
                        CommandConfig.command_name == execution.command_name
                    ).first()
                    
                    if command_config:
                        command_config.last_run = execution.started_at
                        command_config.last_success = success
                        command_config.last_duration = duration
                        command_config.last_error = error_message
                        command_config.updated_at = datetime.utcnow()
                    
                    session.commit()
                    
                    # Broadcast command completed
                    await self._broadcast_update(execution.command_name, {
                        'status': 'completed',
                        'execution_id': execution.id,
                        'success': success,
                        'duration': duration,
                        'completed_at': completed_at.isoformat() + 'Z',
                        'error_message': error_message
                    })
            finally:
                session.close()
        except Exception as e:
            self.logger.error(f"Failed to update execution record: {e}")
    
    async def get_command_status(self, command_name: str) -> Dict[str, Any]:
        """Get current status of a command"""
        self._ensure_initialized()
        is_running = command_name in self.running_commands
        
        # Get latest execution record
        try:
            db_manager = get_database_manager()
            session = db_manager.get_session_sync()
            try:
                latest_execution = session.query(CommandExecution).filter(
                    CommandExecution.command_name == command_name
                ).order_by(CommandExecution.started_at.desc()).first()
                
                if latest_execution:
                    return {
                        'command_name': command_name,
                        'is_running': is_running,
                        'last_execution': {
                            'id': latest_execution.id,
                            'started_at': latest_execution.started_at.isoformat() + 'Z',
                            'completed_at': latest_execution.completed_at.isoformat() + 'Z' if latest_execution.completed_at else None,
                            'success': latest_execution.success,
                            'duration': latest_execution.duration,
                            'error_message': latest_execution.error_message
                        }
                    }
                else:
                    return {
                        'command_name': command_name,
                        'is_running': is_running,
                        'last_execution': None
                    }
            finally:
                session.close()
        except Exception as e:
            self.logger.error(f"Failed to get command status: {e}")
            return {
                'command_name': command_name,
                'is_running': is_running,
                'error': str(e)
            }
    
    async def get_all_command_status(self) -> Dict[str, Any]:
        """Get status of all commands"""
        self._ensure_initialized()
        status = {}
        for command_name in self.command_classes.keys():
            status[command_name] = await self.get_command_status(command_name)
        return status
    
    def get_running_commands(self) -> list:
        """Get list of currently running commands"""
        return list(self.running_commands.keys())
    
    def get_command_class(self, command_name: str):
        """Get command class for a given command name"""
        self._ensure_initialized()
        return self.command_classes.get(command_name)
    
    async def stop_command(self, command_name: str) -> bool:
        """Stop a running command"""
        self._ensure_initialized()
        if command_name not in self.running_commands:
            return False
        
        try:
            task = self.running_commands[command_name]
            task.cancel()
            del self.running_commands[command_name]
            self.logger.info(f"Stopped command: {command_name}")
            return True
        except Exception as e:
            self.logger.error(f"Failed to stop command {command_name}: {e}")
            return False
    
    async def _broadcast_update(self, command_name: str, data: Dict[str, Any]):
        """Broadcast command update via WebSocket"""
        try:
            from app.websocket import manager
            await manager.broadcast_command_update(command_name, data)
        except Exception as e:
            # Don't fail command execution if WebSocket fails
            self.logger.warning(f"Failed to broadcast update for {command_name}: {e}")

    def kill_execution(self, execution_id: int):
        """Kill a running command execution"""
        try:
            self._ensure_initialized()
            
            # Find the running command task
            command_name = None
            task_to_cancel = None
            
            for cmd_name, task in self.running_commands.items():
                # Check if this task is for the execution we want to kill
                if hasattr(task, 'execution_id') and task.execution_id == execution_id:
                    command_name = cmd_name
                    task_to_cancel = task
                    break
            
            if task_to_cancel and not task_to_cancel.done():
                # Cancel the task
                task_to_cancel.cancel()
                self.logger.info(f"Cancelled task for execution {execution_id} ({command_name})")
                
                # Remove from running commands
                if command_name in self.running_commands:
                    del self.running_commands[command_name]
                
                return True
            else:
                self.logger.warning(f"No running task found for execution {execution_id}")
                return False
                
        except Exception as e:
            self.logger.error(f"Failed to kill execution {execution_id}: {e}")
            return False


# Global instance
command_executor = CommandExecutor()
