#!/usr/bin/env python3
"""
Library Cache Manager
Centralized music library caching for dramatic playlist sync performance improvements
"""

import json
import os
import psutil
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List, Tuple
from sqlalchemy import func
from .logger import get_logger
from database.database import get_database_manager
from database.models import LibraryCache


class LibraryCacheManager:
    """
    Centralized music library cache management for playlist operations
    
    Features:
    - Client-agnostic caching (Plex, Jellyfin, future services)
    - Smart memory management with configurable limits
    - SQLAlchemy persistence with configurable TTL
    - On-demand cache refresh when stale tracks detected
    - Batch operation support for multiple playlist commands
    """
    
    def __init__(self, config):
        self.config = config
        self.logger = get_logger('cmdarr.library_cache')
        self.db_manager = get_database_manager()
        
        # Registered clients for cache operations
        self.registered_clients = {}
        
        # In-memory cache for active batch operations
        self.memory_cache = {}
        self.cache_active = False
        
        # Global performance tracking (for overall system monitoring)
        self.global_stats = {
            'total_cache_hits': 0,
            'total_cache_misses': 0,
            'memory_usage_mb': 0,
            'last_cache_build': None
        }
        
        # Per-client performance tracking (isolated by client type)
        # Preserve existing stats if available, otherwise initialize fresh
        if hasattr(self, 'client_stats') and self.client_stats:
            self.logger.info("Library cache manager initialized with preserved client stats")
        else:
            self.client_stats = {
                'plex': {
                    'cache_hits': 0,
                    'cache_misses': 0,
                    'last_used': None,
                    'hit_rate': 0.0
                },
                'jellyfin': {
                    'cache_hits': 0,
                    'cache_misses': 0,
                    'last_used': None,
                    'hit_rate': 0.0
                }
            }
            self.logger.info("Library cache manager initialized with fresh client stats")
        
        # TEMPORARY: Add compatibility property to avoid stats error
        # TODO: Remove this once we find the source of the error
        self.stats = self.global_stats
    
    def register_client(self, client_type: str, client_instance) -> None:
        """
        Register a music library client for caching operations
        
        Client must implement:
        - get_cache_key(library_key) -> str
        - get_cache_ttl() -> int
        - build_library_cache(library_key) -> Dict
        - process_cached_library(cached_data) -> Dict
        - search_cached_library(track_name, artist_name, cached_data) -> Optional[str]
        - verify_track_exists(rating_key) -> bool
        """
        required_methods = [
            'get_cache_key', 'get_cache_ttl', 'build_library_cache',
            'process_cached_library', 'search_cached_library', 'verify_track_exists'
        ]
        
        for method in required_methods:
            if not hasattr(client_instance, method):
                raise ValueError(f"Client {client_type} missing required method: {method}")
        
        self.registered_clients[client_type] = client_instance
        self.logger.info(f"Registered client: {client_type}")
        
        # Validate client type is supported
        if client_type not in self.client_stats:
            self.logger.warning(f"Unsupported client type '{client_type}', stats may not be tracked properly")
        else:
            self.logger.info(f"Client '{client_type}' registered with stats: {self.client_stats[client_type]}")
    
    def get_library_cache(self, client_type: str, library_key: str = None) -> Optional[Dict[str, Any]]:
        """
        Get library cache for a client, building if necessary
        
        Returns:
            Dictionary with cache data or None if client not registered
        """
        if client_type not in self.registered_clients:
            self.logger.error(f"Client {client_type} not registered")
            return None
        
        client = self.registered_clients[client_type]
        cache_key = client.get_cache_key(library_key)
        
        # Check memory cache first if active
        if self.cache_active and cache_key in self.memory_cache:
            self.global_stats['total_cache_hits'] += 1
            self.logger.debug(f"Memory cache hit: {cache_key}")
            return self.memory_cache[cache_key]
        
        # Check SQLite cache
        cached_data = self._get_from_sqlite(cache_key, client_type, library_key)
        if cached_data:
            self.global_stats['total_cache_hits'] += 1
            self.logger.debug(f"SQLite cache hit: {cache_key}")
            
            # Load into memory cache if active
            self._load_to_memory_cache(cache_key, cached_data)
            return cached_data
        
        # Build new cache
        self.global_stats['total_cache_misses'] += 1
        return self._build_and_store_cache(client, client_type, library_key, cache_key)
    
    def get_library_cache_direct(self, client_type: str, library_key: str = None) -> Optional[Dict[str, Any]]:
        """
        Get library cache data directly from database without requiring client registration
        Used for status reporting and cache inspection
        
        Returns:
            Dictionary with cache data or None if not found
        """
        try:
            with self.db_manager.get_session_context() as session:
                # Find the most recent cache entry for this client type
                cache_entry = session.query(LibraryCache).filter(
                    LibraryCache.client_type == client_type,
                    LibraryCache.expires_at > datetime.utcnow()
                ).order_by(LibraryCache.created_at.desc()).first()
                
                if cache_entry:
                    # Return raw cache data without client processing
                    return cache_entry.cache_data
                
                return None
                
        except Exception as e:
            self.logger.warning(f"Direct cache retrieval error for {client_type}: {e}")
            return None
    
    def _get_from_sqlite(self, cache_key: str, client_type: str, library_key: str) -> Optional[Dict[str, Any]]:
        """Retrieve cache data from SQLite if not expired"""
        try:
            with self.db_manager.get_session_context() as session:
                cache_entry = session.query(LibraryCache).filter(
                    LibraryCache.cache_key == cache_key,
                    LibraryCache.expires_at > datetime.utcnow()
                ).first()
                
                if cache_entry:
                    # Process through client for any client-specific transformations
                    client = self.registered_clients[client_type]
                    processed_data = client.process_cached_library(cache_entry.cache_data)
                    
                    self.logger.debug(f"Retrieved {cache_entry.track_count:,} tracks from SQLite cache (created: {cache_entry.created_at})")
                    return processed_data
                
                return None
                
        except Exception as e:
            self.logger.warning(f"Library cache retrieval error: {e}")
            return None
    
    def _build_and_store_cache(self, client, client_type: str, library_key: str, cache_key: str) -> Optional[Dict[str, Any]]:
        """Build new cache data and store in SQLite"""
        try:
            # Build cache through client
            self.logger.info(f"Building library cache for {client_type}:{library_key}")
            cache_data = client.build_library_cache(library_key)
            
            if not cache_data:
                self.logger.warning(f"Failed to build cache for {client_type}:{library_key}")
                return None
            
            # Count tracks
            track_count = len(cache_data.get('tracks', {}))
            ttl_days = client.get_cache_ttl()
            
            # Store in SQLite
            self._store_in_sqlite(cache_key, client_type, library_key, cache_data, track_count, ttl_days)
            
            # Load into memory cache if active
            self._load_to_memory_cache(cache_key, cache_data)
            
            self.global_stats['last_cache_build'] = datetime.utcnow()
            self.logger.info(f"Built and cached {track_count:,} tracks for {client_type}:{library_key}")
            return cache_data
            
        except Exception as e:
            self.logger.error(f"Failed to build cache for {client_type}:{library_key}: {e}")
            return None
    
    def _store_in_sqlite(self, cache_key: str, client_type: str, library_key: str, 
                        cache_data: Dict[str, Any], track_count: int, ttl_days: int) -> None:
        """Store cache data in SQLite with TTL"""
        try:
            expires_at = datetime.utcnow() + timedelta(days=ttl_days)
            schema_version = cache_data.get('schema_version', 'unknown')
            
            # Handle None library_key - use a default value
            stored_library_key = library_key if library_key is not None else 'default'
            
            with self.db_manager.get_session_context() as session:
                # Check if entry exists
                existing = session.query(LibraryCache).filter(
                    LibraryCache.cache_key == cache_key
                ).first()
                
                if existing:
                    # Update existing entry
                    existing.client_type = client_type
                    existing.library_key = stored_library_key
                    existing.schema_version = schema_version
                    existing.cache_data = cache_data
                    existing.track_count = track_count
                    existing.expires_at = expires_at
                else:
                    # Create new entry
                    cache_entry = LibraryCache(
                        cache_key=cache_key,
                        client_type=client_type,
                        library_key=stored_library_key,
                        schema_version=schema_version,
                        cache_data=cache_data,
                        track_count=track_count,
                        expires_at=expires_at
                    )
                    session.add(cache_entry)
                
                session.commit()
                self.logger.debug(f"Stored library cache: {cache_key} ({track_count:,} tracks)")
                
        except Exception as e:
            self.logger.warning(f"Library cache storage error: {e}")
    
    def _load_to_memory_cache(self, cache_key: str, cache_data: Dict[str, Any]) -> None:
        """Load cache data into memory if within limits"""
        if not self.cache_active:
            return
        
        # Estimate memory usage
        estimated_size = self._estimate_cache_size(cache_data)
        current_memory = psutil.Process().memory_info().rss / 1024 / 1024  # MB
        
        # Simple memory limit check (500MB max)
        if current_memory + estimated_size > 500:
            self.logger.debug("Memory limit reached, skipping memory cache")
            return
        
        self.memory_cache[cache_key] = cache_data
        self.global_stats['memory_usage_mb'] = current_memory + estimated_size
        self.logger.debug(f"Loaded to memory cache: {cache_key} (~{estimated_size:.1f}MB)")
    
    def _estimate_cache_size(self, cache_data: Dict[str, Any]) -> float:
        """Estimate memory usage of cache data in MB"""
        try:
            # Rough estimation: JSON size * 1.5 for Python object overhead
            json_size = len(json.dumps(cache_data))
            return (json_size * 1.5) / 1024 / 1024
        except:
            return 10.0  # Conservative estimate
    
    def keep_memory_cache_during_batch(self) -> None:
        """Enable memory caching for batch operations"""
        if self.cache_active:
            self.logger.debug("Memory cache already active")
            return
        
        self.cache_active = True
        self.logger.debug("Memory cache enabled for batch operations")
    
    def clear_memory_cache(self) -> None:
        """Clear memory cache and disable batch mode"""
        if not self.cache_active:
            return
        
        self.memory_cache.clear()
        self.cache_active = False
        self.global_stats['memory_usage_mb'] = 0
        self.logger.debug("Memory cache cleared and disabled")
    
    def verify_and_refresh_cache(self, client_type: str, library_key: str = None, 
                                sample_track_keys: List[str] = None) -> bool:
        """
        Verify cache validity by testing sample tracks, refresh if stale
        
        Returns:
            True if cache is valid, False if refreshed
        """
        if client_type not in self.registered_clients:
            return False
        
        client = self.registered_clients[client_type]
        cache_key = client.get_cache_key(library_key)
        
        # Get current cache
        cached_data = self.get_library_cache(client_type, library_key)
        if not cached_data:
            return False
        
        # Test sample tracks if provided
        if sample_track_keys:
            stale_count = 0
            for track_key in sample_track_keys[:5]:  # Test up to 5 tracks
                if not client.verify_track_exists(track_key):
                    stale_count += 1
            
            # If more than 20% of sample tracks are stale, refresh cache
            if stale_count > len(sample_track_keys) * 0.2:
                self.logger.info(f"Cache appears stale ({stale_count}/{len(sample_track_keys)} tracks missing), refreshing...")
                self._invalidate_sqlite_cache(cache_key)
                self.get_library_cache(client_type, library_key)  # Rebuild
                return False
        
        return True
    
    def _invalidate_sqlite_cache(self, cache_key: str) -> None:
        """Remove cache entry from SQLite"""
        try:
            with self.db_manager.get_session_context() as session:
                session.query(LibraryCache).filter(
                    LibraryCache.cache_key == cache_key
                ).delete()
                session.commit()
                self.logger.debug(f"Invalidated SQLite cache: {cache_key}")
                
        except Exception as e:
            self.logger.warning(f"Cache invalidation error: {e}")
    
    def invalidate_cache(self, client_type: str, library_key: str = None) -> None:
        """Invalidate cache for a specific client and library"""
        try:
            # Generate cache key
            cache_key = f"{client_type}:{library_key or 'default'}"
            
            # Remove from SQLite
            self._invalidate_sqlite_cache(cache_key)
            
            # Remove from memory cache if present
            if cache_key in self.memory_cache:
                del self.memory_cache[cache_key]
                self.logger.debug(f"Removed {cache_key} from memory cache")
            
            self.logger.info(f"Successfully invalidated cache for {client_type} (library: {library_key or 'default'})")
            
        except Exception as e:
            self.logger.error(f"Failed to invalidate cache for {client_type}: {e}")
    
    def cleanup_expired_cache(self) -> int:
        """Remove expired cache entries and return count of removed items"""
        try:
            with self.db_manager.get_session_context() as session:
                expired_count = session.query(LibraryCache).filter(
                    LibraryCache.expires_at <= datetime.utcnow()
                ).delete()
                
                session.commit()
                
                if expired_count > 0:
                    self.logger.debug(f"Cleaned up {expired_count} expired library cache entries")
                
                return expired_count
                
        except Exception as e:
            self.logger.warning(f"Cache cleanup error: {e}")
            return 0
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache statistics and performance metrics"""
        try:
            with self.db_manager.get_session_context() as session:
                # Count by client type
                cache_counts = {}
                for client_type, count in session.query(LibraryCache.client_type, func.count(LibraryCache.id)).group_by(LibraryCache.client_type).all():
                    cache_counts[client_type] = count
                
                # Total track count
                total_tracks = session.query(func.sum(LibraryCache.track_count)).scalar() or 0
                
                # Get oldest and newest entries
                oldest = session.query(func.min(LibraryCache.created_at)).scalar()
                newest = session.query(func.max(LibraryCache.created_at)).scalar()
                
                return {
                    'cache_counts_by_client': cache_counts,
                    'total_cached_tracks': total_tracks,
                    'memory_cache_entries': len(self.memory_cache),
                    'memory_usage_mb': self.global_stats['memory_usage_mb'],
                    'total_cache_hits': self.global_stats['total_cache_hits'],
                    'total_cache_misses': self.global_stats['total_cache_misses'],
                    'global_hit_rate': self.global_stats['total_cache_hits'] / max(1, self.global_stats['total_cache_hits'] + self.global_stats['total_cache_misses']),
                    'client_stats': self.client_stats,
                    'oldest_entry': oldest.isoformat() if oldest else None,
                    'newest_entry': newest.isoformat() if newest else None,
                    'last_cache_build': self.global_stats['last_cache_build'].isoformat() if self.global_stats['last_cache_build'] else None
                }
                
        except Exception as e:
            self.logger.warning(f"Cache stats error: {e}")
            return {}
    
    def set_library_cache(self, client_type: str, cache_data: Dict[str, Any], library_key: str = None) -> None:
        """Store library cache data for a client type"""
        try:
            if client_type not in self.registered_clients:
                self.logger.warning(f"Cannot store cache for unregistered client: {client_type}")
                return
            
            client = self.registered_clients[client_type]
            cache_key = client.get_cache_key(library_key)
            ttl_days = client.get_cache_ttl()
            track_count = cache_data.get('total_tracks', 0)
            
            # Store in SQLite
            self._store_in_sqlite(cache_key, client_type, library_key, cache_data, track_count, ttl_days)
            
            # Load into memory cache
            self._load_to_memory_cache(cache_key, cache_data)
            
            self.logger.info(f"Stored library cache for {client_type}: {track_count:,} tracks")
            
        except Exception as e:
            self.logger.error(f"Failed to store library cache for {client_type}: {e}")
            raise

    def clear_all_cache(self, client_type: str = None) -> int:
        """Clear all cache entries, optionally filtered by client type"""
        try:
            with self.db_manager.get_session_context() as session:
                if client_type:
                    cleared_count = session.query(LibraryCache).filter(
                        LibraryCache.client_type == client_type
                    ).delete()
                else:
                    cleared_count = session.query(LibraryCache).delete()
                
                session.commit()
                
                # Clear memory cache too
                self.clear_memory_cache()
                
                if cleared_count > 0:
                    self.logger.info(f"Cleared {cleared_count} library cache entries" + 
                                   (f" for client: {client_type}" if client_type else ""))
                
                return cleared_count
                
        except Exception as e:
            self.logger.warning(f"Cache clear error: {e}")
            return 0
    
    def record_cache_hit(self, client_type: str) -> None:
        """Record a cache hit for a specific client"""
        if client_type not in self.client_stats:
            self.logger.warning(f"Client '{client_type}' not registered, cannot record cache hit")
            return
        
        # Update client-specific stats
        self.client_stats[client_type]['cache_hits'] += 1
        self.client_stats[client_type]['last_used'] = datetime.now()
        
        # Update global stats
        self.global_stats['total_cache_hits'] += 1
        
        # Recalculate hit rate for this client
        total_requests = (self.client_stats[client_type]['cache_hits'] + 
                         self.client_stats[client_type]['cache_misses'])
        self.client_stats[client_type]['hit_rate'] = (
            self.client_stats[client_type]['cache_hits'] / max(1, total_requests)
        )
        
        self.logger.info(f"Cache hit recorded for '{client_type}': {self.client_stats[client_type]['cache_hits']} hits")
    
    def record_cache_miss(self, client_type: str) -> None:
        """Record a cache miss for a specific client"""
        if client_type not in self.client_stats:
            self.logger.warning(f"Client '{client_type}' not registered, cannot record cache miss")
            return
        
        # Update client-specific stats
        self.client_stats[client_type]['cache_misses'] += 1
        self.client_stats[client_type]['last_used'] = datetime.now()
        
        # Update global stats
        self.global_stats['total_cache_misses'] += 1
        
        # Recalculate hit rate for this client
        total_requests = (self.client_stats[client_type]['cache_hits'] + 
                         self.client_stats[client_type]['cache_misses'])
        self.client_stats[client_type]['hit_rate'] = (
            self.client_stats[client_type]['cache_hits'] / max(1, total_requests)
        )
        
        self.logger.info(f"Cache miss recorded for '{client_type}': {self.client_stats[client_type]['cache_misses']} misses")
    
    def get_client_stats(self, client_type: str) -> Dict[str, Any]:
        """Get cache statistics for a specific client"""
        self.logger.debug(f"Getting client stats for '{client_type}', available clients: {list(self.client_stats.keys())}")
        
        if client_type not in self.client_stats:
            self.logger.debug(f"Client '{client_type}' not found in client_stats, returning default stats")
            return {
                'cache_hits': 0,
                'cache_misses': 0,
                'last_used': None,
                'hit_rate': 0.0
            }
        
        # Return a copy of the client stats (already includes hit_rate)
        stats = self.client_stats[client_type].copy()
        self.logger.debug(f"Client '{client_type}' stats: {stats}")
        return stats
    
    def reset_client_stats(self, client_type: str = None) -> None:
        """Reset cache statistics for a specific client or all clients"""
        if client_type:
            if client_type in self.client_stats:
                self.client_stats[client_type] = {
                    'cache_hits': 0,
                    'cache_misses': 0,
                    'last_used': None,
                    'hit_rate': 0.0
                }
                self.logger.info(f"Reset cache stats for client '{client_type}'")
            else:
                self.logger.warning(f"Cannot reset stats for unknown client '{client_type}'")
        else:
            # Reset all client stats
            for client in self.client_stats:
                self.client_stats[client] = {
                    'cache_hits': 0,
                    'cache_misses': 0,
                    'last_used': None,
                    'hit_rate': 0.0
                }
            self.logger.info("Reset cache stats for all clients")


# Global library cache manager instance
_library_cache_manager: Optional[LibraryCacheManager] = None

def get_library_cache_manager(config) -> LibraryCacheManager:
    """Get or create global library cache manager instance"""
    global _library_cache_manager
    if _library_cache_manager is None:
        _library_cache_manager = LibraryCacheManager(config)
    else:
        pass  # Using existing instance
    return _library_cache_manager

def reset_library_cache_manager():
    """Reset the global library cache manager instance (for testing)"""
    global _library_cache_manager
    _library_cache_manager = None