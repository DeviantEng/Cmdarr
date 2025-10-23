#!/usr/bin/env python3
"""
Library Cache Builder Command
Builds and maintains library caches for configured music players (Plex, Jellyfin)
This is a helper command that runs independently of playlist sync operations
"""

import asyncio
import time
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta

from .command_base import BaseCommand
from clients.client_plex import PlexClient
from clients.client_jellyfin import JellyfinClient
from utils.library_cache_manager import get_library_cache_manager


class LibraryCacheBuilderCommand(BaseCommand):
    """
    Library Cache Builder - Helper command for building music library caches
    Runs independently of playlist sync operations for better performance
    """
    
    def __init__(self, config=None, execution_id=None):
        super().__init__(config, execution_id)
        
        # Initialize library cache manager
        self.library_cache_manager = get_library_cache_manager(self.config)
        
        # Initialize clients for cache building
        self.clients = {}
        self._initialize_clients()
        
        # Store statistics for reporting
        self.last_run_stats = {}
    
    def _initialize_clients(self):
        """Initialize configured clients for cache building"""
        try:
            # Initialize Plex client if enabled and configured
            if (self.config.get('PLEX_CLIENT_ENABLED', False) and 
                self.config.get('PLEX_URL') and 
                self.config.get('PLEX_TOKEN')):
                self.clients['plex'] = PlexClient(self.config)
                self.logger.info("Plex client initialized for cache building")
            
            # Initialize Jellyfin client if enabled and configured
            if (self.config.get('JELLYFIN_CLIENT_ENABLED', False) and
                self.config.get('JELLYFIN_URL') and 
                self.config.get('JELLYFIN_TOKEN') and 
                self.config.get('JELLYFIN_USER_ID')):
                self.clients['jellyfin'] = JellyfinClient(self.config)
                self.logger.info("Jellyfin client initialized for cache building")
            
            if not self.clients:
                self.logger.warning("No music players configured for cache building")
                
        except Exception as e:
            self.logger.error(f"Failed to initialize clients: {e}")
    
    def get_name(self) -> str:
        """Return command name."""
        return "library_cache_builder"
    
    def get_description(self) -> str:
        """Return command description."""
        return "Builds and maintains library caches for configured music players"
    
    def get_logger_name(self) -> str:
        """Return logger name for this command."""
        return "library_cache_builder"
    
    def is_helper_command(self) -> bool:
        """This is a helper command - not shown in UI commands list"""
        return True
    
    def get_schedule_hours(self) -> int:
        """Get cache building schedule in hours"""
        return self.config.get('LIBRARY_CACHE_SCHEDULE_HOURS', 24)
    
    def is_target_enabled(self, target: str) -> bool:
        """Check if cache building is enabled for a specific target"""
        return self.config.get(f'LIBRARY_CACHE_{target.upper()}_ENABLED', False)
    
    def get_target_ttl_days(self, target: str) -> int:
        """Get cache TTL in days for a specific target"""
        return self.config.get(f'LIBRARY_CACHE_{target.upper()}_TTL_DAYS', 30)
    
    def execute(self, force_rebuild: bool = False, target_filter: Optional[str] = None) -> bool:
        """Execute the library cache building process"""
        try:
            self.logger.info(f"Starting library cache building process (force_rebuild={force_rebuild}, target_filter={target_filter})")
            
            # Check which targets are enabled
            enabled_targets = [target for target in self.clients.keys() 
                             if self.is_target_enabled(target)]
            
            # Apply target filter if specified
            if target_filter and target_filter in enabled_targets:
                enabled_targets = [target_filter]
                self.logger.info(f"Filtered to target: {target_filter}")
            elif target_filter and target_filter not in enabled_targets:
                self.logger.warning(f"Target filter '{target_filter}' not in enabled targets: {enabled_targets}")
                return False
            
            if not enabled_targets:
                self.logger.info("No targets enabled for cache building")
                return True
            
            self.logger.info(f"Building caches for enabled targets: {', '.join(enabled_targets)}")
            
            # Build caches for each enabled target
            results = {}
            for target in enabled_targets:
                try:
                    result = self._build_target_cache(target, force_rebuild=force_rebuild)
                    results[target] = result
                except Exception as e:
                    self.logger.error(f"Failed to build cache for {target}: {e}")
                    results[target] = {'success': False, 'error': str(e)}
            
            # Store results for reporting
            self.last_run_stats = {
                'timestamp': datetime.now().isoformat(),
                'results': results
            }
            
            # Log summary
            successful = [target for target, result in results.items() if result.get('success', False)]
            failed = [target for target, result in results.items() if not result.get('success', False)]
            
            if successful:
                self.logger.info(f"Successfully built caches for: {', '.join(successful)}")
            if failed:
                self.logger.warning(f"Failed to build caches for: {', '.join(failed)}")
            
            return len(successful) > 0
            
        except Exception as e:
            self.logger.error(f"Library cache building failed: {e}")
            import traceback
            self.logger.error(f"Traceback: {traceback.format_exc()}")
            return False
    
    def _build_target_cache(self, target: str, force_rebuild: bool = False) -> Dict[str, Any]:
        """Build cache for a specific target using smart incremental approach"""
        try:
            self.logger.info(f"Building library cache for {target} (force_rebuild={force_rebuild})")
            start_time = time.time()
            
            client = self.clients[target]
            
            # Register client with cache manager if not already registered
            if target not in self.library_cache_manager.registered_clients:
                self.library_cache_manager.register_client(target, client)
                self.logger.debug(f"Registered {target} client with cache manager")
            
            # Handle force rebuild vs smart refresh
            if force_rebuild:
                self.logger.info(f"Force rebuild requested for {target}, invalidating existing cache")
                # Invalidate existing cache
                self.library_cache_manager.invalidate_cache(target)
            else:
                # Smart refresh - always run incremental update (36-hour lookback)
                existing_cache = self.library_cache_manager.get_library_cache(target)
                if existing_cache:
                    cache_age_hours = (time.time() - existing_cache.get('built_at', 0)) / 3600
                    ttl_hours = self.get_target_ttl_days(target) * 24
                    self.logger.info(f"Smart refresh for {target}: cache is {cache_age_hours:.1f}h old (TTL: {ttl_hours}h), running incremental update")
                else:
                    self.logger.info(f"Smart refresh for {target}: no existing cache, will perform full rebuild")
            
            # Use smart incremental cache building
            cache_data = self._build_smart_cache(target, client, force_rebuild)
            
            if not cache_data:
                return {
                    'success': False,
                    'error': 'No cache data returned from smart cache building'
                }
            
            # Store cache in cache manager
            self.library_cache_manager.set_library_cache(target, cache_data)
            
            build_time = time.time() - start_time
            track_count = cache_data.get('total_tracks', 0)
            new_tracks = cache_data.get('new_tracks_added', 0)
            
            self.logger.info(f"Successfully built {target} cache: {track_count:,} total tracks ({new_tracks:,} new) in {build_time:.1f}s")
            
            return {
                'success': True,
                'cached': False,
                'track_count': track_count,
                'new_tracks_added': new_tracks,
                'build_time_seconds': build_time,
                'message': f'Built fresh cache with {track_count:,} tracks ({new_tracks:,} new)'
            }
            
        except Exception as e:
            self.logger.error(f"Failed to build cache for {target}: {e}")
            import traceback
            self.logger.error(f"Traceback: {traceback.format_exc()}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def _build_smart_cache(self, target: str, client, force_rebuild: bool = False) -> Dict[str, Any]:
        """Build cache using smart incremental approach with 36-hour lookback"""
        try:
            # Get existing cache data
            existing_cache = self.library_cache_manager.get_library_cache(target)
            
            # Debug: Check the type and structure of existing_cache
            self.logger.debug(f"existing_cache type: {type(existing_cache)}")
            if existing_cache:
                self.logger.debug(f"existing_cache keys: {list(existing_cache.keys()) if isinstance(existing_cache, dict) else 'Not a dict'}")
                if isinstance(existing_cache, dict) and 'tracks' in existing_cache:
                    tracks = existing_cache['tracks']
                    self.logger.debug(f"tracks type: {type(tracks)}, length: {len(tracks) if hasattr(tracks, '__len__') else 'No length'}")
            
            if force_rebuild or not existing_cache:
                # Full rebuild - use existing method
                self.logger.info(f"Performing full cache rebuild for {target}")
                return client.build_library_cache()
            
            # Smart incremental rebuild
            self.logger.info(f"Performing smart incremental cache update for {target} (36-hour lookback)")
            
            # Safety check: ensure existing_cache is a dictionary
            if not isinstance(existing_cache, dict):
                self.logger.error(f"existing_cache is not a dictionary, got {type(existing_cache)}. Falling back to full rebuild.")
                return client.build_library_cache()
            
            # Get tracks added in last 36 hours (1.5 days)
            lookback_hours = 36
            lookback_days = lookback_hours / 24
            
            new_tracks = []
            total_tracks = existing_cache.get('total_tracks', 0)
            incremental_start_time = time.time()
            
            if target == 'plex':
                # Get all music libraries
                libraries = client.get_music_libraries()
                
                for library in libraries:
                    library_key = library['key']
                    library_name = library.get('title', f'Library {library_key}')
                    
                    # Get recently added tracks
                    recent_tracks = client.get_recently_added_tracks(library_key, days=lookback_days)
                    
                    if recent_tracks:
                        self.logger.info(f"Found {len(recent_tracks)} tracks added in last {lookback_days:.1f} days in {library_name}")
                        
                        # Process each track
                        for track in recent_tracks:
                            track_key = track.get('key')
                            if track_key:
                                # Check if track already exists in cache
                                existing_tracks = existing_cache.get('tracks', [])
                                existing_track = None
                                
                                # Find existing track by key
                                for existing in existing_tracks:
                                    if existing.get('key') == track_key:
                                        existing_track = existing
                                        break
                                
                                if not existing_track:
                                    # New track - add to cache
                                    new_tracks.append(track)
                                    total_tracks += 1
                                else:
                                    # Track exists but might have been updated
                                    # Check if metadata changed
                                    if self._track_metadata_changed(track, existing_track):
                                        new_tracks.append(track)
                                        self.logger.debug(f"Updated metadata for track: {track.get('title', 'Unknown')}")
                    else:
                        self.logger.debug(f"No new tracks found in {library_name}")
            
            elif target == 'jellyfin':
                # Jellyfin implementation would go here
                self.logger.info("Jellyfin smart cache building not yet implemented, falling back to full rebuild")
                return client.build_library_cache()
            
            incremental_time = time.time() - incremental_start_time
            
            # Update cache data
            if new_tracks:
                # Add new tracks to existing cache
                existing_tracks = existing_cache.get('tracks', [])
                for track in new_tracks:
                    track_key = track.get('key')
                    if track_key:
                        # Check if track already exists and update it, or add new
                        found = False
                        for i, existing in enumerate(existing_tracks):
                            if existing.get('key') == track_key:
                                existing_tracks[i] = track  # Update existing
                                found = True
                                break
                        
                        if not found:
                            existing_tracks.append(track)  # Add new
                
                # Update cache data
                cache_data = existing_cache.copy()
                cache_data['tracks'] = existing_tracks
                cache_data['total_tracks'] = total_tracks
                cache_data['new_tracks_added'] = len(new_tracks)
                cache_data['built_at'] = time.time()
                cache_data['last_incremental_update'] = time.time()
                
                self.logger.info(f"Smart cache update complete: added {len(new_tracks)} new tracks in {incremental_time:.1f}s")
                self.logger.info(f"Performance: {len(new_tracks)} tracks processed vs {total_tracks:,} total cached (efficiency: {len(new_tracks)/total_tracks*100:.2f}% new)")
                return cache_data
            else:
                # No new tracks found - update timestamp but keep existing data
                cache_data = existing_cache.copy()
                cache_data['last_incremental_update'] = time.time()
                cache_data['new_tracks_added'] = 0
                
                self.logger.info(f"Smart cache update complete: no new tracks found in {incremental_time:.1f}s")
                self.logger.info(f"Performance: 0 tracks processed vs {total_tracks:,} total cached (efficiency: 100% - no work needed)")
                return cache_data
                
        except Exception as e:
            self.logger.error(f"Smart cache building failed for {target}: {e}")
            # Fall back to full rebuild
            self.logger.info(f"Falling back to full cache rebuild for {target}")
            return client.build_library_cache()
    
    def _track_metadata_changed(self, new_track: Dict, existing_track: Dict) -> bool:
        """Check if track metadata has changed"""
        # Compare key metadata fields
        fields_to_check = ['title', 'grandparentTitle', 'parentTitle', 'addedAt', 'updatedAt']
        
        for field in fields_to_check:
            if new_track.get(field) != existing_track.get(field):
                return True
        
        return False
    
    def get_last_run_stats(self) -> Dict[str, Any]:
        """Get statistics from the last run"""
        return self.last_run_stats
    
    async def test_connections(self) -> Dict[str, bool]:
        """Test connections to all configured targets"""
        results = {}
        for target, client in self.clients.items():
            try:
                connected = await client.test_connection()
                results[target] = connected
                if connected:
                    self.logger.info(f"✓ {target} connection successful")
                else:
                    self.logger.warning(f"✗ {target} connection failed")
            except Exception as e:
                self.logger.error(f"✗ {target} connection error: {e}")
                results[target] = False
        
        return results
