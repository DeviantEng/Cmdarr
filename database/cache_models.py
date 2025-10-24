#!/usr/bin/env python3
"""
SQLAlchemy models for Cmdarr cache database
"""

from sqlalchemy import Column, Integer, String, DateTime, JSON
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.sql import func
from datetime import datetime

# Separate base for cache database
CacheBase = declarative_base()


class CacheEntry(CacheBase):
    """API response cache entries"""
    
    __tablename__ = 'api_cache'
    
    id = Column(Integer, primary_key=True, index=True)
    cache_key = Column(String(500), unique=True, nullable=False, index=True)
    source = Column(String(100), nullable=False, index=True)  # 'lastfm', 'musicbrainz', etc.
    data = Column(JSON, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    expires_at = Column(DateTime(timezone=True), nullable=False, index=True)
    
    @property
    def is_expired(self) -> bool:
        """Check if cache entry is expired"""
        return datetime.utcnow() > self.expires_at


class FailedLookup(CacheBase):
    """Failed API lookups to avoid retrying too frequently"""
    
    __tablename__ = 'failed_lookups'
    
    id = Column(Integer, primary_key=True, index=True)
    cache_key = Column(String(500), unique=True, nullable=False, index=True)
    source = Column(String(100), nullable=False, index=True)
    error_reason = Column(String(500), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    expires_at = Column(DateTime(timezone=True), nullable=False, index=True)
    
    @property
    def is_expired(self) -> bool:
        """Check if failed lookup entry is expired"""
        return datetime.utcnow() > self.expires_at


class LibraryCache(CacheBase):
    """Music library cache for performance optimization"""
    
    __tablename__ = 'library_cache'
    
    id = Column(Integer, primary_key=True, index=True)
    cache_key = Column(String(500), unique=True, nullable=False, index=True)
    client_type = Column(String(50), nullable=False, index=True)  # 'plex', 'jellyfin', etc.
    library_key = Column(String(200), nullable=False, index=True)
    schema_version = Column(String(20), nullable=False)
    cache_data = Column(JSON, nullable=False)
    track_count = Column(Integer, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    expires_at = Column(DateTime(timezone=True), nullable=False, index=True)
    
    @property
    def is_expired(self) -> bool:
        """Check if library cache entry is expired"""
        return datetime.utcnow() > self.expires_at
