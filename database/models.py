#!/usr/bin/env python3
"""
SQLAlchemy models for Cmdarr configuration and data management
"""

from sqlalchemy import Column, Integer, String, Boolean, Text, DateTime, JSON, Float
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.sql import func
from datetime import datetime
from typing import Optional, Dict, Any

Base = declarative_base()


class ConfigSetting(Base):
    """Configuration settings with environment variable priority support"""
    
    __tablename__ = 'config_settings'
    
    id = Column(Integer, primary_key=True, index=True)
    key = Column(String(255), unique=True, nullable=False, index=True)
    value = Column(Text, nullable=True)  # NULL means use default
    default_value = Column(Text, nullable=False)
    data_type = Column(String(50), nullable=False)  # 'string', 'int', 'bool', 'float', 'json'
    category = Column(String(100), nullable=False, index=True)  # 'lidarr', 'lastfm', 'cache', etc.
    description = Column(Text, nullable=True)
    is_sensitive = Column(Boolean, default=False)  # For API keys, tokens, etc.
    is_required = Column(Boolean, default=False)
    validation_regex = Column(String(500), nullable=True)  # Optional regex validation
    min_value = Column(Float, nullable=True)  # For numeric validation
    max_value = Column(Float, nullable=True)  # For numeric validation
    options = Column(Text, nullable=True)  # JSON string for dropdown options
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    def get_effective_value(self) -> Any:
        """Get the effective value (environment variable > database > default)"""
        import os
        
        # Check environment variable first
        env_key = self.key.upper()
        if env_value := os.getenv(env_key):
            return self._convert_value(env_value)
        
        # Return database value or default
        return self._convert_value(self.value or self.default_value)
    
    def _convert_value(self, value: str) -> Any:
        """Convert string value to appropriate type"""
        if value is None:
            return None
            
        if self.data_type == 'bool':
            return value.lower() in ('true', '1', 'yes', 'on')
        elif self.data_type == 'int':
            return int(value)
        elif self.data_type == 'float':
            return float(value)
        elif self.data_type == 'json':
            import json
            return json.loads(value)
        else:  # string
            return value


class CommandConfig(Base):
    """Command configuration and scheduling"""
    
    __tablename__ = 'command_configs'
    
    id = Column(Integer, primary_key=True, index=True)
    command_name = Column(String(100), unique=True, nullable=False, index=True)
    display_name = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)
    enabled = Column(Boolean, default=False, nullable=False)
    schedule_hours = Column(Integer, nullable=True)  # NULL means manual only
    timeout_minutes = Column(Integer, nullable=True)  # Timeout in minutes (NULL = no timeout)
    config_json = Column(JSON, nullable=True)  # Command-specific settings
    last_run = Column(DateTime(timezone=True), nullable=True)
    last_success = Column(Boolean, nullable=True)
    last_duration = Column(Float, nullable=True)  # Duration in seconds
    last_error = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class CommandExecution(Base):
    """Command execution history and statistics"""
    
    __tablename__ = 'command_executions'
    
    id = Column(Integer, primary_key=True, index=True)
    command_name = Column(String(100), nullable=False, index=True)
    started_at = Column(DateTime(timezone=True), nullable=False, index=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    success = Column(Boolean, nullable=True)
    status = Column(String(20), nullable=False, default='running')  # 'running', 'completed', 'failed', 'cancelled'
    duration = Column(Float, nullable=True)  # Duration in seconds
    error_message = Column(Text, nullable=True)
    result_data = Column(JSON, nullable=True)  # Command-specific result data
    output_summary = Column(Text, nullable=True)  # Human-readable command output summary
    triggered_by = Column(String(50), nullable=False, default='scheduler')  # 'scheduler', 'manual', 'api'
    
    @property
    def is_running(self) -> bool:
        """Check if command is currently running"""
        return self.status == 'running'


class SystemStatus(Base):
    """System status and health information"""
    
    __tablename__ = 'system_status'
    
    id = Column(Integer, primary_key=True, index=True)
    status_key = Column(String(100), unique=True, nullable=False, index=True)
    status_value = Column(JSON, nullable=False)
    last_updated = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    description = Column(Text, nullable=True)


class CacheEntry(Base):
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


class FailedLookup(Base):
    """Failed API lookups to avoid retrying too frequently"""
    
    __tablename__ = 'failed_lookups'
    
    id = Column(Integer, primary_key=True, index=True)
    cache_key = Column(String(500), unique=True, nullable=False, index=True)
    source = Column(String(100), nullable=False, index=True)
    error_reason = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    expires_at = Column(DateTime(timezone=True), nullable=False, index=True)
    
    @property
    def is_expired(self) -> bool:
        """Check if failed lookup entry is expired"""
        return datetime.utcnow() > self.expires_at


class LibraryCache(Base):
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
