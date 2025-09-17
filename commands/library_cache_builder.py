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
    
    def __init__(self, config=None):
        super().__init__(config)
        
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
            # Initialize Plex client if configured
            if self.config.get('PLEX_URL') and self.config.get('PLEX_TOKEN'):
                self.clients['plex'] = PlexClient(self.config)
                self.logger.info("Plex client initialized for cache building")
            
            # Initialize Jellyfin client if configured
            if (self.config.get('JELLYFIN_URL') and 
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
        """Build cache for a specific target"""
        try:
            self.logger.info(f"Building library cache for {target} (force_rebuild={force_rebuild})")
            start_time = time.time()
            
            client = self.clients[target]
            
            # Register client with cache manager if not already registered
            if target not in self.library_cache_manager.registered_clients:
                self.library_cache_manager.register_client(target, client)
                self.logger.debug(f"Registered {target} client with cache manager")
            
            # Check if cache exists and is fresh (unless force rebuild is requested)
            if not force_rebuild:
                existing_cache = self.library_cache_manager.get_library_cache(target)
                if existing_cache:
                    cache_age_hours = (time.time() - existing_cache.get('built_at', 0)) / 3600
                    ttl_hours = self.get_target_ttl_days(target) * 24
                    
                    if cache_age_hours < ttl_hours:
                        self.logger.info(f"Cache for {target} is fresh ({cache_age_hours:.1f}h old, TTL: {ttl_hours}h)")
                        return {
                            'success': True,
                            'cached': True,
                            'age_hours': cache_age_hours,
                            'message': 'Cache was already fresh'
                        }
                    else:
                        self.logger.info(f"Cache for {target} is stale ({cache_age_hours:.1f}h old, TTL: {ttl_hours}h), rebuilding")
            else:
                self.logger.info(f"Force rebuild requested for {target}, invalidating existing cache")
                # Invalidate existing cache
                self.library_cache_manager.invalidate_cache(target)
            
            # Build new cache
            self.logger.info(f"Building fresh cache for {target}")
            cache_data = client.build_library_cache()
            
            if not cache_data:
                return {
                    'success': False,
                    'error': 'No cache data returned from client'
                }
            
            # Store cache in cache manager
            self.library_cache_manager.set_library_cache(target, cache_data)
            
            build_time = time.time() - start_time
            track_count = cache_data.get('total_tracks', 0)
            
            self.logger.info(f"Successfully built {target} cache: {track_count:,} tracks in {build_time:.1f}s")
            
            return {
                'success': True,
                'cached': False,
                'track_count': track_count,
                'build_time_seconds': build_time,
                'message': f'Built fresh cache with {track_count:,} tracks'
            }
            
        except Exception as e:
            self.logger.error(f"Failed to build cache for {target}: {e}")
            import traceback
            self.logger.error(f"Traceback: {traceback.format_exc()}")
            return {
                'success': False,
                'error': str(e)
            }
    
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
