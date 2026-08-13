#!/usr/bin/env python3
"""
Initialize default command configurations in the database
"""

import sys
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import logging

from database.config_models import CommandConfig
from database.database import get_database_manager

# Setup basic logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("cmdarr.init_commands")


def init_default_commands():
    """Initialize default command configurations"""

    # Order matters: ids are assigned by insertion order. Maintenance first (id 1) so it runs
    # before playlist syncs when the scheduler sorts due commands by id.
    default_commands = [
        {
            "command_name": "playlist_sync_discovery_maintenance",
            "display_name": "Playlist Sync Discovery Maintenance",
            "description": "Removes stale entries from the playlist sync discovery import list and refreshes the Lidarr artist cache. Empty file is normal when playlists have no new artists to add.",
            "enabled": True,
            "timeout_minutes": 30,
            "command_type": "discovery",
            "config_json": {"age_threshold_days": 30},
        },
        {
            "command_name": "discovery_lastfm",
            "display_name": "Last.fm Discovery",
            "description": "Discover similar artists from Last.fm and add them to Lidarr via API",
            "enabled": False,
            "timeout_minutes": 30,
            "command_type": "discovery",
            "config_json": {
                "artists_to_query": 3,
                "similar_per_artist": 1,
                "artist_cooldown_days": 30,
                "limit": 5,
                "min_match_score": 0.9,
                "search_for_missing_albums": False,
            },
        },
        {
            "command_name": "library_cache_builder",
            "display_name": "Library Cache Builder",
            "description": "Builds and maintains library caches for configured music players (helper command)",
            "enabled": False,
            "timeout_minutes": 180,
            "command_type": None,
            "config_json": {"plex_enabled": False, "jellyfin_enabled": False},
        },
        {
            "command_name": "new_releases_discovery",
            "display_name": "New Releases Discovery",
            "description": "Scan Lidarr artists for Deezer (or Spotify) releases missing from MusicBrainz",
            "enabled": False,
            "timeout_minutes": 30,
            "command_type": "discovery",
            "config_json": {
                "artists_per_run": 25,
                "album_types": "album",
                "new_releases_source": "deezer",
                "continual_validation_enabled": False,
                "continual_validation_batch_size": 50,
                "continual_validation_interval_days": 14,
            },
        },
        {
            "command_name": "artist_events_refresh",
            "display_name": "Artist Events Refresh",
            "description": "Fetch upcoming events for Lidarr artists (Ticketmaster / SeatGeek / Deezer)",
            "enabled": False,
            "timeout_minutes": 60,
            "command_type": "discovery",
            "config_json": {
                "artists_per_run": 20,
                "refresh_ttl_days": 14,
            },
        },
        {
            "command_name": "library_audit",
            "display_name": "Library Audit",
            "description": "Inventory music files and analyze pending FLACs for authenticity issues (requires LIBRARY_AUDIT_ENABLED and /music mount)",
            "enabled": False,
            "timeout_minutes": 120,
            "command_type": None,
            "config_json": {
                "analysis_batch_size": 25,
                "inventory_interval_hours": 24,
                "extensions": [".flac"],
                "review_threshold": "WARNING",
                "missing_retention_days": 90,
                "analysis_provider": "flac_detective",
                "provider_mode": "standard",
            },
        },
    ]

    try:
        manager = get_database_manager()
        session = manager.get_session_sync()
        try:
            for command_data in default_commands:
                # Check if command already exists
                existing = (
                    session.query(CommandConfig)
                    .filter(CommandConfig.command_name == command_data["command_name"])
                    .first()
                )

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
