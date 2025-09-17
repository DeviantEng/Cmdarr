#!/usr/bin/env python3
"""
ListenBrainz Curated Playlist Sync Command
Syncs ListenBrainz curated playlists (Weekly Exploration, Weekly Jams, Daily Jams) to music players
Enhanced with library cache optimization for dramatic performance improvements
"""

import asyncio
import re
import time
from typing import List, Dict, Any, Optional
from datetime import datetime

from .command_base import BaseCommand
from clients.client_listenbrainz import ListenBrainzClient
from clients.client_plex import PlexClient
from clients.client_jellyfin import JellyfinClient
from utils.library_cache_manager import get_library_cache_manager


class PlaylistSyncListenBrainzCuratedCommand(BaseCommand):
    """Command to sync ListenBrainz curated playlists to music players with library cache optimization"""
    
    def __init__(self, config=None):
        super().__init__(config)
        self.listenbrainz = ListenBrainzClient(self.config)
        
        # Target client will be initialized in _initialize_target_client()
        self.target_client = None
        self.target_name = None
        
        # Initialize library cache manager for performance optimization
        self.library_cache_manager = get_library_cache_manager(self.config)
        
        # Store statistics for reporting
        self.last_run_stats = {}
    
    def _initialize_target_client(self):
        """Initialize target client based on command-specific configuration"""
        target = None
        
        # Check if the command executor set it as an attribute on config (primary method)
        target = getattr(self.config, 'COMMAND_PLAYLIST_SYNC_LISTENBRAINZ_CURATED_TARGET', None)
        
        # Fallback: check if we have command-specific config (set by command executor)
        if not target and hasattr(self, 'config_json') and self.config_json:
            # The command executor maps 'target' to 'COMMAND_PLAYLIST_SYNC_LISTENBRAINZ_CURATED_TARGET'
            target = self.config_json.get('target')
        
        # Fallback: check global config (for backward compatibility)
        if not target:
            target = self.config.get('COMMAND_PLAYLIST_SYNC_LISTENBRAINZ_CURATED_TARGET')
        
        self.logger.info(f"Final target value: {target}")
        
        if not target or target == 'None' or target == '':
            raise ValueError("No playlist sync target configured. Please set the Target in the command configuration to 'plex' or 'jellyfin'")
        
        target = target.lower()
        if target == 'plex':
            self.target_client = PlexClient(self.config)
            self.target_name = 'Plex'
        elif target == 'jellyfin':
            self.target_client = JellyfinClient(self.config)
            self.target_name = 'Jellyfin'
        else:
            raise ValueError(f"Unsupported playlist sync target: {target}. Must be 'plex' or 'jellyfin'")
    
    def get_description(self) -> str:
        """Return command description for help text."""
        target_name = self.target_name or "music player"
        return f"Sync ListenBrainz curated playlists (Weekly Exploration, Weekly Jams, Daily Jams) to {target_name} with library cache optimization"
    
    def get_logger_name(self) -> str:
        """Return logger name for this command."""
        return "playlist_sync.listenbrainz_curated"
    
    async def _validate_existing_playlists(self) -> Dict[str, Any]:
        """
        Comprehensive validation of existing playlists before sync.
        Returns validation results and recommendations for each playlist type.
        """
        validation_results = {
            'overall_status': 'clean',
            'duplicates_found': 0,
            'empty_playlists_found': 0,
            'playlist_validations': {},
            'recommendations': []
        }
        
        try:
            self.logger.info("Starting comprehensive playlist validation...")
            
            # Get all existing ListenBrainz playlists
            if self.target_name == 'Plex':
                # Use Plex API directly
                results = self.target_client._get("/playlists")
                media_container = results.get("MediaContainer", {})
                all_playlists = media_container.get("Metadata", [])
                lb_playlists = [p for p in all_playlists if p.get('title', '').startswith('[LB] ')]
            elif self.target_name == 'Jellyfin':
                # Use Jellyfin API
                all_playlists = self.target_client.get_playlists_sync() if hasattr(self.target_client, 'get_playlists_sync') else []
                lb_playlists = [p for p in all_playlists if p.get('Name', '').startswith('[LB] ')]
            else:
                lb_playlists = []
            
            self.logger.info(f"Found {len(lb_playlists)} existing ListenBrainz playlists")
            
            # Group playlists by name to detect duplicates
            from collections import defaultdict
            playlist_groups = defaultdict(list)
            for playlist in lb_playlists:
                name = playlist.get('Name', '')
                playlist_groups[name].append(playlist)
            
            # Validate each playlist group
            for playlist_name, playlists in playlist_groups.items():
                validation = {
                    'name': playlist_name,
                    'count': len(playlists),
                    'is_duplicate': len(playlists) > 1,
                    'has_tracks': False,
                    'total_tracks': 0,
                    'playlists': []
                }
                
                # Check each playlist in the group
                for playlist in playlists:
                    playlist_id = playlist.get('Id', '')
                    tracks = []
                    
                    # Get tracks for this playlist
                    if hasattr(self.target_client, 'get_playlist_tracks_sync'):
                        tracks = self.target_client.get_playlist_tracks_sync(playlist_id)
                    
                    playlist_info = {
                        'id': playlist_id,
                        'track_count': len(tracks),
                        'has_tracks': len(tracks) > 0,
                        'tracks': tracks
                    }
                    
                    validation['playlists'].append(playlist_info)
                    validation['total_tracks'] += len(tracks)
                    if len(tracks) > 0:
                        validation['has_tracks'] = True
                
                # Update overall validation results
                if validation['is_duplicate']:
                    validation_results['duplicates_found'] += len(playlists) - 1
                    validation_results['recommendations'].append(f"Found {len(playlists)} duplicates of '{playlist_name}' - recommend cleanup")
                
                if not validation['has_tracks']:
                    validation_results['empty_playlists_found'] += len(playlists)
                    validation_results['recommendations'].append(f"Found empty playlist(s) '{playlist_name}' - recommend deletion")
                
                validation_results['playlist_validations'][playlist_name] = validation
            
            # Determine overall status
            if validation_results['duplicates_found'] > 0 or validation_results['empty_playlists_found'] > 0:
                validation_results['overall_status'] = 'issues_found'
            else:
                validation_results['overall_status'] = 'clean'
            
            self.logger.info(f"Validation complete: {validation_results['duplicates_found']} duplicates, {validation_results['empty_playlists_found']} empty playlists")
            
            return validation_results
            
        except Exception as e:
            self.logger.error(f"Error during playlist validation: {e}")
            validation_results['overall_status'] = 'error'
            validation_results['error'] = str(e)
            return validation_results
    
    async def _cleanup_duplicates_and_empty(self, validation_results: Dict[str, Any]) -> bool:
        """
        Clean up duplicates and empty playlists based on validation results.
        Returns True if cleanup was successful.
        """
        try:
            if validation_results['overall_status'] == 'clean':
                self.logger.info("No cleanup needed - playlists are clean")
                return True
            
            self.logger.info("Starting cleanup of duplicates and empty playlists...")
            
            cleanup_count = 0
            
            for playlist_name, validation in validation_results['playlist_validations'].items():
                if validation['is_duplicate'] or not validation['has_tracks']:
                    self.logger.info(f"Cleaning up playlist group: {playlist_name}")
                    
                    # Find the best playlist to keep (one with most tracks)
                    best_playlist = None
                    best_track_count = 0
                    
                    for playlist_info in validation['playlists']:
                        if playlist_info['track_count'] > best_track_count:
                            best_track_count = playlist_info['track_count']
                            best_playlist = playlist_info
                    
                    # Delete all others (if we have a best playlist to keep)
                    if best_playlist:
                        best_playlist_id = best_playlist.get('Id') or best_playlist.get('id')
                        
                        for playlist_info in validation['playlists']:
                            # Handle different client ID field names
                            playlist_id = playlist_info.get('Id') or playlist_info.get('id')
                            
                            if playlist_id != best_playlist_id:
                                self.logger.info(f"Deleting playlist: {playlist_name} (ID: {playlist_id})")
                                if hasattr(self.target_client, 'delete_playlist_sync'):
                                    success = self.target_client.delete_playlist_sync(playlist_id)
                                    if success:
                                        cleanup_count += 1
                                        self.logger.info(f"Successfully deleted playlist {playlist_id}")
                                    else:
                                        self.logger.error(f"Failed to delete playlist {playlist_id}")
                    else:
                        # No best playlist found, delete all
                        self.logger.warning(f"No valid playlist found to keep for {playlist_name}, deleting all")
                        for playlist_info in validation['playlists']:
                            playlist_id = playlist_info.get('Id') or playlist_info.get('id')
                            if playlist_id:
                                self.logger.info(f"Deleting playlist: {playlist_name} (ID: {playlist_id})")
                                if hasattr(self.target_client, 'delete_playlist_sync'):
                                    success = self.target_client.delete_playlist_sync(playlist_id)
                                    if success:
                                        cleanup_count += 1
                                        self.logger.info(f"Successfully deleted playlist {playlist_id}")
                                    else:
                                        self.logger.error(f"Failed to delete playlist {playlist_id}")
            
            self.logger.info(f"Cleanup complete: {cleanup_count} playlists removed")
            return True
            
        except Exception as e:
            self.logger.error(f"Error during cleanup: {e}")
            return False
    
    async def _validate_and_sync_playlist(self, playlist_key: str, playlist_data: Dict[str, Any], tracks: List[Dict[str, Any]], target_title: str, description: str) -> Dict[str, Any]:
        """
        Validate and sync a single playlist with proper duplicate prevention.
        This method ensures that no duplicate playlists are created.
        """
        try:
            self.logger.info(f"Validating playlist '{target_title}' before sync...")
            
            # Check if playlist already exists with exact name
            existing_playlists = []
            if hasattr(self.target_client, 'find_all_playlists_by_name'):
                existing_playlists = self.target_client.find_all_playlists_by_name(target_title)
            elif hasattr(self.target_client, 'validate_playlist_exists'):
                validation = self.target_client.validate_playlist_exists(target_title)
                existing_playlists = validation.get('playlists', [])
            
            if existing_playlists:
                self.logger.info(f"Found {len(existing_playlists)} existing playlist(s) with name '{target_title}'")
                
                # Check if any existing playlist has the expected track count
                expected_track_count = len(tracks)
                matching_playlist = None
                
                for existing_playlist in existing_playlists:
                    if hasattr(self.target_client, 'get_playlist_tracks_sync'):
                        # Handle different client ID field names
                        playlist_id = existing_playlist.get('Id') or existing_playlist.get('id')
                        existing_tracks = self.target_client.get_playlist_tracks_sync(playlist_id)
                        existing_track_count = len(existing_tracks)
                        
                        if existing_track_count == expected_track_count:
                            matching_playlist = existing_playlist
                            self.logger.info(f"Found existing playlist with matching track count ({existing_track_count} tracks)")
                            break
                        else:
                            self.logger.info(f"Existing playlist has {existing_track_count} tracks, expected {expected_track_count}")
                
                if matching_playlist:
                    # Playlist exists with correct track count, skip creation
                    self.logger.info(f"Playlist '{target_title}' already exists with correct track count, skipping creation")
                    return {
                        'success': True,
                        'action': 'skipped_existing',
                        'total_tracks': expected_track_count,
                        'found_tracks': expected_track_count,
                        'message': f"Playlist '{target_title}' already exists with correct track count"
                    }
                else:
                    # Playlist exists but with wrong track count, delete all existing and create new
                    self.logger.info(f"Playlist '{target_title}' exists but with incorrect track count, deleting existing and creating new")
                    for existing_playlist in existing_playlists:
                        if hasattr(self.target_client, 'delete_playlist_sync'):
                            # Handle different client ID field names
                            playlist_id = existing_playlist.get('Id') or existing_playlist.get('id')
                            self.logger.info(f"Deleting existing playlist '{target_title}' (ID: {playlist_id})")
                            self.target_client.delete_playlist_sync(playlist_id)
            
            # No existing playlist or all existing playlists deleted, proceed with sync
            self.logger.info(f"Proceeding with sync for playlist '{target_title}'")
            
            # Call the client's sync method - now standardized across all clients
            if hasattr(self.target_client, 'sync_playlist'):
                return self.target_client.sync_playlist(target_title, tracks, description)
            else:
                self.logger.error(f"Target client does not support sync_playlist method")
                return {
                    'success': False,
                    'action': 'error',
                    'total_tracks': len(tracks),
                    'found_tracks': 0,
                    'message': f"Target client does not support sync_playlist method"
                }
                
        except Exception as e:
            import traceback
            self.logger.error(f"Error validating and syncing playlist '{target_title}': {e}")
            self.logger.error(f"Full traceback: {traceback.format_exc()}")
            return {
                'success': False,
                'action': 'error',
                'total_tracks': len(tracks),
                'found_tracks': 0,
                'message': f"Error: {str(e)}"
            }

    async def execute(self) -> bool:
        """Execute the playlist sync process with library cache optimization"""
        try:
            # Initialize target client (needs to be done after command executor sets config_json)
            self._initialize_target_client()
            
            self.logger.info(f"Starting ListenBrainz curated playlist sync to {self.target_name}")
            
            # Clean up expired cache entries if caching is enabled
            if self.config.get('CACHE_ENABLED', True):
                from cache_manager import get_cache_manager
                cache = get_cache_manager()
                expired_count = cache.cleanup_expired()
                if expired_count > 0:
                    self.logger.info(f"Cleaned up {expired_count} expired cache entries")
                
                # Also cleanup library cache
                library_expired = self.library_cache_manager.cleanup_expired_cache()
                if library_expired > 0:
                    self.logger.info(f"Cleaned up {library_expired} expired library cache entries")
            
            # Register target client with library cache manager
            self._register_target_client()
            
            # Enable memory cache for batch operations
            self.library_cache_manager.keep_memory_cache_during_batch()
            
            try:
                # PRE-SYNC VALIDATION: Check for existing playlists and duplicates
                self.logger.info("Performing pre-sync validation...")
                validation_results = await self._validate_existing_playlists()
                
                if validation_results['overall_status'] == 'issues_found':
                    self.logger.warning(f"Found playlist issues: {validation_results['duplicates_found']} duplicates, {validation_results['empty_playlists_found']} empty playlists")
                    
                    # Clean up duplicates and empty playlists before sync
                    cleanup_success = await self._cleanup_duplicates_and_empty(validation_results)
                    if not cleanup_success:
                        self.logger.error("Failed to clean up playlist issues, continuing with sync...")
                elif validation_results['overall_status'] == 'error':
                    self.logger.error("Playlist validation failed, continuing with sync...")
                else:
                    self.logger.info("Playlist validation passed - no issues found")
                
                # Sync playlists with library cache optimization
                sync_results = await self._sync_curated_playlists()
                
                # Store statistics
                self._store_run_statistics(sync_results)
                
                # Log final statistics including cache performance
                self._log_final_statistics()
                
                # Determine overall success from sync results
                success = any(result['success'] for result in sync_results.values())
                
            finally:
                # Always clear memory cache after batch operations
                self.library_cache_manager.clear_memory_cache()
            
            # Clean up old playlists based on retention settings
            if success:
                await self._cleanup_old_playlists()
            
            # Determine overall success
            if success:
                self.logger.info(f"ListenBrainz curated playlist sync to {self.target_name} completed successfully")
            else:
                self.logger.error(f"ListenBrainz curated playlist sync to {self.target_name} failed")
            
            return success
            
        except Exception as e:
            self.logger.error(f"ListenBrainz curated playlist sync failed: {e}")
            return False
        finally:
            # Clean up HTTP sessions
            await self.listenbrainz.close()
            # Close target client if it has a close method
            if hasattr(self.target_client, 'close'):
                await self.target_client.close()
    
    def _register_target_client(self) -> None:
        """Register target music client with library cache manager"""
        try:
            # Use the same target logic as __init__ to ensure consistency
            target_type = self.target_name.lower()
            
            if target_type == 'plex':
                self.library_cache_manager.register_client('plex', self.target_client)
                self.logger.debug("Registered Plex client with library cache manager")
            elif target_type == 'jellyfin':
                self.library_cache_manager.register_client('jellyfin', self.target_client)
                self.logger.debug("Registered Jellyfin client with library cache manager")
        except Exception as e:
            self.logger.warning(f"Failed to register client with library cache manager: {e}")
            import traceback
            self.logger.warning(f"Full traceback: {traceback.format_exc()}")
    
    async def _sync_curated_playlists(self) -> Dict[str, Dict[str, Any]]:
        """Main processing function to sync curated playlists with library cache optimization"""
        
        # Get configured playlists to sync
        playlists_to_sync = self._get_configured_playlists()
        
        if not playlists_to_sync:
            self.logger.warning("No playlists configured for sync")
            return {}
        
        self.logger.info(f"Configured to sync: {', '.join(playlists_to_sync)}")
        
        # Test connections
        self.logger.info("Testing API connections...")
        lb_connected = await self.listenbrainz.test_connection()
        
        # Jellyfin client is synchronous, Plex client is async
        if self.target_name.lower() == 'jellyfin':
            target_connected = self.target_client.test_connection()
        else:
            target_connected = await self.target_client.test_connection()
        
        if not lb_connected:
            self.logger.error("Failed to connect to ListenBrainz API")
            return {}
        
        if not target_connected:
            self.logger.error(f"Failed to connect to {self.target_name}")
            return {}
        
        # Check for available library cache
        library_cache = self._check_library_cache()
        
        if library_cache:
            track_count = library_cache.get('total_tracks', 0)
            self.logger.info(f"Library cache available: {track_count:,} tracks")
            
            # Only pass cached library to target client if their library cache is enabled
            if self.target_name.lower() == 'plex' and self.config.get('LIBRARY_CACHE_PLEX_ENABLED', False):
                self.target_client._cached_library = library_cache
                self.logger.info("Plex library cache enabled - using cached library for fast lookups")
            elif self.target_name.lower() == 'jellyfin' and self.config.get('LIBRARY_CACHE_JELLYFIN_ENABLED', False):
                self.target_client._cached_library = library_cache
                self.logger.info("Jellyfin library cache enabled - using cached library for fast lookups")
            else:
                self.logger.info(f"{self.target_name} library cache disabled - using live API searches")
        else:
            self.logger.info("No library cache available, will use live API searches")
        
        # Get curated playlists from ListenBrainz
        username = self.config.get('LISTENBRAINZ_USERNAME', '')
        self.logger.info(f"Fetching curated playlists for user: {username}")
        curated_playlists = await self.listenbrainz.get_curated_playlists(username)
        
        # Process each configured playlist with cache optimization
        sync_results = {}
        total_sync_time = 0
        
        for playlist_key in playlists_to_sync:
            playlist_start_time = datetime.now()
            
            playlist_data = curated_playlists.get(playlist_key)
            
            if playlist_data is None:
                self.logger.warning(f"Playlist '{playlist_key}' not found in ListenBrainz")
                sync_results[playlist_key] = {
                    'success': False,
                    'error': 'Playlist not found in ListenBrainz',
                    'tracks_found': 0,
                    'tracks_total': 0,
                    'playlist_title': self._get_display_name(playlist_key),
                    'sync_time': 0,
                    'cache_used': False
                }
                continue
            
            # Extract tracks from playlist
            tracks = await self.listenbrainz.extract_tracks_from_playlist(playlist_data)
            
            if not tracks:
                self.logger.warning(f"No tracks found in playlist '{playlist_key}'")
                sync_results[playlist_key] = {
                    'success': False,
                    'error': 'No tracks found in playlist',
                    'tracks_found': 0,
                    'tracks_total': 0,
                    'playlist_title': playlist_data.get('title', self._get_display_name(playlist_key)),
                    'sync_time': 0,
                    'cache_used': False
                }
                continue
            
            # Generate target playlist title
            original_title = playlist_data.get('title', self._get_display_name(playlist_key))
            target_title = self._generate_target_playlist_title(original_title, playlist_key)
            
            # Generate playlist description
            description = self._generate_playlist_description(playlist_data, playlist_key)
            
            # Validate and sync playlist with proper duplicate prevention
            self.logger.info(f"Validating and syncing '{playlist_key}' ({len(tracks)} tracks) to {self.target_name} as '{target_title}'")
            
            # Use the new validation and sync method
            result = await self._validate_and_sync_playlist(
                playlist_key=playlist_key,
                playlist_data=playlist_data,
                tracks=tracks,
                target_title=target_title,
                description=description
            )
            
            # Extract results from the validation method
            success = result.get('success', False)
            tracks_found = result.get('found_tracks', 0)
            tracks_total = result.get('total_tracks', len(tracks))
            
            playlist_sync_time = (datetime.now() - playlist_start_time).total_seconds()
            total_sync_time += playlist_sync_time
            
            sync_results[playlist_key] = {
                'success': success,
                'error': None if success else 'Sync operation failed',
                'tracks_found': tracks_found,
                'tracks_total': tracks_total,
                'playlist_title': target_title,
                'original_title': original_title,
                'sync_time': playlist_sync_time,
                'cache_used': library_cache is not None
            }
            
            if success:
                match_rate = (tracks_found / tracks_total * 100) if tracks_total > 0 else 0
                self.logger.info(f"Successfully synced '{playlist_key}': {tracks_found}/{tracks_total} tracks ({match_rate:.1f}%) in {playlist_sync_time:.1f}s")
            else:
                self.logger.error(f"Failed to sync '{playlist_key}' after {playlist_sync_time:.1f}s")
        
        # Log overall performance improvement
        if library_cache and total_sync_time > 0:
            estimated_without_cache = total_sync_time * 6  # Conservative estimate of 6x improvement
            time_saved = estimated_without_cache - total_sync_time
            self.logger.info(f"Library cache performance: {total_sync_time:.1f}s total sync time (estimated {time_saved:.1f}s saved)")
        
        return sync_results
    
    def _check_library_cache(self) -> Optional[Dict[str, Any]]:
        """Check if library cache is available and fresh, build if missing"""
        try:
            target_type = self.target_name.lower()
            
            # Get existing cache
            library_cache = self.library_cache_manager.get_library_cache(target_type)
            
            if not library_cache:
                self.logger.info(f"No library cache found for {target_type}, building cache...")
                return self._build_library_cache_if_enabled(target_type)
            
            # Check if cache is fresh (within TTL)
            cache_age_hours = (time.time() - library_cache.get('built_at', 0)) / 3600
            ttl_hours = self.config.get(f'LIBRARY_CACHE_{target_type.upper()}_TTL_DAYS', 30) * 24
            
            if cache_age_hours > ttl_hours:
                self.logger.info(f"Library cache for {target_type} is stale ({cache_age_hours:.1f}h old, TTL: {ttl_hours}h), rebuilding...")
                return self._build_library_cache_if_enabled(target_type)
            
            self.logger.debug(f"Library cache for {target_type} is fresh ({cache_age_hours:.1f}h old)")
            return library_cache
                
        except Exception as e:
            self.logger.warning(f"Failed to check library cache: {e}")
            return None
    
    def _build_library_cache_if_enabled(self, target_type: str) -> Optional[Dict[str, Any]]:
        """Build library cache if enabled for the target"""
        try:
            # Check if cache building is enabled for this target
            enabled_key = f'LIBRARY_CACHE_{target_type.upper()}_ENABLED'
            if not self.config.get(enabled_key, False):
                self.logger.info(f"Library cache building is disabled for {target_type}, skipping cache build")
                return None
            
            self.logger.info(f"Building library cache for {target_type}...")
            
            # Import and execute cache builder
            from commands.library_cache_builder import LibraryCacheBuilderCommand
            import asyncio
            
            # Create cache builder command
            cache_builder = LibraryCacheBuilderCommand(self.config)
            
            # Temporarily enable only this target
            original_plex_enabled = self.config.get('LIBRARY_CACHE_PLEX_ENABLED', False)
            original_jellyfin_enabled = self.config.get('LIBRARY_CACHE_JELLYFIN_ENABLED', False)
            
            if target_type == 'plex':
                self.config.LIBRARY_CACHE_PLEX_ENABLED = True
                self.config.LIBRARY_CACHE_JELLYFIN_ENABLED = False
            else:
                self.config.LIBRARY_CACHE_PLEX_ENABLED = False
                self.config.LIBRARY_CACHE_JELLYFIN_ENABLED = True
            
            # Execute cache building
            result = asyncio.run(cache_builder.execute())
            
            # Restore original settings
            self.config.LIBRARY_CACHE_PLEX_ENABLED = original_plex_enabled
            self.config.LIBRARY_CACHE_JELLYFIN_ENABLED = original_jellyfin_enabled
            
            if result:
                self.logger.info(f"Successfully built library cache for {target_type}")
                # Get the newly built cache
                return self.library_cache_manager.get_library_cache(target_type)
            else:
                self.logger.warning(f"Failed to build library cache for {target_type}")
                return None
                
        except Exception as e:
            self.logger.error(f"Failed to build library cache for {target_type}: {e}")
            return None
    
    def _get_configured_playlists(self) -> List[str]:
        """Get list of playlists to sync from configuration"""
        # Read from command-specific config first, fallback to global config
        configured_playlists = []
        valid_playlists = ['weekly_exploration', 'weekly_jams', 'daily_jams']
        
        # Check each playlist setting from command-specific config
        for playlist in valid_playlists:
            config_key = f'COMMAND_PLAYLIST_SYNC_LISTENBRAINZ_CURATED_{playlist.upper()}'
            value = getattr(self.config, config_key, None)
            self.logger.debug(f"Checking {config_key}: {value}")
            if value:
                configured_playlists.append(playlist)
                self.logger.debug(f"Added {playlist} to configured playlists")
        
        # If no playlists configured via command-specific config, fallback to global config
        if not configured_playlists:
            playlists_config = getattr(self.config, 'PLAYLIST_SYNC_LISTENBRAINZ_CURATED_PLAYLISTS', 'weekly_exploration,weekly_jams,daily_jams')
            playlists = [p.strip() for p in playlists_config.split(',') if p.strip()]
            
            for playlist in playlists:
                if playlist in valid_playlists:
                    configured_playlists.append(playlist)
                else:
                    self.logger.warning(f"Unknown playlist type '{playlist}' in configuration, skipping")
        
        return configured_playlists
    
    def _get_display_name(self, playlist_key: str) -> str:
        """Get human-readable display name for playlist key"""
        display_names = {
            'weekly_exploration': 'Weekly Exploration',
            'weekly_jams': 'Weekly Jams',
            'daily_jams': 'Daily Jams'
        }
        return display_names.get(playlist_key, playlist_key.replace('_', ' ').title())
    
    def _generate_target_playlist_title(self, original_title: str, playlist_key: str) -> str:
        """Generate the target playlist title with [LB] prefix and formatted date"""
        # Map playlist keys to ListenBrainz type names
        type_names = {
            'daily_jams': 'Daily Jams',
            'weekly_jams': 'Weekly Jams', 
            'weekly_exploration': 'Weekly Exploration'
        }
        
        type_name = type_names.get(playlist_key, playlist_key.replace('_', ' ').title())
        
        # Try to extract date from original title
        formatted_date = None
        if original_title and original_title.strip():
            # Look for patterns like "week of 2025-09-01" or "2025-09-01"
            date_patterns = [
                r'week of (\d{4}-\d{2}-\d{2})',  # "week of 2025-09-01"
                r'(\d{4}-\d{2}-\d{2})',          # "2025-09-01"
                r'(\d{2}/\d{2}/\d{4})',          # "09/01/2025"
                r'(\d{1,2}/\d{1,2}/\d{4})'       # "9/1/2025"
            ]
            
            for pattern in date_patterns:
                match = re.search(pattern, original_title)
                if match:
                    date_str = match.group(1)
                    try:
                        # Parse different date formats
                        if '-' in date_str:
                            date_obj = datetime.strptime(date_str, '%Y-%m-%d')
                        elif '/' in date_str:
                            # Try MM/DD/YYYY first, then M/D/YYYY
                            try:
                                date_obj = datetime.strptime(date_str, '%m/%d/%Y')
                            except ValueError:
                                date_obj = datetime.strptime(date_str, '%m/%d/%Y')
                        else:
                            continue
                            
                        # Format as 3-letter month + day (Sep-01)
                        formatted_date = date_obj.strftime('%b-%d')
                        break
                        
                    except ValueError:
                        continue
        
        # Generate final title
        if formatted_date:
            return f"[LB] {type_name}, {formatted_date}"
        else:
            # Fallback without date if extraction fails
            return f"[LB] {type_name}"
    
    def _generate_playlist_description(self, playlist_data: Dict[str, Any], playlist_key: str) -> str:
        """Generate playlist description"""
        original_description = playlist_data.get('annotation', '').strip()
        
        # Use original description if available
        if original_description:
            description = original_description
        else:
            # Generate default description based on playlist type
            type_descriptions = {
                'weekly_exploration': 'Your personalized weekly music discovery playlist from ListenBrainz',
                'weekly_jams': 'Your weekly music recommendations from ListenBrainz',
                'daily_jams': 'Your daily music recommendations from ListenBrainz'
            }
            description = type_descriptions.get(playlist_key, f'Curated playlist from ListenBrainz')
        
        # Add sync timestamp
        sync_time = datetime.now().strftime('%Y-%m-%d %H:%M')
        description += f"\n\nSynced from ListenBrainz on {sync_time} by Cmdarr"
        
        return description
    
    def _store_run_statistics(self, sync_results: Dict[str, Dict[str, Any]]):
        """Store statistics for reporting including cache performance metrics"""
        total_playlists = len(sync_results)
        successful_syncs = sum(1 for result in sync_results.values() if result['success'])
        total_tracks_found = sum(result['tracks_found'] for result in sync_results.values())
        total_tracks_attempted = sum(result['tracks_total'] for result in sync_results.values())
        total_sync_time = sum(result.get('sync_time', 0) for result in sync_results.values())
        cache_used = any(result.get('cache_used', False) for result in sync_results.values())
        
        # Get library cache stats
        cache_stats = self.library_cache_manager.get_cache_stats()
        
        self.last_run_stats = {
            'target': self.target_name.lower(),
            'total_playlists_configured': total_playlists,
            'successful_syncs': successful_syncs,
            'failed_syncs': total_playlists - successful_syncs,
            'total_tracks_found': total_tracks_found,
            'total_tracks_attempted': total_tracks_attempted,
            'total_sync_time': total_sync_time,
            'cache_used': cache_used,
            'cache_performance': {
                'cache_hits': cache_stats.get('cache_hits', 0),
                'cache_misses': cache_stats.get('cache_misses', 0),
                'memory_usage_mb': cache_stats.get('current_memory_usage_mb', 0),
                'library_cache_entries': cache_stats.get('memory_cache_entries', 0)
            },
            'sync_results': sync_results,
            'overall_success': successful_syncs > 0
        }
    
    def _log_final_statistics(self):
        """Log comprehensive run statistics including cache performance"""
        stats = self.last_run_stats
        
        self.logger.info("=" * 70)
        self.logger.info("PLAYLIST SYNC STATISTICS")
        self.logger.info("=" * 70)
        
        self.logger.info(f"Target: {self.target_name}")
        username = self.config.get('LISTENBRAINZ_USERNAME', '')
        self.logger.info(f"Source: ListenBrainz ({username})")
        self.logger.info(f"Playlists Configured: {stats['total_playlists_configured']}")
        self.logger.info(f"Successful Syncs: {stats['successful_syncs']}")
        self.logger.info(f"Failed Syncs: {stats['failed_syncs']}")
        self.logger.info(f"Total Tracks Found: {stats['total_tracks_found']:,}")
        self.logger.info(f"Total Tracks Attempted: {stats['total_tracks_attempted']:,}")
        self.logger.info(f"Total Sync Time: {stats['total_sync_time']:.1f}s")
        
        if stats['total_tracks_attempted'] > 0:
            success_rate = (stats['total_tracks_found'] / stats['total_tracks_attempted'] * 100)
            self.logger.info(f"Track Success Rate: {success_rate:.1f}%")
        
        # Log cache performance
        if stats['cache_used']:
            cache_perf = stats['cache_performance']
            total_cache_ops = cache_perf['cache_hits'] + cache_perf['cache_misses']
            if total_cache_ops > 0:
                cache_hit_rate = (cache_perf['cache_hits'] / total_cache_ops * 100)
                self.logger.info(f"Library Cache Performance:")
                self.logger.info(f"  Cache Hit Rate: {cache_hit_rate:.1f}% ({cache_perf['cache_hits']}/{total_cache_ops})")
                self.logger.info(f"  Memory Usage: {cache_perf['memory_usage_mb']:.1f}MB")
                self.logger.info(f"  Libraries Cached: {cache_perf['library_cache_entries']}")
                
                # Estimate performance improvement
                if stats['total_sync_time'] > 0:
                    estimated_without_cache = stats['total_sync_time'] * 6  # Conservative 6x estimate
                    estimated_savings = estimated_without_cache - stats['total_sync_time']
                    self.logger.info(f"  Estimated Time Saved: {estimated_savings:.1f}s ({estimated_without_cache:.1f}s → {stats['total_sync_time']:.1f}s)")
        else:
            self.logger.info("Library Cache: Not used (live API searches)")
        
        # Log individual playlist results
        self.logger.info("")
        self.logger.info("Individual Playlist Results:")
        for playlist_key, result in stats['sync_results'].items():
            status = "✅" if result['success'] else "❌"
            cache_indicator = "🚀" if result.get('cache_used') else "🐌"
            sync_time = result.get('sync_time', 0)
            self.logger.info(f"  {status} {cache_indicator} {result['playlist_title']}: {result['tracks_found']}/{result['tracks_total']} tracks ({sync_time:.1f}s)")
            if not result['success'] and result['error']:
                self.logger.info(f"    Error: {result['error']}")
        
        self.logger.info("=" * 70)
    
    async def _cleanup_old_playlists(self) -> None:
        """Clean up old playlists based on retention settings"""
        try:
            self.logger.info("Starting playlist cleanup based on retention settings...")
            
            # Get all playlists from target
            playlists = await self._get_all_playlists()
            if not playlists:
                self.logger.warning("No playlists found for cleanup")
                return
            
            self.logger.info(f"Found {len(playlists)} ListenBrainz playlists for cleanup")
            if playlists:
                playlist_titles = [p.get("title", p.get("Name", "")) for p in playlists]
                self.logger.info(f"Playlist titles found: {playlist_titles}")
            else:
                self.logger.warning("No playlists found - this might indicate an issue with playlist retrieval")
            
            # Group playlists by type and date
            playlist_groups = self._group_playlists_by_type_and_date(playlists)
            
            # Log what was found
            for playlist_type, playlists_by_date in playlist_groups.items():
                if playlists_by_date:
                    dates = sorted(playlists_by_date.keys())
                    self.logger.info(f"Found {playlist_type} playlists: {dates}")
                else:
                    self.logger.info(f"No {playlist_type} playlists found")
            
            # Clean up each playlist type
            total_cleaned = 0
            for playlist_type, playlists_by_date in playlist_groups.items():
                if playlists_by_date:
                    cleaned_count = self._cleanup_playlist_type(playlist_type, playlists_by_date)
                    total_cleaned += cleaned_count
            
            if total_cleaned > 0:
                self.logger.info(f"Cleaned up {total_cleaned} old playlists")
            else:
                self.logger.info("No old playlists needed cleanup")
                
        except Exception as e:
            self.logger.error(f"Error during playlist cleanup: {e}")
    
    async def _get_all_playlists(self) -> List[Dict[str, Any]]:
        """Get all playlists from target client - simplified version"""
        try:
            self.logger.info(f"Getting all playlists from {self.target_name}...")
            
            if self.target_name == 'Plex':
                # Use the simple direct API call
                self.logger.info("Calling Plex API /playlists endpoint...")
                results = self.target_client._get("/playlists")
                media_container = results.get("MediaContainer", {})
                all_playlists = media_container.get("Metadata", [])
                
                self.logger.info(f"Plex API returned {len(all_playlists)} total playlists")
                
                # Filter for ListenBrainz playlists (those starting with [LB])
                lb_playlists = [p for p in all_playlists if p.get("title", "").startswith("[LB]")]
                
                self.logger.info(f"Found {len(lb_playlists)} ListenBrainz playlists")
                if lb_playlists:
                    playlist_titles = [p.get("title", "") for p in lb_playlists]
                    self.logger.info(f"ListenBrainz playlist titles: {playlist_titles}")
                
                return lb_playlists
                
            elif self.target_name == 'Jellyfin':
                # Use Jellyfin API
                playlists = self.target_client.get_playlists_sync()
                lb_playlists = [p for p in playlists if p.get("Name", "").startswith("[LB]")]
                self.logger.info(f"Found {len(lb_playlists)} ListenBrainz playlists in Jellyfin")
                return lb_playlists
            else:
                self.logger.warning(f"Unknown target type: {self.target_name}")
                return []
            
        except Exception as e:
            self.logger.error(f"Error getting playlists: {e}")
            import traceback
            self.logger.error(f"Traceback: {traceback.format_exc()}")
            return []
    
    def _group_playlists_by_type_and_date(self, playlists: List[Dict[str, Any]]) -> Dict[str, Dict[str, List[Dict[str, Any]]]]:
        """Group playlists by type and date for cleanup"""
        groups = {
            'daily_jams': {},
            'weekly_jams': {},
            'weekly_exploration': {}
        }
        
        for playlist in playlists:
            # Handle different field names for different clients
            if self.target_name == 'Plex':
                title = playlist.get("title", "")
            elif self.target_name == 'Jellyfin':
                title = playlist.get("Name", "")
            else:
                title = playlist.get("title", playlist.get("Name", ""))
            
            # Parse playlist type and date from title
            if "[LB] Daily Jams," in title:
                playlist_type = 'daily_jams'
                date_str = self._extract_date_from_title(title)
            elif "[LB] Weekly Jams," in title:
                playlist_type = 'weekly_jams'
                date_str = self._extract_date_from_title(title)
            elif "[LB] Weekly Exploration," in title:
                playlist_type = 'weekly_exploration'
                date_str = self._extract_date_from_title(title)
            else:
                continue  # Skip non-matching playlists
            
            if date_str:
                if date_str not in groups[playlist_type]:
                    groups[playlist_type][date_str] = []
                groups[playlist_type][date_str].append(playlist)
        
        return groups
    
    def _extract_date_from_title(self, title: str) -> Optional[str]:
        """Extract date string from playlist title"""
        try:
            # Look for patterns like ", Sep-07" or ", Sep-09"
            import re
            match = re.search(r',\s+(\w{3}-\d{2})$', title)
            if match:
                date_str = match.group(1)
                # Convert to a sortable date format
                from datetime import datetime
                try:
                    # Try current year first
                    current_year = datetime.now().year
                    parsed_date = datetime.strptime(f"{date_str} {current_year}", "%b-%d %Y")
                    
                    # If the date is in the future, try previous year
                    if parsed_date > datetime.now():
                        parsed_date = datetime.strptime(f"{date_str} {current_year - 1}", "%b-%d %Y")
                    
                    return parsed_date.strftime("%Y-%m-%d")
                except ValueError:
                    return None
            return None
        except Exception:
            return None
    
    def _cleanup_playlist_type(self, playlist_type: str, playlists_by_date: Dict[str, List[Dict[str, Any]]]) -> int:
        """Clean up old playlists for a specific type"""
        try:
            # Get retention count for this playlist type from command config
            command_config = getattr(self, 'config_json', {})
            
            # Map playlist types to command config keys
            config_key_map = {
                'daily_jams': 'daily_jams_keep',
                'weekly_exploration': 'weekly_exploration_keep', 
                'weekly_jams': 'weekly_jams_keep'
            }
            
            config_key = config_key_map.get(playlist_type)
            if config_key and command_config and config_key in command_config:
                retention_count = command_config.get(config_key, 3)
                self.logger.info(f"Using command config {config_key}={retention_count} for {playlist_type}")
            else:
                # Fallback to global config - this should not happen for playlist retention!
                self.logger.warning(f"Command config not found for {playlist_type}, using default retention=3")
                retention_count = 3
            
            # Sort dates (newest first)
            sorted_dates = sorted(playlists_by_date.keys(), reverse=True)
            
            # Keep only the most recent playlists up to retention count
            playlists_to_keep = sorted_dates[:retention_count]
            playlists_to_delete = sorted_dates[retention_count:]
            
            deleted_count = 0
            
            for date_str in playlists_to_delete:
                playlists = playlists_by_date[date_str]
                for playlist in playlists:
                    # Handle different field names for different clients
                    if self.target_name == 'Plex':
                        playlist_title = playlist.get("title", "")
                        playlist_key = playlist.get("ratingKey", "")
                    elif self.target_name == 'Jellyfin':
                        playlist_title = playlist.get("Name", "")
                        playlist_key = playlist.get("Id", "")
                    else:
                        playlist_title = playlist.get("title", playlist.get("Name", ""))
                        playlist_key = playlist.get("ratingKey", playlist.get("Id", ""))
                    
                    if playlist_key:
                        self.logger.info(f"Deleting old playlist: {playlist_title}")
                        # Use synchronous delete method for both Plex and Jellyfin
                        if self.target_name == 'Jellyfin':
                            success = self.target_client.delete_playlist_sync(playlist_key)
                        else:
                            success = self.target_client.delete_playlist(playlist_key)
                        
                        if success:
                            deleted_count += 1
                        else:
                            self.logger.warning(f"Failed to delete playlist: {playlist_title}")
            
            if deleted_count > 0:
                self.logger.info(f"Cleaned up {deleted_count} old {playlist_type} playlists (kept {len(playlists_to_keep)} most recent)")
            
            return deleted_count
            
        except Exception as e:
            self.logger.error(f"Error cleaning up {playlist_type} playlists: {e}")
            return 0


# Playlist type mapping for future expansion
PLAYLIST_TYPE_MAPPING = {
    'weekly_exploration': {
        'listenbrainz_key': 'weekly_exploration',
        'display_name': 'Weekly Exploration',
        'description': 'Your personalized weekly music discovery playlist from ListenBrainz'
    },
    'weekly_jams': {
        'listenbrainz_key': 'weekly_jams', 
        'display_name': 'Weekly Jams',
        'description': 'Your weekly music recommendations from ListenBrainz'
    },
    'daily_jams': {
        'listenbrainz_key': 'daily_jams',
        'display_name': 'Daily Jams', 
        'description': 'Your daily music recommendations from ListenBrainz'
    }
}
