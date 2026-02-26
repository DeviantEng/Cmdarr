#!/usr/bin/env python3
"""
Playlist Sync Command
Dynamic command for syncing playlists from external sources (Spotify, etc.)
"""

import asyncio
import time
from datetime import datetime
from typing import Dict, List, Any, Optional

from .command_base import BaseCommand
from clients.client_spotify import SpotifyClient
from clients.client_deezer import DeezerClient
from clients.client_plex import PlexClient
from clients.client_jellyfin import JellyfinClient
from utils.library_cache_manager import get_library_cache_manager


class PlaylistSyncCommand(BaseCommand):
    """Dynamic command for syncing playlists from external sources"""
    
    def __init__(self, config=None):
        # Initialize config_json to empty dict to prevent null reference errors
        # This must be done BEFORE calling super().__init__() because get_logger_name() needs it
        self.config_json = {}
        
        super().__init__(config)
        
        # Source client will be initialized based on config
        self.source_client = None
        self.target_client = None
        self.target_name = None
        
        # Initialize library cache manager for performance optimization
        self.library_cache_manager = get_library_cache_manager(self.config)
        
        # Store statistics for reporting
        self.last_run_stats = {}
    
    def _initialize_clients(self):
        """Initialize source and target clients based on command configuration"""
        if not hasattr(self, 'config_json') or not self.config_json:
            raise ValueError("No playlist sync configuration found")
        
        config = self.config_json
        source = config.get('source')
        target = config.get('target')
        
        if not source:
            raise ValueError("No source configured for playlist sync")
        if not target:
            raise ValueError("No target configured for playlist sync")
        
        # Initialize source client
        if source == 'spotify':
            self.source_client = SpotifyClient(self.config)
        elif source == 'deezer':
            self.source_client = DeezerClient(self.config)
        else:
            raise ValueError(f"Unsupported playlist source: {source}")
        
        # Initialize target client
        target = target.lower()
        if target == 'plex':
            self.target_client = PlexClient(self.config)
            self.target_name = 'Plex'
        elif target == 'jellyfin':
            self.target_client = JellyfinClient(self.config)
            self.target_name = 'Jellyfin'
        else:
            raise ValueError(f"Unsupported playlist target: {target}")
    
    def get_description(self) -> str:
        """Return command description for help text."""
        if not hasattr(self, 'config_json') or not self.config_json:
            return "Playlist sync command"
        
        config = self.config_json
        source = config.get('source', 'unknown')
        target = self.target_name or 'music player'
        playlist_name = config.get('playlist_name', 'playlist')
        
        return f"Sync {source.title()} playlist '{playlist_name}' to {target}"
    
    def get_logger_name(self) -> str:
        """Return logger name for this command."""
        unique_id = self.config_json.get('unique_id', 'unknown')
        return f"playlist_sync.{unique_id}"
    
    async def execute(self) -> bool:
        """Execute playlist sync command"""
        try:
            self.logger.info("Starting playlist sync command execution")
            
            # Initialize clients
            self._initialize_clients()
            
            # Get configuration
            config = self.config_json
            playlist_url = config.get('playlist_url')
            playlist_name = config.get('playlist_name')
            sync_mode = config.get('sync_mode', 'full')
            
            if not playlist_url:
                raise ValueError("No playlist URL configured")
            
            self.logger.info(f"Syncing {config.get('source', 'unknown')} playlist: {playlist_name}")
            self.logger.info(f"Target: {self.target_name}, Mode: {sync_mode}")
            
            # Fetch tracks from source
            self.logger.info("Fetching tracks from source playlist...")
            
            # Use source client as context manager for proper session cleanup
            async with self.source_client as client:
                tracks_result = await client.get_playlist_tracks(playlist_url)
            
            if not tracks_result.get('success'):
                error_msg = tracks_result.get('error', 'Unknown error')
                self.logger.error(f"Failed to fetch tracks: {error_msg}")
                return False
            
            tracks = tracks_result.get('tracks', [])
            total_tracks = len(tracks)
            
            if not tracks:
                self.logger.warning("No tracks found in source playlist")
                return True  # Not an error, just empty playlist
            
            self.logger.info(f"Found {total_tracks} tracks in source playlist")
            
            # Prepare playlist title and summary
            playlist_title = f"[{config.get('source', 'Unknown').title()}] {playlist_name}"
            playlist_summary = f"Synced from {config.get('source', 'unknown')} playlist: {playlist_name}"
            
            # Get library cache if available (target resolved library for cache + playlist content)
            cached_data = None
            library_key = None
            if hasattr(self.target_client, 'get_resolved_library_key'):
                library_key = self.target_client.get_resolved_library_key()
            if self.library_cache_manager:
                cached_data = self.library_cache_manager.get_library_cache(
                    self.target_name.lower(), library_key
                )
                if cached_data:
                    track_count = cached_data.get('total_tracks', 0)
                    self.logger.info(f"Using library cache with {track_count:,} tracks")
                else:
                    self.logger.warning(
                        f"Library cache not available for {self.target_name}. "
                        "Playlist sync will use live API (slower performance expected)."
                    )
            
            # Sync playlist based on mode
            sync_result = None
            if sync_mode == 'additive':
                sync_result = await self._sync_additive(playlist_title, tracks, playlist_summary, cached_data, library_key)
            else:  # full sync
                sync_result = await self._sync_full(playlist_title, tracks, playlist_summary, cached_data, library_key)
            
            # Extract success and stats from sync result
            if isinstance(sync_result, dict):
                success = sync_result.get('success', False)
                sync_stats = sync_result
            else:
                success = bool(sync_result)
                sync_stats = {'success': success}
            
            if success:
                self.logger.info(f"Successfully synced playlist '{playlist_title}'")
                
                # Artist discovery (if enabled)
                artist_discovery_stats = None
                self.logger.info("Checking if artist discovery is enabled...")
                if config.get('enable_artist_discovery', False):
                    self.logger.info("Artist discovery is enabled, proceeding...")
                    # Extract unmatched tracks from sync result
                    unmatched_tracks = sync_stats.get('unmatched_tracks', [])
                    self.logger.info(f"Sync stats: {sync_stats}")
                    self.logger.info(f"Unmatched tracks from sync: {unmatched_tracks}")
                    if unmatched_tracks:
                        self.logger.info(f"Found {len(unmatched_tracks)} unmatched tracks for artist discovery")
                        # Convert unmatched track strings back to track objects for artist discovery
                        unmatched_track_objects = []
                        for track_string in unmatched_tracks:
                            if ' - ' in track_string:
                                artist, track_name = track_string.split(' - ', 1)
                                unmatched_track_objects.append({
                                    'artist': artist.strip(),
                                    'track': track_name.strip()
                                })
                        artist_discovery_stats = await self._discover_and_add_artists(unmatched_track_objects, cached_data)
                    else:
                        self.logger.info("No unmatched tracks found - skipping artist discovery")
                        artist_discovery_stats = {
                            'total_artists': 0,
                            'artists_added': 0,
                            'artists_skipped': 0,
                            'artists_failed': 0,
                            'added_artists': [],
                            'skipped_artists': [],
                            'failed_artists': []
                        }
                
                # Get sync statistics from target client
                # sync_stats already contains the result from sync operation
                
                self.last_run_stats = {
                    'total_tracks': total_tracks,
                    'sync_mode': sync_mode,
                    'target': self.target_name,
                    'source': config.get('source'),
                    'sync_stats': sync_stats,
                    'artist_discovery': artist_discovery_stats
                }
                return True
            else:
                self.logger.error(f"Failed to sync playlist '{playlist_title}'")
                return False
                
        except Exception as e:
            self.logger.error(f"Error executing playlist sync: {e}")
            return False
        finally:
            # Ensure clients are properly closed
            await self._close_clients()
    
    async def _close_clients(self):
        """Close HTTP sessions for clients"""
        try:
            # Source client is now managed as context manager, so no manual cleanup needed
            # Target client cleanup is still needed for Plex/Jellyfin
            if hasattr(self, 'target_client') and self.target_client:
                if hasattr(self.target_client, 'close'):
                    await self.target_client.close()
        except Exception as e:
            self.logger.warning(f"Error closing clients: {e}")
    
    async def _discover_and_add_artists(self, tracks: List[Dict[str, Any]], 
                                      cached_data: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        """Discover artists from unmatched tracks and save them to import list"""
        try:
            self.logger.info("Starting artist discovery for unmatched tracks...")
            
            # Collect unique artists from tracks
            unique_artists = set()
            for track in tracks:
                artist = track.get('artist', '').strip()
                if artist:
                    unique_artists.add(artist)
            
            if not unique_artists:
                self.logger.info("No artists found in tracks for discovery")
                return {
                    'total_artists': 0,
                    'artists_added': 0,
                    'artists_skipped': 0,
                    'artists_failed': 0,
                    'added_artists': [],
                    'skipped_artists': [],
                    'failed_artists': []
                }
            
            self.logger.info(f"Found {len(unique_artists)} unique artists to check")
            
            # Initialize clients
            from clients.client_lidarr import LidarrClient
            from clients.client_musicbrainz import MusicBrainzClient
            from utils.discovery import DiscoveryUtils
            
            lidarr_client = LidarrClient(self.config)
            musicbrainz_client = MusicBrainzClient(self.config) if self.config.MUSICBRAINZ_ENABLED else None
            
            if not musicbrainz_client:
                self.logger.warning("MusicBrainz is disabled - cannot discover artists without MBID lookup")
                return {
                    'total_artists': len(unique_artists),
                    'artists_added': 0,
                    'artists_skipped': len(unique_artists),
                    'artists_failed': 0,
                    'added_artists': [],
                    'skipped_artists': list(unique_artists),
                    'failed_artists': [],
                    'error': 'MusicBrainz is disabled'
                }
            
            try:
                # Get Lidarr context for filtering
                discovery_utils = DiscoveryUtils(self.config, lidarr_client, musicbrainz_client)
                existing_mbids, existing_names, excluded_mbids = await discovery_utils.get_lidarr_context()
                
                # Process each artist
                artists_added = 0
                artists_skipped = 0
                artists_failed = 0
                added_artists = []
                skipped_artists = []
                failed_artists = []
                new_discoveries = []
                
                for artist_name in unique_artists:
                    try:
                        # Skip if already in Lidarr (by name)
                        if artist_name.lower() in existing_names:
                            artists_skipped += 1
                            skipped_artists.append({
                                'name': artist_name,
                                'reason': 'Already in Lidarr'
                            })
                            continue
                        
                        # Look up MBID in MusicBrainz
                        mbid_result = await musicbrainz_client.fuzzy_search_artist(artist_name)
                        
                        if not mbid_result or not mbid_result.get('mbid'):
                            self.logger.debug(f"No MBID found for artist: {artist_name}")
                            artists_skipped += 1
                            skipped_artists.append({
                                'name': artist_name,
                                'reason': 'No MBID found in MusicBrainz'
                            })
                            continue
                        
                        mbid = mbid_result['mbid']
                        resolved_name = mbid_result.get('name', artist_name)
                        
                        # Skip if MBID is already in Lidarr or excluded
                        if mbid in existing_mbids or mbid in excluded_mbids:
                            artists_skipped += 1
                            skipped_artists.append({
                                'name': artist_name,
                                'resolved_name': resolved_name,
                                'mbid': mbid,
                                'reason': 'MBID already in Lidarr or excluded'
                            })
                            continue
                        
                        # Create artist entry for import list
                        artist_entry = discovery_utils.create_artist_entry(
                            mbid=mbid,
                            name=resolved_name,
                            source=self.config_json.get('playlist_name', 'unknown'),  # Use playlist name, not command name
                            dateAdded=datetime.utcnow().strftime('%Y-%m-%d, %H:%M:%S')
                        )
                        
                        new_discoveries.append(artist_entry)
                        artists_added += 1
                        added_artists.append({
                            'name': artist_name,
                            'resolved_name': resolved_name,
                            'mbid': mbid
                        })
                        self.logger.info(f"Discovered artist: {resolved_name} (MBID: {mbid})")
                        
                    except Exception as e:
                        artists_failed += 1
                        failed_artists.append({
                            'name': artist_name,
                            'error': str(e)
                        })
                        self.logger.warning(f"Error processing artist {artist_name}: {e}")
                        continue
                
                # Save discovered artists to import list
                if new_discoveries:
                    await self._save_discovered_artists(new_discoveries)
                
                # Log summary
                self.logger.info(f"Artist discovery completed: {artists_added} added to import list, {artists_skipped} skipped, {artists_failed} failed")
                
                # Return detailed statistics
                return {
                    'total_artists': len(unique_artists),
                    'artists_added': artists_added,
                    'artists_skipped': artists_skipped,
                    'artists_failed': artists_failed,
                    'added_artists': added_artists,
                    'skipped_artists': skipped_artists,
                    'failed_artists': failed_artists
                }
            finally:
                if musicbrainz_client and hasattr(musicbrainz_client, 'close'):
                    await musicbrainz_client.close()
            
        except Exception as e:
            self.logger.error(f"Error during artist discovery: {e}")
            return {
                'total_artists': len(unique_artists) if 'unique_artists' in locals() else 0,
                'artists_added': 0,
                'artists_skipped': 0,
                'artists_failed': 0,
                'added_artists': [],
                'skipped_artists': [],
                'failed_artists': [],
                'error': str(e)
            }
    
    async def _save_discovered_artists(self, new_discoveries: List[Dict[str, Any]]):
        """Save discovered artists to the unified import list file"""
        try:
            import json
            import os
            from pathlib import Path
            
            # Path to the playlist sync discovery file
            import_lists_dir = Path("data/import_lists")
            import_lists_dir.mkdir(exist_ok=True)
            discovery_file = import_lists_dir / "discovery_playlistsync.json"
            
            # Load existing discoveries
            existing_discoveries = []
            if discovery_file.exists():
                try:
                    with open(discovery_file, 'r', encoding='utf-8') as f:
                        existing_discoveries = json.load(f)
                except (json.JSONDecodeError, IOError) as e:
                    self.logger.warning(f"Could not load existing discoveries: {e}")
                    existing_discoveries = []
            
            # Create a set of existing MBIDs for deduplication
            existing_mbids = {entry.get('MusicBrainzId') for entry in existing_discoveries}
            
            # Add new discoveries (avoiding duplicates by MBID)
            added_count = 0
            for discovery in new_discoveries:
                mbid = discovery.get('MusicBrainzId')
                if mbid and mbid not in existing_mbids:
                    existing_discoveries.append(discovery)
                    existing_mbids.add(mbid)
                    added_count += 1
            
            # Save updated discoveries
            with open(discovery_file, 'w', encoding='utf-8') as f:
                json.dump(existing_discoveries, f, indent=2, ensure_ascii=False)
            
            self.logger.info(f"Saved {added_count} new artists to {discovery_file}")
            
        except Exception as e:
            self.logger.error(f"Error saving discovered artists: {e}")
            raise
    
    async def _sync_full(self, playlist_title: str, tracks: List[Dict[str, Any]], 
                        summary: str, cached_data: Optional[Dict[str, Any]], 
                        library_key: Optional[str] = None) -> Dict[str, Any]:
        """Sync playlist using full sync mode (delete and recreate)"""
        try:
            self.logger.info(f"Performing full sync for playlist '{playlist_title}'")
            
            result = self.target_client.sync_playlist(
                title=playlist_title,
                tracks=tracks,
                summary=summary,
                library_cache_manager=self.library_cache_manager,
                library_key=library_key,
            )
            
            if result.get('success'):
                action = result.get('action', 'unknown')
                found_tracks = result.get('found_tracks', 0)
                total_tracks = result.get('total_tracks', 0)
                
                self.logger.info(f"Full sync completed: {action}, {found_tracks}/{total_tracks} tracks matched")
                return result
            else:
                self.logger.error(f"Full sync failed: {result.get('message', 'Unknown error')}")
                return result
                
        except Exception as e:
            self.logger.error(f"Error in full sync: {e}")
            return {
                'success': False,
                'action': 'full_sync',
                'total_tracks': len(tracks),
                'found_tracks': 0,
                'message': f"Error in full sync: {str(e)}"
            }
    
    async def _sync_additive(self, playlist_title: str, tracks: List[Dict[str, Any]], 
                           summary: str, cached_data: Optional[Dict[str, Any]], 
                           library_key: Optional[str] = None) -> Dict[str, Any]:
        """Sync playlist using additive mode (only add new tracks)"""
        try:
            self.logger.info(f"Performing additive sync for playlist '{playlist_title}'")
            
            # Check if playlist exists
            existing_playlist = self.target_client.find_playlist_by_name(playlist_title)
            
            if not existing_playlist:
                # Playlist doesn't exist, create it with all tracks
                self.logger.info(f"Playlist '{playlist_title}' doesn't exist, creating with all tracks")
                return await self._sync_full(playlist_title, tracks, summary, cached_data, library_key)
            
            # Get existing tracks
            playlist_rating_key = existing_playlist.get('ratingKey') or existing_playlist.get('Id')
            existing_track_keys = self.target_client.get_playlist_track_rating_keys(playlist_rating_key)
            
            self.logger.info(f"Found existing playlist with {len(existing_track_keys)} tracks")
            
            # Find tracks to add (not already in playlist)
            tracks_to_add = []
            for track in tracks:
                artist = track.get('artist', '')
                track_name = track.get('track', '')
                
                if not artist or not track_name:
                    continue
                
                # Search for track in target library
                album = track.get('album', '')
                rating_key = self.target_client.search_for_track(
                    track_name, artist, cached_data=cached_data, album_name=album
                )
                
                if rating_key and rating_key not in existing_track_keys:
                    tracks_to_add.append(rating_key)
            
            if not tracks_to_add:
                self.logger.info("No new tracks to add to playlist")
                return {
                    'success': True,
                    'action': 'additive_sync',
                    'total_tracks': len(tracks),
                    'found_tracks': len(existing_track_keys),
                    'added_tracks': 0,
                    'message': "No new tracks to add to playlist"
                }
            
            self.logger.info(f"Adding {len(tracks_to_add)} new tracks to playlist")
            
            # Add new tracks to existing playlist
            success = self.target_client.add_tracks_to_playlist(playlist_rating_key, tracks_to_add)
            
            if success:
                self.logger.info(f"Successfully added {len(tracks_to_add)} tracks to playlist")
                return {
                    'success': True,
                    'action': 'additive_sync',
                    'total_tracks': len(tracks),
                    'found_tracks': len(existing_track_keys) + len(tracks_to_add),
                    'added_tracks': len(tracks_to_add),
                    'message': f"Successfully added {len(tracks_to_add)} tracks to playlist"
                }
            else:
                self.logger.error("Failed to add tracks to playlist")
                return {
                    'success': False,
                    'action': 'additive_sync',
                    'total_tracks': len(tracks),
                    'found_tracks': len(existing_track_keys),
                    'added_tracks': 0,
                    'message': "Failed to add tracks to playlist"
                }
                
        except Exception as e:
            self.logger.error(f"Error in additive sync: {e}")
            return {
                'success': False,
                'action': 'additive_sync',
                'total_tracks': len(tracks),
                'found_tracks': 0,
                'added_tracks': 0,
                'message': f"Error in additive sync: {str(e)}"
            }
