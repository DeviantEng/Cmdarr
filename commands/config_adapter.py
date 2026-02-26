#!/usr/bin/env python3
"""
Configuration adapter to bridge old Config class with new config service
This allows existing commands to work with the new database-based configuration
"""

from typing import Any
from services.config_service import config_service
from utils.logger import get_logger


class ConfigAdapter:
    """
    Adapter class that provides the old Config interface using the new config service
    This allows existing commands to work without modification
    """
    
    def __init__(self):
        self.logger = get_logger('cmdarr.config_adapter')
        
        # Map old config attributes to new config service
        self._setup_attributes()
    
    def get(self, key: str, default: Any = None) -> Any:
        """Get configuration value using the new config service"""
        return config_service.get(key, default)
    
    def _setup_attributes(self):
        """Setup all the old config attributes using the new config service"""
        
        # Logging Configuration
        self.LOG_LEVEL = config_service.get('LOG_LEVEL', 'INFO')
        self.LOG_FILE = config_service.get('LOG_FILE', 'data/logs/cmdarr.log')
        self.LOG_RETENTION_DAYS = config_service.get('LOG_RETENTION_DAYS', 7)
        self.LOG_ROTATION = config_service.get('LOG_ROTATION', 'daily')
        
        # Lidarr Configuration
        self.LIDARR_URL = config_service.get('LIDARR_URL', 'http://localhost:8686')
        self.LIDARR_API_KEY = config_service.get('LIDARR_API_KEY', '')
        self.LIDARR_TIMEOUT = config_service.get('LIDARR_TIMEOUT', 30)
        self.LIDARR_IGNORE_TLS = config_service.get('LIDARR_IGNORE_TLS', False)
        
        # Last.fm Configuration
        self.LASTFM_API_KEY = config_service.get('LASTFM_API_KEY', '')
        self.LASTFM_API_SECRET = config_service.get('LASTFM_API_SECRET', '')
        self.LASTFM_RATE_LIMIT = config_service.get('LASTFM_RATE_LIMIT', 5.0)
        self.LASTFM_SIMILAR_COUNT = config_service.get('LASTFM_SIMILAR_COUNT', 1)
        self.LASTFM_MIN_MATCH_SCORE = config_service.get('LASTFM_MIN_MATCH_SCORE', 0.0)
        
        # ListenBrainz Configuration
        self.LISTENBRAINZ_TOKEN = config_service.get('LISTENBRAINZ_TOKEN', '')
        self.LISTENBRAINZ_USERNAME = config_service.get('LISTENBRAINZ_USERNAME', '')
        self.LISTENBRAINZ_RATE_LIMIT = config_service.get('LISTENBRAINZ_RATE_LIMIT', 5.0)
        
        # MusicBrainz Configuration
        self.MUSICBRAINZ_ENABLED = config_service.get('MUSICBRAINZ_ENABLED', True)
        self.MUSICBRAINZ_RATE_LIMIT = config_service.get('MUSICBRAINZ_RATE_LIMIT', 0.8)
        self.MUSICBRAINZ_MIN_SIMILARITY = config_service.get('MUSICBRAINZ_MIN_SIMILARITY', 0.85)
        self.MUSICBRAINZ_MAX_RETRIES = config_service.get('MUSICBRAINZ_MAX_RETRIES', 3)
        self.MUSICBRAINZ_RETRY_DELAY = config_service.get('MUSICBRAINZ_RETRY_DELAY', 2.0)
        
        # Plex Configuration
        self.PLEX_URL = config_service.get('PLEX_URL', 'http://localhost:32400')
        self.PLEX_TOKEN = config_service.get('PLEX_TOKEN', '')
        self.PLEX_TIMEOUT = config_service.get('PLEX_TIMEOUT', 30)
        self.PLEX_IGNORE_TLS = config_service.get('PLEX_IGNORE_TLS', False)
        
        # Jellyfin Configuration
        self.JELLYFIN_URL = config_service.get('JELLYFIN_URL', 'http://localhost:8096')
        self.JELLYFIN_TOKEN = config_service.get('JELLYFIN_TOKEN', '')
        self.JELLYFIN_USER_ID = config_service.get('JELLYFIN_USER_ID', '')
        self.JELLYFIN_TIMEOUT = config_service.get('JELLYFIN_TIMEOUT', 30)
        self.JELLYFIN_IGNORE_TLS = config_service.get('JELLYFIN_IGNORE_TLS', False)
        
        # Spotify Configuration
        self.SPOTIFY_CLIENT_ID = config_service.get('SPOTIFY_CLIENT_ID', '')
        self.SPOTIFY_CLIENT_SECRET = config_service.get('SPOTIFY_CLIENT_SECRET', '')
        self.NEW_RELEASES_CACHE_DAYS = config_service.get('NEW_RELEASES_CACHE_DAYS', 14)
        
        # Processing Configuration
        self.GENERATE_DEBUG_VALIDATION_CALLS = config_service.get('GENERATE_DEBUG_VALIDATION_CALLS', True)
        
        # Commands Configuration
        self.DISCOVERY_LASTFM_ENABLED = config_service.get('DISCOVERY_LASTFM_ENABLED', True)
        self.DISCOVERY_LASTFM_SCHEDULE = config_service.get('DISCOVERY_LASTFM_SCHEDULE', 24)
        self.DISCOVERY_LASTFM_LIMIT = config_service.get('DISCOVERY_LASTFM_LIMIT', 5)
        self.DISCOVERY_LISTENBRAINZ_ENABLED = config_service.get('DISCOVERY_LISTENBRAINZ_ENABLED', False)
        self.DISCOVERY_LISTENBRAINZ_SCHEDULE = config_service.get('DISCOVERY_LISTENBRAINZ_SCHEDULE', 24)
        self.DISCOVERY_LISTENBRAINZ_LIMIT = config_service.get('DISCOVERY_LISTENBRAINZ_LIMIT', 5)
        self.LISTENBRAINZ_PLEX_PLAYLIST_ENABLED = config_service.get('LISTENBRAINZ_PLEX_PLAYLIST_ENABLED', False)
        self.LISTENBRAINZ_PLEX_PLAYLIST_SCHEDULE = config_service.get('LISTENBRAINZ_PLEX_PLAYLIST_SCHEDULE', 12)
        
        
        # Web Server Configuration
        self.WEB_PORT = config_service.get('WEB_PORT', 8080)
        self.WEB_HOST = config_service.get('WEB_HOST', '0.0.0.0')
        
        # Output Configuration
        self.OUTPUT_FILE = config_service.get('OUTPUT_FILE', 'data/import_lists/discovery_lastfm.json')
        self.LISTENBRAINZ_OUTPUT_FILE = config_service.get('LISTENBRAINZ_OUTPUT_FILE', 'data/import_lists/discovery_listenbrainz.json')
        self.PRETTY_PRINT_JSON = config_service.get('PRETTY_PRINT_JSON', True)
        
        # Cache Configuration
        self.CACHE_ENABLED = config_service.get('CACHE_ENABLED', True)
        self.CACHE_FILE = config_service.get('CACHE_FILE', 'data/cmdarr.db')
        self.CACHE_LASTFM_TTL_DAYS = config_service.get('CACHE_LASTFM_TTL_DAYS', 7)
        self.CACHE_MUSICBRAINZ_TTL_DAYS = config_service.get('CACHE_MUSICBRAINZ_TTL_DAYS', 7)
        self.CACHE_LISTENBRAINZ_TTL_DAYS = config_service.get('CACHE_LISTENBRAINZ_TTL_DAYS', 3)
        self.CACHE_PLEX_TTL_DAYS = config_service.get('CACHE_PLEX_TTL_DAYS', 1)
        self.CACHE_JELLYFIN_TTL_DAYS = config_service.get('CACHE_JELLYFIN_TTL_DAYS', 1)
        self.CACHE_FAILED_LOOKUP_TTL_DAYS = config_service.get('CACHE_FAILED_LOOKUP_TTL_DAYS', 1)
        
        # Library Cache Configuration
        self.LIBRARY_CACHE_MEMORY_LIMIT_MB = config_service.get('LIBRARY_CACHE_MEMORY_LIMIT_MB', 512)
    
    def get_config_summary(self) -> dict:
        """Get configuration summary for logging (excluding sensitive data)"""
        return {
            'log_level': self.LOG_LEVEL,
            'log_file': self.LOG_FILE,
            'log_retention_days': self.LOG_RETENTION_DAYS,
            'lidarr_url': self.LIDARR_URL,
            'lidarr_timeout': self.LIDARR_TIMEOUT,
            'lidarr_ignore_tls': self.LIDARR_IGNORE_TLS,
            'lastfm_rate_limit': self.LASTFM_RATE_LIMIT,
            'lastfm_similar_count': self.LASTFM_SIMILAR_COUNT,
            'lastfm_min_match_score': self.LASTFM_MIN_MATCH_SCORE,
            'discovery_lastfm_enabled': self.DISCOVERY_LASTFM_ENABLED,
            'discovery_lastfm_schedule': self.DISCOVERY_LASTFM_SCHEDULE,
            'discovery_lastfm_limit': self.DISCOVERY_LASTFM_LIMIT,
            'listenbrainz_username': self.LISTENBRAINZ_USERNAME,
            'listenbrainz_rate_limit': self.LISTENBRAINZ_RATE_LIMIT,
            'discovery_listenbrainz_enabled': self.DISCOVERY_LISTENBRAINZ_ENABLED,
            'discovery_listenbrainz_schedule': self.DISCOVERY_LISTENBRAINZ_SCHEDULE,
            'discovery_listenbrainz_limit': self.DISCOVERY_LISTENBRAINZ_LIMIT,
            'listenbrainz_plex_playlist_enabled': self.LISTENBRAINZ_PLEX_PLAYLIST_ENABLED,
            'plex_url': self.PLEX_URL,
            'plex_timeout': self.PLEX_TIMEOUT,
            'plex_ignore_tls': self.PLEX_IGNORE_TLS,
            'musicbrainz_enabled': self.MUSICBRAINZ_ENABLED,
            'musicbrainz_min_similarity': self.MUSICBRAINZ_MIN_SIMILARITY,
            'generate_debug_calls': self.GENERATE_DEBUG_VALIDATION_CALLS,
            'web_port': self.WEB_PORT,
            'web_host': self.WEB_HOST,
            'output_file': self.OUTPUT_FILE,
            'listenbrainz_output_file': self.LISTENBRAINZ_OUTPUT_FILE,
            'pretty_print_json': self.PRETTY_PRINT_JSON,
            'cache_enabled': self.CACHE_ENABLED,
            'cache_file': self.CACHE_FILE,
            'cache_lastfm_ttl_days': self.CACHE_LASTFM_TTL_DAYS,
            'cache_musicbrainz_ttl_days': self.CACHE_MUSICBRAINZ_TTL_DAYS,
            'cache_listenbrainz_ttl_days': self.CACHE_LISTENBRAINZ_TTL_DAYS,
            'cache_plex_ttl_days': self.CACHE_PLEX_TTL_DAYS,
            'cache_jellyfin_ttl_days': self.CACHE_JELLYFIN_TTL_DAYS,
            'cache_failed_lookup_ttl_days': self.CACHE_FAILED_LOOKUP_TTL_DAYS,
            'library_cache_memory_limit_mb': self.LIBRARY_CACHE_MEMORY_LIMIT_MB
        }
    
    def print_config(self):
        """Print configuration summary"""
        print("=== Configuration Summary ===")
        config_summary = self.get_config_summary()
        for key, value in config_summary.items():
            print(f"{key.upper()}: {value}")
        print("=" * 30)


# Create a global instance for backward compatibility
Config = ConfigAdapter
