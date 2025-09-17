#!/usr/bin/env python3
"""
Centralized cache client utility for music library clients
Provides consistent cache hit/miss recording and statistics across all clients
"""

import logging
import time
from typing import Dict, Any, Optional
from utils.library_cache_manager import get_library_cache_manager


class CacheClient:
    """
    Centralized cache client for music library clients
    Provides consistent cache operations and statistics recording
    """
    
    def __init__(self, client_name: str, config: Dict[str, Any]):
        """
        Initialize cache client
        
        Args:
            client_name: Name of the client (e.g., 'plex', 'jellyfin')
            config: Configuration dictionary
        """
        self.client_name = client_name
        self.config = config
        self.logger = logging.getLogger(f'cmdarr.cache_client.{client_name}')
        
        # Check if library cache is enabled for this client
        self.library_cache_enabled = config.get(f'LIBRARY_CACHE_{client_name.upper()}_ENABLED', False)
        
        if self.library_cache_enabled:
            self.logger.debug(f"Library cache enabled for {client_name}")
        else:
            self.logger.debug(f"Library cache disabled for {client_name}")
    
    def record_cache_hit(self) -> None:
        """Record a library cache hit"""
        if not self.library_cache_enabled:
            return
            
        try:
            cache_manager = get_library_cache_manager(self.config)
            cache_manager.record_cache_hit(self.client_name)
        except Exception as e:
            self.logger.debug(f"Failed to record cache hit: {e}")
    
    def record_cache_miss(self) -> None:
        """Record a library cache miss"""
        if not self.library_cache_enabled:
            return
            
        try:
            cache_manager = get_library_cache_manager(self.config)
            cache_manager.record_cache_miss(self.client_name)
        except Exception as e:
            self.logger.debug(f"Failed to record cache miss: {e}")
    
    def get_cache_stats(self) -> Optional[Dict[str, Any]]:
        """Get cache statistics for this client"""
        if not self.library_cache_enabled:
            return None
            
        try:
            cache_manager = get_library_cache_manager(self.config)
            return cache_manager.get_client_stats(self.client_name)
        except Exception as e:
            self.logger.debug(f"Failed to get cache stats: {e}")
            return None
    
    def register_with_cache_manager(self, client_instance) -> None:
        """Register client instance with library cache manager"""
        if not self.library_cache_enabled:
            return
            
        try:
            cache_manager = get_library_cache_manager(self.config)
            cache_manager.register_client(self.client_name, client_instance)
            self.logger.debug(f"Registered {self.client_name} client with library cache manager")
        except Exception as e:
            self.logger.warning(f"Failed to register client with library cache manager: {e}")
    
    def is_cache_enabled(self) -> bool:
        """Check if library cache is enabled for this client"""
        return self.library_cache_enabled
    
    def get_cache_stats_summary(self) -> Dict[str, Any]:
        """Get a summary of cache statistics for this client"""
        stats = self.get_cache_stats()
        if not stats:
            return {
                'enabled': False,
                'cache_hits': 0,
                'cache_misses': 0,
                'hit_rate': 0.0,
                'last_used': None
            }
        
        return {
            'enabled': True,
            'cache_hits': stats.get('cache_hits', 0),
            'cache_misses': stats.get('cache_misses', 0),
            'hit_rate': stats.get('hit_rate', 0.0),
            'last_used': stats.get('last_used')
        }
    
    def log_cache_performance(self, operation_name: str, start_time: float) -> None:
        """Log cache performance metrics for an operation"""
        if not self.library_cache_enabled:
            return
            
        try:
            duration = time.time() - start_time
            stats = self.get_cache_stats()
            if stats:
                hit_rate = stats.get('hit_rate', 0.0)
                total_ops = stats.get('cache_hits', 0) + stats.get('cache_misses', 0)
                self.logger.info(f"Cache performance for {operation_name}: {duration:.2f}s, {total_ops} operations, {hit_rate:.1%} hit rate")
        except Exception as e:
            self.logger.debug(f"Failed to log cache performance: {e}")


def create_cache_client(client_name: str, config: Dict[str, Any]) -> CacheClient:
    """
    Factory function to create a cache client
    
    Args:
        client_name: Name of the client (e.g., 'plex', 'jellyfin')
        config: Configuration dictionary
        
    Returns:
        CacheClient instance
    """
    return CacheClient(client_name, config)
