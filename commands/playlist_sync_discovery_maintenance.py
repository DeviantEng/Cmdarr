#!/usr/bin/env python3
"""
Playlist Sync Discovery Maintenance Command
Maintains the unified discovery import list by removing stale entries
"""

import json
import os
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Any, List, Optional

from .command_base import BaseCommand
from clients.client_lidarr import LidarrClient
from utils.logger import get_logger


class PlaylistSyncDiscoveryMaintenanceCommand(BaseCommand):
    """Maintain the playlist sync discovery import list by removing stale entries"""
    
    def __init__(self, config=None):
        super().__init__(config)
        self.logger = get_logger('cmdarr.playlist_sync_discovery_maintenance')
        self.discovery_file = Path("data/import_lists/discovery_playlistsync.json")
        self.backup_file = Path("data/import_lists/discovery_playlistsync.json.backup")
    
    async def execute(self) -> bool:
        """Execute the maintenance command"""
        try:
            self.logger.info("Starting playlist sync discovery maintenance...")
            
            # Load current import list
            current_entries = await self._load_discovery_file()
            if not current_entries:
                self.logger.info("No entries found in discovery file")
                return True
            
            self.logger.info(f"Loaded {len(current_entries)} entries from discovery file")
            
            # Get Lidarr context for filtering
            lidarr_client = LidarrClient(self.config)
            existing_mbids, existing_names, excluded_mbids = await self._get_lidarr_context(lidarr_client)
            
            # Clean up entries
            cleanup_stats = await self._cleanup_entries(
                current_entries, 
                existing_mbids, 
                excluded_mbids
            )
            
            # Save cleaned list if changes were made
            if cleanup_stats['removed_count'] > 0:
                await self._save_discovery_file(cleanup_stats['cleaned_entries'])
                self.logger.info(f"Saved cleaned discovery file with {len(cleanup_stats['cleaned_entries'])} entries")
            else:
                self.logger.info("No cleanup needed - all entries are still valid")
            
            # Log summary
            self.logger.info(f"Maintenance completed: {cleanup_stats['removed_count']} removed, "
                           f"{cleanup_stats['remaining_count']} remaining")
            
            return True
            
        except Exception as e:
            self.logger.error(f"Error during maintenance: {e}")
            return False
    
    async def _load_discovery_file(self) -> List[Dict[str, Any]]:
        """Load the discovery file"""
        try:
            if not self.discovery_file.exists():
                self.logger.warning(f"Discovery file not found: {self.discovery_file}")
                return []
            
            with open(self.discovery_file, 'r', encoding='utf-8') as f:
                entries = json.load(f)
            
            if not isinstance(entries, list):
                self.logger.error("Discovery file does not contain a valid JSON array")
                return []
            
            return entries
            
        except json.JSONDecodeError as e:
            self.logger.error(f"Invalid JSON in discovery file: {e}")
            return []
        except Exception as e:
            self.logger.error(f"Error loading discovery file: {e}")
            return []
    
    async def _get_lidarr_context(self, lidarr_client: LidarrClient) -> tuple:
        """Get Lidarr context for filtering"""
        try:
            # Get existing artists from Lidarr
            self.logger.info("Fetching existing artists from Lidarr...")
            lidarr_artists = await lidarr_client.get_all_artists()
            existing_mbids = {artist['musicBrainzId'] for artist in lidarr_artists}
            existing_names = {artist['artistName'].lower() for artist in lidarr_artists}
            
            self.logger.info(f"Retrieved {len(lidarr_artists)} existing artists from Lidarr")
            
            # Get Import List Exclusions
            self.logger.info("Fetching Import List Exclusions from Lidarr...")
            excluded_mbids = await lidarr_client.get_import_list_exclusions()
            self.logger.info(f"Retrieved {len(excluded_mbids)} Import List Exclusions")
            
            return existing_mbids, existing_names, excluded_mbids
            
        except Exception as e:
            self.logger.error(f"Error getting Lidarr context: {e}")
            return set(), set(), set()
    
    async def _cleanup_entries(self, entries: List[Dict[str, Any]], 
                              existing_mbids: set, excluded_mbids: set) -> Dict[str, Any]:
        """Clean up entries based on Lidarr state and age"""
        try:
            removed_count = 0
            cleaned_entries = []
            removed_entries = []
            
            # Get age threshold from config (default: 30 days)
            age_threshold_days = getattr(self.config, 'PLAYLIST_SYNC_DISCOVERY_AGE_THRESHOLD_DAYS', 30)
            age_threshold = datetime.utcnow() - timedelta(days=age_threshold_days)
            
            self.logger.info(f"Using age threshold: {age_threshold_days} days")
            
            for entry in entries:
                mbid = entry.get('MusicBrainzId')
                artist_name = entry.get('ArtistName', '')
                date_added_str = entry.get('dateAdded', '')
                
                should_remove = False
                removal_reason = ""
                
                # Check if artist is now in Lidarr
                if mbid in existing_mbids:
                    should_remove = True
                    removal_reason = "Artist now in Lidarr"
                
                # Check if artist is excluded
                elif mbid in excluded_mbids:
                    should_remove = True
                    removal_reason = "Artist in exclusions list"
                
                # Check age threshold
                elif date_added_str:
                    try:
                        # Parse dateAdded format: "2025-10-16, 13:15:25"
                        date_added = datetime.strptime(date_added_str, '%Y-%m-%d, %H:%M:%S')
                        if date_added < age_threshold:
                            should_remove = True
                            removal_reason = f"Older than {age_threshold_days} days"
                    except ValueError:
                        self.logger.warning(f"Invalid dateAdded format for {artist_name}: {date_added_str}")
                
                if should_remove:
                    removed_count += 1
                    removed_entries.append({
                        'artist': artist_name,
                        'mbid': mbid,
                        'reason': removal_reason,
                        'dateAdded': date_added_str
                    })
                    self.logger.debug(f"Removing {artist_name} ({mbid}): {removal_reason}")
                else:
                    cleaned_entries.append(entry)
            
            # Log detailed removal info
            if removed_entries:
                self.logger.info(f"Removed {removed_count} entries:")
                for entry in removed_entries[:10]:  # Log first 10
                    self.logger.info(f"  - {entry['artist']}: {entry['reason']}")
                if len(removed_entries) > 10:
                    self.logger.info(f"  ... and {len(removed_entries) - 10} more")
            
            return {
                'removed_count': removed_count,
                'remaining_count': len(cleaned_entries),
                'cleaned_entries': cleaned_entries,
                'removed_entries': removed_entries
            }
            
        except Exception as e:
            self.logger.error(f"Error during cleanup: {e}")
            return {
                'removed_count': 0,
                'remaining_count': len(entries),
                'cleaned_entries': entries,
                'removed_entries': []
            }
    
    async def _save_discovery_file(self, entries: List[Dict[str, Any]]):
        """Save the cleaned discovery file"""
        try:
            # Create backup of original file
            if self.discovery_file.exists():
                import shutil
                shutil.copy2(self.discovery_file, self.backup_file)
                self.logger.info(f"Created backup: {self.backup_file}")
            
            # Ensure directory exists
            self.discovery_file.parent.mkdir(parents=True, exist_ok=True)
            
            # Save cleaned entries
            with open(self.discovery_file, 'w', encoding='utf-8') as f:
                json.dump(entries, f, indent=2, ensure_ascii=False)
            
            self.logger.info(f"Saved {len(entries)} entries to {self.discovery_file}")
            
        except Exception as e:
            self.logger.error(f"Error saving discovery file: {e}")
            raise
    
    def get_description(self) -> str:
        """Return command description"""
        return "Maintain the unified discovery import list by removing stale entries"
    
    def get_logger_name(self) -> str:
        """Return logger name"""
        return 'cmdarr.playlist_sync_discovery_maintenance'
