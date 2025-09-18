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
from database.models import CommandConfig
import logging

# Setup basic logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('cmdarr.init_commands')


def init_default_commands():
    """Initialize default command configurations"""
    
    default_commands = [
        {
            'command_name': 'discovery_lastfm',
            'display_name': 'Last.fm Discovery',
            'description': 'Discover similar artists from Last.fm and MusicBrainz for Lidarr import',
            'enabled': False,
            'schedule_hours': 24,
            'timeout_minutes': 30,
            'config_json': {
                'limit': 5,
                'similar_count': 1,
                'min_match_score': 0.5
            }
        },
        {
            'command_name': 'discovery_listenbrainz',
            'display_name': 'ListenBrainz Discovery',
            'description': 'Discover artists from ListenBrainz Weekly Discovery playlist for Lidarr import',
            'enabled': False,
            'schedule_hours': 24,
            'timeout_minutes': 30,
            'config_json': {
                'limit': 5
            }
        },
        {
            'command_name': 'playlist_sync_listenbrainz_curated',
            'display_name': 'ListenBrainz Playlist Sync',
            'description': 'Sync ListenBrainz curated playlists to music players',
            'enabled': False,
            'schedule_hours': 12,
            'timeout_minutes': 30,
            'config_json': {
                'target': 'plex',
                'weekly_exploration': True,
                'weekly_jams': True,
                'daily_jams': False,
                'playlist_cleanup': True,
                'weekly_exploration_keep': 2,
                'weekly_jams_keep': 2,
                'daily_jams_keep': 3
            }
        },
        {
            'command_name': 'library_cache_builder',
            'display_name': 'Library Cache Builder',
            'description': 'Builds and maintains library caches for configured music players (helper command)',
            'enabled': False,
            'schedule_hours': 24,
            'timeout_minutes': 180,
            'config_json': {
                'plex_enabled': False,
                'jellyfin_enabled': False
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
