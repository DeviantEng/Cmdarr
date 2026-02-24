#!/usr/bin/env python3
"""
SQLAlchemy models for Cmdarr configuration database
"""

from sqlalchemy import Column, Integer, String, Boolean, Text, DateTime, JSON, Float, UniqueConstraint
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.sql import func
from datetime import datetime
from typing import Optional, Dict, Any
import json

# Separate base for config database
ConfigBase = declarative_base()


class ConfigSetting(ConfigBase):
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
    is_hidden = Column(Boolean, default=False)  # Hide from UI (auto-managed settings)
    validation_regex = Column(String(500), nullable=True)  # Optional regex validation
    min_value = Column(Float, nullable=True)  # For numeric validation
    max_value = Column(Float, nullable=True)  # For numeric validation
    options = Column(Text, nullable=True)  # JSON string for dropdown options
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    def get_effective_value(self) -> Any:
        """
        Get the effective value (environment variable takes precedence over database value)
        """
        import os
        env_value = os.getenv(self.key)
        if env_value is not None:
            return self._convert_value(env_value)
        
        if self.value is not None:
            return self._convert_value(self.value)
        
        return self._convert_value(self.default_value)
    
    def _convert_value(self, value: str) -> Any:
        """Convert string value to appropriate type"""
        if self.data_type == 'int':
            return int(value)
        elif self.data_type == 'bool':
            return value.lower() in ('true', '1', 'yes', 'on')
        elif self.data_type == 'float':
            return float(value)
        elif self.data_type == 'json':
            return json.loads(value)
        else:  # string
            return value


class CommandConfig(ConfigBase):
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
    command_type = Column(String(50), nullable=True, index=True)  # 'discovery', 'playlist_sync'
    last_run = Column(DateTime(timezone=True), nullable=True)
    last_success = Column(Boolean, nullable=True)
    last_duration = Column(Float, nullable=True)  # Duration in seconds
    last_error = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class CommandExecution(ConfigBase):
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
        return self.status == 'running'


class SystemStatus(ConfigBase):
    """System status and health information"""
    
    __tablename__ = 'system_status'
    
    id = Column(Integer, primary_key=True, index=True)
    status_key = Column(String(100), unique=True, nullable=False, index=True)
    status_value = Column(JSON, nullable=False)
    last_updated = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    description = Column(Text, nullable=True)


class NewReleasePending(ConfigBase):
    """Releases to add - discovered from Spotify, missing from MusicBrainz"""
    
    __tablename__ = 'new_release_pending'
    
    id = Column(Integer, primary_key=True, index=True)
    artist_mbid = Column(String(100), nullable=False, index=True)
    artist_name = Column(String(500), nullable=False)
    spotify_artist_id = Column(String(100), nullable=True)
    album_title = Column(String(500), nullable=False)
    album_type = Column(String(50), nullable=True)
    release_date = Column(String(50), nullable=True)
    total_tracks = Column(Integer, nullable=True)
    spotify_url = Column(String(500), nullable=True)
    harmony_url = Column(String(500), nullable=True)
    lidarr_artist_id = Column(Integer, nullable=True)
    lidarr_artist_url = Column(String(500), nullable=True)
    added_at = Column(DateTime(timezone=True), server_default=func.now())
    source = Column(String(50), nullable=False, default='scheduled')  # scheduled, manual
    status = Column(String(50), nullable=False, default='pending', index=True)  # pending, recheck_requested, resolved, dismissed
    resolved_at = Column(DateTime(timezone=True), nullable=True)
    resolved_reason = Column(String(100), nullable=True)  # in_mb, manual_dismiss, etc.


class ArtistScanLog(ConfigBase):
    """Tracks when each artist was last scanned for new releases"""
    
    __tablename__ = 'artist_scan_log'
    
    id = Column(Integer, primary_key=True, index=True)
    artist_mbid = Column(String(100), nullable=False, unique=True, index=True)
    last_scanned_at = Column(DateTime(timezone=True), nullable=False)
    had_pending_releases = Column(Boolean, nullable=False, default=False)


class LidarrArtist(ConfigBase):
    """Synced Lidarr artist list for autocomplete (periodic sync)"""
    
    __tablename__ = 'lidarr_artist'
    
    id = Column(Integer, primary_key=True, index=True)
    artist_mbid = Column(String(100), nullable=False, unique=True, index=True)
    artist_name = Column(String(500), nullable=False, index=True)
    lidarr_id = Column(Integer, nullable=True)
    spotify_artist_id = Column(String(100), nullable=True)
    last_synced_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class DismissedArtistAlbum(ConfigBase):
    """Artist+album combinations user has dismissed - never re-add on scan"""
    
    __tablename__ = 'dismissed_artist_album'
    
    id = Column(Integer, primary_key=True, index=True)
    artist_mbid = Column(String(100), nullable=False, index=True)
    artist_name = Column(String(500), nullable=True)
    album_title = Column(String(500), nullable=False)
    release_date = Column(String(50), nullable=True)
    dismissed_at = Column(DateTime(timezone=True), server_default=func.now())
    __table_args__ = (UniqueConstraint('artist_mbid', 'album_title', 'release_date', name='uq_dismissed_artist_album'),)
