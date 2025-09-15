#!/usr/bin/env python3
"""
SQLAlchemy-based caching for API responses with configurable TTL
"""

import json
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from utils.logger import get_logger
from database.database import get_database_manager
from database.models import CacheEntry, FailedLookup


class CacheManager:
    """SQLAlchemy-based cache manager for API responses"""
    
    def __init__(self):
        self.logger = get_logger('cmdarr.cache')
        self.db_manager = get_database_manager()
    
    def get(self, cache_key: str, source: str) -> Optional[Dict[str, Any]]:
        """Retrieve cached data if it exists and hasn't expired"""
        try:
            with self.db_manager.get_session_context() as session:
                cache_entry = session.query(CacheEntry).filter(
                    CacheEntry.cache_key == cache_key,
                    CacheEntry.source == source,
                    CacheEntry.expires_at > datetime.utcnow()
                ).first()
                
                if cache_entry:
                    self.logger.debug(f"Cache hit: {source}:{cache_key}")
                    return cache_entry.data
                
                self.logger.debug(f"Cache miss: {source}:{cache_key}")
                return None
                
        except Exception as e:
            self.logger.warning(f"Cache retrieval error for {source}:{cache_key}: {e}")
            return None
    
    def set(self, cache_key: str, source: str, data: Dict[str, Any], ttl_days: int) -> None:
        """Store data in cache with TTL"""
        try:
            expires_at = datetime.utcnow() + timedelta(days=ttl_days)
            
            with self.db_manager.get_session_context() as session:
                # Check if entry exists
                existing = session.query(CacheEntry).filter(
                    CacheEntry.cache_key == cache_key,
                    CacheEntry.source == source
                ).first()
                
                if existing:
                    # Update existing entry
                    existing.data = data
                    existing.expires_at = expires_at
                else:
                    # Create new entry
                    cache_entry = CacheEntry(
                        cache_key=cache_key,
                        source=source,
                        data=data,
                        expires_at=expires_at
                    )
                    session.add(cache_entry)
                
                session.commit()
                self.logger.debug(f"Cached: {source}:{cache_key} (expires: {expires_at.strftime('%Y-%m-%d')})")
                
        except Exception as e:
            self.logger.warning(f"Cache storage error for {source}:{cache_key}: {e}")
    
    def is_failed_lookup(self, cache_key: str, source: str) -> bool:
        """Check if this lookup is known to fail recently"""
        try:
            with self.db_manager.get_session_context() as session:
                failed_entry = session.query(FailedLookup).filter(
                    FailedLookup.cache_key == cache_key,
                    FailedLookup.source == source,
                    FailedLookup.expires_at > datetime.utcnow()
                ).first()
                
                return failed_entry is not None
                
        except Exception as e:
            self.logger.warning(f"Failed lookup check error for {source}:{cache_key}: {e}")
            return False
    
    def mark_failed_lookup(self, cache_key: str, source: str, error_reason: str, ttl_days: int) -> None:
        """Mark a lookup as failed to avoid repeated attempts"""
        try:
            expires_at = datetime.utcnow() + timedelta(days=ttl_days)
            
            with self.db_manager.get_session_context() as session:
                # Check if entry exists
                existing = session.query(FailedLookup).filter(
                    FailedLookup.cache_key == cache_key,
                    FailedLookup.source == source
                ).first()
                
                if existing:
                    # Update existing entry
                    existing.error_reason = error_reason
                    existing.expires_at = expires_at
                else:
                    # Create new entry
                    failed_entry = FailedLookup(
                        cache_key=cache_key,
                        source=source,
                        error_reason=error_reason,
                        expires_at=expires_at
                    )
                    session.add(failed_entry)
                
                session.commit()
                self.logger.debug(f"Marked failed: {source}:{cache_key} ({error_reason})")
                
        except Exception as e:
            self.logger.warning(f"Failed lookup marking error for {source}:{cache_key}: {e}")
    
    def cleanup_expired(self) -> int:
        """Remove expired cache entries and return count of removed items"""
        try:
            with self.db_manager.get_session_context() as session:
                # Remove expired cache entries
                expired_cache = session.query(CacheEntry).filter(
                    CacheEntry.expires_at <= datetime.utcnow()
                ).delete()
                
                # Remove expired failed lookups
                expired_failures = session.query(FailedLookup).filter(
                    FailedLookup.expires_at <= datetime.utcnow()
                ).delete()
                
                session.commit()
                
                total_expired = expired_cache + expired_failures
                if total_expired > 0:
                    self.logger.debug(f"Cleaned up {total_expired} expired cache entries")
                
                return total_expired
                
        except Exception as e:
            self.logger.warning(f"Cache cleanup error: {e}")
            return 0
    
    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics"""
        try:
            with self.db_manager.get_session_context() as session:
                # Count by source
                cache_counts = {}
                for source, count in session.query(CacheEntry.source, session.func.count(CacheEntry.id)).filter(
                    CacheEntry.expires_at > datetime.utcnow()
                ).group_by(CacheEntry.source).all():
                    cache_counts[source] = count
                
                # Count failed lookups
                failed_count = session.query(FailedLookup).filter(
                    FailedLookup.expires_at > datetime.utcnow()
                ).count()
                
                # Get oldest and newest entries
                oldest = session.query(session.func.min(CacheEntry.created_at)).scalar()
                newest = session.query(session.func.max(CacheEntry.created_at)).scalar()
                
                return {
                    'cache_counts_by_source': cache_counts,
                    'failed_lookups_count': failed_count,
                    'oldest_entry': oldest.isoformat() if oldest else None,
                    'newest_entry': newest.isoformat() if newest else None,
                    'cache_file_size': 0  # Not applicable for SQLAlchemy
                }
                
        except Exception as e:
            self.logger.warning(f"Cache stats error: {e}")
            return {}
    
    def clear_cache(self, source: Optional[str] = None) -> int:
        """Clear cache entries, optionally filtered by source"""
        try:
            with self.db_manager.get_session_context() as session:
                if source:
                    cleared_cache = session.query(CacheEntry).filter(
                        CacheEntry.source == source
                    ).delete()
                    cleared_failures = session.query(FailedLookup).filter(
                        FailedLookup.source == source
                    ).delete()
                else:
                    cleared_cache = session.query(CacheEntry).delete()
                    cleared_failures = session.query(FailedLookup).delete()
                
                session.commit()
                cleared_count = cleared_cache + cleared_failures
                
                if cleared_count > 0:
                    self.logger.info(f"Cleared {cleared_count} cache entries" + 
                                   (f" for source: {source}" if source else ""))
                
                return cleared_count
                
        except Exception as e:
            self.logger.warning(f"Cache clear error: {e}")
            return 0


# Global cache instance
_cache_manager: Optional[CacheManager] = None

def get_cache_manager() -> CacheManager:
    """Get or create global cache manager instance"""
    global _cache_manager
    if _cache_manager is None:
        _cache_manager = CacheManager()
    return _cache_manager