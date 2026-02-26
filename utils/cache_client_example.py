#!/usr/bin/env python3
"""
Example usage of the centralized cache client utility
Demonstrates how to integrate cache operations in music library clients
"""

from utils.cache_client import create_cache_client


class ExampleMusicClient:
    """Example music client showing how to use centralized cache operations"""
    
    def __init__(self, config):
        self.config = config
        self.client_name = 'example_client'
        
        # Initialize centralized cache client
        self.cache_client = create_cache_client(self.client_name, config)
        
        # Register with cache manager if enabled
        if self.cache_client.is_cache_enabled():
            self.cache_client.register_with_cache_manager(self)
    
    def search_for_track(self, artist: str, title: str):
        """Example track search with cache operations"""
        # Check if we have cached data
        if self.cache_client.is_cache_enabled():
            # Try cached search first
            cached_result = self._search_cached_library(artist, title)
            if cached_result:
                # Record cache hit
                self.cache_client.record_cache_hit()
                return cached_result
            
            # Record cache miss
            self.cache_client.record_cache_miss()
        
        # Fallback to live API search
        return self._search_live_api(artist, title)
    
    def get_cache_performance_summary(self):
        """Get cache performance summary"""
        return self.cache_client.get_cache_stats_summary()
    
    def log_operation_performance(self, operation_name: str, start_time: float):
        """Log cache performance for an operation"""
        self.cache_client.log_cache_performance(operation_name, start_time)
    
    def _search_cached_library(self, artist: str, title: str):
        """Search in cached library data"""
        # Implementation would go here
        return None
    
    def _search_live_api(self, artist: str, title: str):
        """Search using live API"""
        # Implementation would go here
        return None


# Example usage:
if __name__ == "__main__":
    config = {
        'LIBRARY_CACHE_EXAMPLE_CLIENT_ENABLED': True,
        'LIBRARY_CACHE_PLEX_TTL_DAYS': 30
    }
    
    client = ExampleMusicClient(config)
    
    # Search for a track (automatically handles cache operations)
    result = client.search_for_track("Artist Name", "Track Title")
    
    # Get cache performance summary
    stats = client.get_cache_performance_summary()
    print(f"Cache enabled: {stats['enabled']}")
    print(f"Hit rate: {stats['hit_rate']:.1%}")
    print(f"Total operations: {stats['cache_hits'] + stats['cache_misses']}")
