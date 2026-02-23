#!/usr/bin/env python3
"""
Configuration service with environment variable priority
Handles: Environment Variables > Database > Defaults
"""

import os
import json
from typing import Any, Dict, List, Optional, Union
from sqlalchemy.orm import Session
from database.config_models import ConfigSetting
from database.database import get_database_manager
from utils.logger import get_logger


class ConfigService:
    """Centralized configuration management with priority system"""
    
    def __init__(self):
        self._logger = None
        self._cache = {}  # Simple in-memory cache
        self._cache_ttl = 300  # 5 minutes
        self._last_cache_update = 0
        
        # Initialize default configuration
        self._initialize_defaults()
    
    @property
    def logger(self):
        """Lazy logger initialization"""
        if self._logger is None:
            try:
                self._logger = get_logger('cmdarr.config_service')
            except RuntimeError:
                # Logging not configured yet, create a dummy logger
                import logging
                self._logger = logging.getLogger('cmdarr.config_service')
        return self._logger
    
    def _initialize_defaults(self):
        """Initialize default configuration settings"""
        defaults = [
            # Logging Configuration
            {'key': 'LOG_LEVEL', 'default_value': 'INFO', 'data_type': 'dropdown', 'category': 'logging', 'description': 'Logging level', 'options': ['DEBUG', 'INFO', 'WARNING', 'ERROR']},
            {'key': 'LOG_FILE', 'default_value': 'data/logs/cmdarr.log', 'data_type': 'string', 'category': 'logging', 'description': 'Log file location'},
            {'key': 'LOG_RETENTION_DAYS', 'default_value': '7', 'data_type': 'int', 'category': 'logging', 'description': 'Number of daily log files to keep'},
            
            # Lidarr Configuration
            {'key': 'LIDARR_URL', 'default_value': 'http://localhost:8686', 'data_type': 'string', 'category': 'lidarr', 'description': 'Lidarr instance URL'},
            {'key': 'LIDARR_API_KEY', 'default_value': '', 'data_type': 'string', 'category': 'lidarr', 'description': 'Lidarr API key', 'is_sensitive': True},
            {'key': 'LIDARR_TIMEOUT', 'default_value': '30', 'data_type': 'int', 'category': 'lidarr', 'description': 'Request timeout in seconds'},
            {'key': 'LIDARR_IGNORE_TLS', 'default_value': 'false', 'data_type': 'bool', 'category': 'lidarr', 'description': 'Ignore TLS certificate verification'},
            
            # Last.fm Configuration
            {'key': 'LASTFM_API_KEY', 'default_value': '', 'data_type': 'string', 'category': 'lastfm', 'description': 'Last.fm API key', 'is_sensitive': True},
            {'key': 'LASTFM_API_SECRET', 'default_value': '', 'data_type': 'string', 'category': 'lastfm', 'description': 'Last.fm API secret', 'is_sensitive': True},
            {'key': 'LASTFM_RATE_LIMIT', 'default_value': '8.0', 'data_type': 'float', 'category': 'lastfm', 'description': 'Rate limit in requests per second'},
            
            # ListenBrainz Configuration
            {'key': 'LISTENBRAINZ_TOKEN', 'default_value': '', 'data_type': 'string', 'category': 'listenbrainz', 'description': 'ListenBrainz user token', 'is_sensitive': True},
            {'key': 'LISTENBRAINZ_USERNAME', 'default_value': '', 'data_type': 'string', 'category': 'listenbrainz', 'description': 'ListenBrainz username'},
            {'key': 'LISTENBRAINZ_RATE_LIMIT', 'default_value': '5.0', 'data_type': 'float', 'category': 'listenbrainz', 'description': 'Rate limit in requests per second'},
            
            # MusicBrainz Configuration
            {'key': 'MUSICBRAINZ_ENABLED', 'default_value': 'true', 'data_type': 'bool', 'category': 'musicbrainz', 'description': 'Enable MusicBrainz fuzzy matching'},
            {'key': 'MUSICBRAINZ_RATE_LIMIT', 'default_value': '1.0', 'data_type': 'float', 'category': 'musicbrainz', 'description': 'Rate limit in requests per second'},
            {'key': 'MUSICBRAINZ_MAX_RETRIES', 'default_value': '3', 'data_type': 'int', 'category': 'musicbrainz', 'description': 'Maximum retry attempts for rate limit errors'},
            {'key': 'MUSICBRAINZ_RETRY_DELAY', 'default_value': '2.0', 'data_type': 'float', 'category': 'musicbrainz', 'description': 'Initial retry delay in seconds (exponential backoff)'},
            {'key': 'MUSICBRAINZ_MIN_SIMILARITY', 'default_value': '0.85', 'data_type': 'float', 'category': 'musicbrainz', 'description': 'Minimum similarity score for fuzzy matching'},
            {'key': 'MUSICBRAINZ_USER_AGENT', 'default_value': 'Cmdarr', 'data_type': 'string', 'category': 'musicbrainz', 'description': 'User agent identifier'},
            {'key': 'MUSICBRAINZ_CONTACT', 'default_value': 'your-email@example.com', 'data_type': 'string', 'category': 'musicbrainz', 'description': 'Contact email (required by MusicBrainz API)'},
            
            # Plex Configuration
            {'key': 'PLEX_CLIENT_ENABLED', 'default_value': 'false', 'data_type': 'bool', 'category': 'plex', 'description': 'Enable Plex client functionality'},
            {'key': 'PLEX_URL', 'default_value': 'http://localhost:32400', 'data_type': 'string', 'category': 'plex', 'description': 'Plex Media Server URL'},
            {'key': 'PLEX_TOKEN', 'default_value': '', 'data_type': 'string', 'category': 'plex', 'description': 'Plex authentication token', 'is_sensitive': True},
            {'key': 'PLEX_TIMEOUT', 'default_value': '30', 'data_type': 'int', 'category': 'plex', 'description': 'Request timeout in seconds'},
            {'key': 'PLEX_IGNORE_TLS', 'default_value': 'false', 'data_type': 'bool', 'category': 'plex', 'description': 'Ignore TLS certificate verification'},
            
            # Jellyfin Configuration
            {'key': 'JELLYFIN_CLIENT_ENABLED', 'default_value': 'false', 'data_type': 'bool', 'category': 'jellyfin', 'description': 'Enable Jellyfin client functionality'},
            {'key': 'JELLYFIN_URL', 'default_value': 'http://localhost:8096', 'data_type': 'string', 'category': 'jellyfin', 'description': 'Jellyfin Media Server URL'},
            {'key': 'JELLYFIN_TOKEN', 'default_value': '', 'data_type': 'string', 'category': 'jellyfin', 'description': 'Jellyfin authentication token', 'is_sensitive': True},
            {'key': 'JELLYFIN_USER_ID', 'default_value': '', 'data_type': 'string', 'category': 'jellyfin', 'description': 'Jellyfin user ID'},
            {'key': 'JELLYFIN_TIMEOUT', 'default_value': '30', 'data_type': 'int', 'category': 'jellyfin', 'description': 'Request timeout in seconds'},
            {'key': 'JELLYFIN_IGNORE_TLS', 'default_value': 'false', 'data_type': 'bool', 'category': 'jellyfin', 'description': 'Ignore TLS certificate verification'},
            
            # Spotify Configuration
            {'key': 'SPOTIFY_CLIENT_ID', 'default_value': '', 'data_type': 'string', 'category': 'spotify', 'description': 'Spotify API Client ID', 'is_sensitive': True},
            {'key': 'SPOTIFY_CLIENT_SECRET', 'default_value': '', 'data_type': 'string', 'category': 'spotify', 'description': 'Spotify API Client Secret', 'is_sensitive': True},
            {'key': 'NEW_RELEASES_CACHE_DAYS', 'default_value': '14', 'data_type': 'int', 'category': 'spotify', 'description': 'Cache TTL in days for New Releases data (Lidarr, Spotify, MusicBrainz)'},
            
            # Web Server Configuration
            {'key': 'WEB_PORT', 'default_value': '8080', 'data_type': 'int', 'category': 'web_server', 'description': 'Web server port'},
            {'key': 'WEB_HOST', 'default_value': '0.0.0.0', 'data_type': 'string', 'category': 'web_server', 'description': 'Web server host'},
            
            # Command Configuration
            {'key': 'COMMAND_CLEANUP_RETENTION', 'default_value': '50', 'data_type': 'int', 'category': 'commands', 'description': 'Number of command executions to keep per command'},
            {'key': 'MAX_PARALLEL_COMMANDS', 'default_value': '3', 'data_type': 'int', 'category': 'commands', 'description': 'Maximum number of commands that can run in parallel', 'min_value': 1, 'max_value': 10},
            
            
            # Cache Configuration
            {'key': 'CACHE_FILE', 'default_value': 'data/cmdarr.db', 'data_type': 'string', 'category': 'cache', 'description': 'Cache database file location'},
            {'key': 'CACHE_LASTFM_TTL_DAYS', 'default_value': '7', 'data_type': 'int', 'category': 'cache', 'description': 'Cache TTL for Last.fm API responses (days)'},
            {'key': 'CACHE_MUSICBRAINZ_TTL_DAYS', 'default_value': '7', 'data_type': 'int', 'category': 'cache', 'description': 'Cache TTL for MusicBrainz API responses (days)'},
            {'key': 'CACHE_LISTENBRAINZ_TTL_DAYS', 'default_value': '3', 'data_type': 'int', 'category': 'cache', 'description': 'Cache TTL for ListenBrainz API responses (days)'},
            {'key': 'CACHE_PLEX_TTL_DAYS', 'default_value': '1', 'data_type': 'int', 'category': 'cache', 'description': 'Cache TTL for Plex API responses (days)'},
            {'key': 'CACHE_JELLYFIN_TTL_DAYS', 'default_value': '1', 'data_type': 'int', 'category': 'cache', 'description': 'Cache TTL for Jellyfin API responses (days)'},
            {'key': 'CACHE_FAILED_LOOKUP_TTL_DAYS', 'default_value': '1', 'data_type': 'int', 'category': 'cache', 'description': 'Cache TTL for failed API lookups (days)'},
            
            # Library Cache Configuration
            {'key': 'LIBRARY_CACHE_TTL_DAYS', 'default_value': '30', 'data_type': 'int', 'category': 'cache', 'description': 'Library cache duration (days)'},
            {'key': 'LIBRARY_CACHE_MEMORY_LIMIT_MB', 'default_value': '512', 'data_type': 'int', 'category': 'cache', 'description': 'Maximum memory usage during playlist operations (MB)'},
            {'key': 'LIBRARY_CACHE_SCHEDULE_HOURS', 'default_value': '24', 'data_type': 'int', 'category': 'cache', 'description': 'Library cache building schedule (hours)'},
            
            # Library Cache Target Configuration (default disabled)
            {'key': 'LIBRARY_CACHE_PLEX_ENABLED', 'default_value': 'true', 'data_type': 'bool', 'category': 'plex', 'description': 'Enable library cache building for Plex (auto-managed)', 'is_hidden': True},
            {'key': 'LIBRARY_CACHE_PLEX_TTL_DAYS', 'default_value': '30', 'data_type': 'int', 'category': 'plex', 'description': 'Plex library cache TTL (days)'},
            {'key': 'LIBRARY_CACHE_PLEX_USER_DISABLED', 'default_value': 'false', 'data_type': 'bool', 'category': 'plex', 'description': 'Disable library caching (slower playlist sync)'},
            {'key': 'LIBRARY_CACHE_JELLYFIN_ENABLED', 'default_value': 'true', 'data_type': 'bool', 'category': 'jellyfin', 'description': 'Enable library cache building for Jellyfin (auto-managed)', 'is_hidden': True},
            {'key': 'LIBRARY_CACHE_JELLYFIN_TTL_DAYS', 'default_value': '30', 'data_type': 'int', 'category': 'jellyfin', 'description': 'Jellyfin library cache TTL (days)'},
            {'key': 'LIBRARY_CACHE_JELLYFIN_USER_DISABLED', 'default_value': 'false', 'data_type': 'bool', 'category': 'jellyfin', 'description': 'Disable library caching (slower playlist sync)'},
            
            # Playlist Sync Configuration
            # Note: Target configuration is handled at the command level
            {'key': 'PLAYLIST_SYNC_DISCOVERY_AGE_THRESHOLD_DAYS', 'default_value': '30', 'data_type': 'int', 'category': 'playlist_sync', 'description': 'Age threshold in days for removing stale discovery entries'},
            
            # Output Configuration
            {'key': 'OUTPUT_FILE', 'default_value': 'data/import_lists/discovery_lastfm.json', 'data_type': 'string', 'category': 'output', 'description': 'Output file for Last.fm Lidarr import list'},
            {'key': 'LISTENBRAINZ_OUTPUT_FILE', 'default_value': 'data/import_lists/discovery_listenbrainz.json', 'data_type': 'string', 'category': 'output', 'description': 'Output file for ListenBrainz Lidarr import list'},
            {'key': 'PRETTY_PRINT_JSON', 'default_value': 'true', 'data_type': 'bool', 'category': 'output', 'description': 'Pretty print JSON output'},
        ]
        
        # Initialize database with defaults
        self._initialize_database_defaults(defaults)
    
    def _initialize_database_defaults(self, defaults: List[Dict[str, Any]]):
        """Initialize database with default configuration settings"""
        try:
            manager = get_database_manager()
            session = manager.get_session_sync()
            try:
                for default in defaults:
                    # Check if setting already exists
                    existing = session.query(ConfigSetting).filter(ConfigSetting.key == default['key']).first()
                    if not existing:
                        # Convert options list to JSON string if present
                        setting_data = default.copy()
                        if 'options' in setting_data and setting_data['options']:
                            import json
                            setting_data['options'] = json.dumps(setting_data['options'])
                        
                        setting = ConfigSetting(**setting_data)
                        session.add(setting)
                
                session.commit()
                self.logger.info(f"Initialized {len(defaults)} default configuration settings")
            finally:
                session.close()
        except Exception as e:
            self.logger.error(f"Failed to initialize default configuration: {e}")
            raise
    
    def get(self, key: str, default: Any = None) -> Any:
        """Get configuration value with priority: Environment > Database > Default"""
        # Check cache first
        if self._is_cache_valid():
            if key in self._cache:
                return self._cache[key]
        
        # Check environment variable first
        env_key = key.upper()
        if env_value := os.getenv(env_key):
            value = self._convert_value(env_value, self._get_data_type(key))
            self._cache[key] = value
            return value
        
        # Check database
        try:
            manager = get_database_manager()
            session = manager.get_session_sync()
            try:
                setting = session.query(ConfigSetting).filter(ConfigSetting.key == key).first()
                if setting:
                    value = setting.get_effective_value()
                    self._cache[key] = value
                    return value
            finally:
                session.close()
        except Exception as e:
            self.logger.warning(f"Failed to get setting from database: {e}")
        
        # Return default or provided default
        return default
    
    def set(self, key: str, value: Any, data_type: str = None) -> bool:
        """Set configuration value in database"""
        try:
            manager = get_database_manager()
            session = manager.get_session_sync()
            try:
                setting = session.query(ConfigSetting).filter(ConfigSetting.key == key).first()
                if setting:
                    setting.value = str(value)
                    if data_type:
                        setting.data_type = data_type
                else:
                    # Create new setting
                    setting = ConfigSetting(
                        key=key,
                        value=str(value),
                        default_value=str(value),
                        data_type=data_type or 'string',
                        category='custom',
                        description='User-defined setting'
                    )
                    session.add(setting)
                
                session.commit()
                
                # Clear cache
                self._clear_cache()
                return True
            finally:
                session.close()
        except Exception as e:
            self.logger.error(f"Failed to set configuration {key}: {e}")
            return False
    
    def get_all_by_category(self, category: str) -> Dict[str, Any]:
        """Get all configuration settings for a category"""
        try:
            manager = get_database_manager()
            session = manager.get_session_sync()
            try:
                settings = session.query(ConfigSetting).filter(ConfigSetting.category == category).all()
                return {setting.key: setting.get_effective_value() for setting in settings}
            finally:
                session.close()
        except Exception as e:
            self.logger.error(f"Failed to get settings for category {category}: {e}")
            return {}
    
    def get_visible_settings(self) -> Dict[str, Any]:
        """Get all visible (non-hidden) configuration settings"""
        try:
            manager = get_database_manager()
            session = manager.get_session_sync()
            try:
                settings = session.query(ConfigSetting).filter(ConfigSetting.is_hidden == False).all()
                result = {}
                for setting in settings:
                    result[setting.key] = setting.get_effective_value()
                return result
            finally:
                session.close()
        except Exception as e:
            self.logger.error(f"Failed to get visible settings: {e}")
            return {}
    
    def get_visible_settings_by_category(self, category: str) -> Dict[str, Any]:
        """Get visible settings by category"""
        try:
            manager = get_database_manager()
            session = manager.get_session_sync()
            try:
                settings = session.query(ConfigSetting).filter(
                    ConfigSetting.category == category,
                    ConfigSetting.is_hidden == False
                ).all()
                result = {}
                for setting in settings:
                    result[setting.key] = setting.get_effective_value()
                return result
            finally:
                session.close()
        except Exception as e:
            self.logger.error(f"Failed to get visible settings for category {category}: {e}")
            return {}

    def get_all_settings(self) -> Dict[str, Any]:
        """Get all configuration settings"""
        try:
            manager = get_database_manager()
            session = manager.get_session_sync()
            try:
                settings = session.query(ConfigSetting).all()
                return {setting.key: setting.get_effective_value() for setting in settings}
            finally:
                session.close()
        except Exception as e:
            self.logger.error(f"Failed to get all settings: {e}")
            return {}
    
    def get_int(self, key: str, default: int = 0) -> int:
        """Get a configuration value as integer"""
        try:
            value = self.get(key)
            if value is None:
                return default
            return int(value)
        except (ValueError, TypeError):
            self.logger.warning(f"Failed to convert {key} to int, using default: {default}")
            return default
    
    def validate_required_settings(self) -> List[str]:
        """Validate that all required settings are configured"""
        missing = []
        try:
            manager = get_database_manager()
            session = manager.get_session_sync()
            try:
                required_settings = session.query(ConfigSetting).filter(ConfigSetting.is_required == True).all()
                for setting in required_settings:
                    value = setting.get_effective_value()
                    if not value or value == '':
                        missing.append(setting.key)
            finally:
                session.close()
        except Exception as e:
            self.logger.error(f"Failed to validate required settings: {e}")
        
        return missing
    
    def validate_client_dependencies(self) -> List[str]:
        """Validate that client-dependent settings are properly configured"""
        warnings = []
        
        # Check Plex library cache dependency
        plex_client_enabled = self.get('PLEX_CLIENT_ENABLED', False)
        plex_cache_enabled = self.get('LIBRARY_CACHE_PLEX_ENABLED', False)
        
        if plex_cache_enabled and not plex_client_enabled:
            warnings.append("LIBRARY_CACHE_PLEX_ENABLED is enabled but PLEX_CLIENT_ENABLED is disabled")
        
        # Check Jellyfin library cache dependency
        jellyfin_client_enabled = self.get('JELLYFIN_CLIENT_ENABLED', False)
        jellyfin_cache_enabled = self.get('LIBRARY_CACHE_JELLYFIN_ENABLED', False)
        
        if jellyfin_cache_enabled and not jellyfin_client_enabled:
            warnings.append("LIBRARY_CACHE_JELLYFIN_ENABLED is enabled but JELLYFIN_CLIENT_ENABLED is disabled")
        
        return warnings
    
    def _get_data_type(self, key: str) -> str:
        """Get data type for a configuration key"""
        try:
            manager = get_database_manager()
            session = manager.get_session_sync()
            try:
                setting = session.query(ConfigSetting).filter(ConfigSetting.key == key).first()
                return setting.data_type if setting else 'string'
            finally:
                session.close()
        except:
            return 'string'
    
    def _convert_value(self, value: str, data_type: str) -> Any:
        """Convert string value to appropriate type"""
        if value is None:
            return None
            
        if data_type == 'bool':
            return value.lower() in ('true', '1', 'yes', 'on')
        elif data_type == 'int':
            return int(value)
        elif data_type == 'float':
            return float(value)
        elif data_type == 'json':
            return json.loads(value)
        else:  # string
            return value
    
    def _is_cache_valid(self) -> bool:
        """Check if cache is still valid"""
        import time
        return time.time() - self._last_cache_update < self._cache_ttl
    
    def _clear_cache(self):
        """Clear configuration cache"""
        self._cache.clear()
        import time
        self._last_cache_update = time.time()
    
    def refresh_cache(self):
        """Force refresh of configuration cache"""
        self._clear_cache()


# Global configuration service instance
config_service = ConfigService()
