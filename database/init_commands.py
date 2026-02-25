#!/usr/bin/env python3
"""
Initialize default command configurations in the database
"""

import os
import sys
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from database.database import get_database_manager
from database.config_models import CommandConfig
import logging

# Setup basic logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('cmdarr.init_commands')


def init_default_commands():
    """Initialize default command configurations"""
    
    # Order matters: ids are assigned by insertion order. Maintenance first (id 1) so it runs
    # before playlist syncs when the scheduler sorts due commands by id.
    default_commands = [
        {
            'command_name': 'playlist_sync_discovery_maintenance',
            'display_name': 'Playlist Sync Discovery Maintenance',
            'description': 'Maintains the unified discovery import list by removing stale entries',
            'enabled': True,
            'timeout_minutes': 30,
            'command_type': 'discovery',
            'config_json': {
                'age_threshold_days': 30
            }
        },
        {
            'command_name': 'discovery_lastfm',
            'display_name': 'Last.fm Discovery',
            'description': 'Discover similar artists from Last.fm and MusicBrainz for Lidarr import',
            'enabled': False,
            'timeout_minutes': 30,
            'command_type': 'discovery',
            'config_json': {
                'artists_to_query': 3,
                'similar_per_artist': 1,
                'artist_cooldown_days': 30,
                'limit': 5,
                'min_match_score': 0.9
            }
        },
        {
            'command_name': 'library_cache_builder',
            'display_name': 'Library Cache Builder',
            'description': 'Builds and maintains library caches for configured music players (helper command)',
            'enabled': False,
            'timeout_minutes': 180,
            'command_type': None,
            'config_json': {
                'plex_enabled': False,
                'jellyfin_enabled': False
            }
        },
        {
            'command_name': 'new_releases_discovery',
            'display_name': 'New Releases Discovery',
            'description': 'Scan Lidarr artists for Spotify releases missing from MusicBrainz',
            'enabled': False,
            'timeout_minutes': 30,
            'command_type': 'discovery',
            'config_json': {
                'artists_per_run': 5,
                'album_types': 'album'
            }
        }
    ]
    
    try:
        manager = get_database_manager()
        session = manager.get_session_sync()
        try:
            for command_data in default_commands:
                # Check if command already exists
                existing = session.query(CommandConfig).filter(
                    CommandConfig.command_name == command_data['command_name']
                ).first()
                
                if not existing:
                    command = CommandConfig(**command_data)
                    session.add(command)
                    logger.info(f"Added command: {command_data['command_name']}")
                else:
                    logger.info(f"Command already exists: {command_data['command_name']}")
            
            session.commit()
            logger.info("Default commands initialized successfully")
        finally:
            session.close()
            
    except Exception as e:
        logger.error(f"Failed to initialize default commands: {e}")
        raise


if __name__ == "__main__":
    init_default_commands()
