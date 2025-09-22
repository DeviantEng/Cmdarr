#!/usr/bin/env python3
"""
ListenBrainz Discovery Command
Extracts artists from ListenBrainz Weekly Discovery playlist for Lidarr import
REFACTORED: Uses utils/discovery.py to eliminate code duplication
"""

import json
import os
from typing import List, Dict, Any

from .command_base import BaseCommand
from clients.client_lidarr import LidarrClient
from clients.client_listenbrainz import ListenBrainzClient
from clients.client_musicbrainz import MusicBrainzClient
from utils.discovery import DiscoveryUtils, FilteringStats


class DiscoveryListenbrainzCommand(BaseCommand):
    """Command to discover artists from ListenBrainz Weekly Discovery playlist using shared utilities"""
    
    def __init__(self, config=None):
        super().__init__(config)
        self.lidarr = LidarrClient(self.config)
        self.listenbrainz = ListenBrainzClient(self.config)
        self.musicbrainz = MusicBrainzClient(self.config) if self.config.MUSICBRAINZ_ENABLED else None
        
        # Initialize shared utilities
        self.utils = DiscoveryUtils(self.config, self.lidarr, self.musicbrainz)
        
        # Store statistics for reporting
        self.last_run_stats = {}
    
    def get_description(self) -> str:
        """Return command description for help text."""
        return "Discover artists from ListenBrainz Weekly Discovery playlist for Lidarr import with exclusion filtering"
    
    def get_logger_name(self) -> str:
        """Return logger name for this command."""
        return "discovery_listenbrainz"
    
    async def execute(self) -> bool:
        """Execute the ListenBrainz discovery process"""
        try:
            self.logger.info("Starting ListenBrainz discovery process")
            
            # Clean up expired cache entries
            await self.utils.cleanup_expired_cache()
            
            # Discover artists from ListenBrainz with shared utilities
            discovery_artists = await self._discover_artists_from_listenbrainz()
            
            # Save results
            self._save_results(discovery_artists)
            
            self.logger.info("ListenBrainz discovery completed successfully")
            return True
            
        except Exception as e:
            self.logger.error(f"ListenBrainz discovery failed: {e}")
            return False
    
    async def _discover_artists_from_listenbrainz(self) -> List[Dict[str, Any]]:
        """Main processing function using shared utilities"""
        
        # Get Lidarr context (existing artists + exclusions)
        existing_mbids, existing_names, excluded_mbids = await self.utils.get_lidarr_context()
        
        # Statistics tracking
        stats = FilteringStats()
        stats.exclusions_count = len(excluded_mbids)
        
        # Get Weekly Discovery playlist from ListenBrainz
        self.logger.info(f"Fetching Weekly Discovery playlist for user: {self.config.LISTENBRAINZ_USERNAME}")
        discovery_playlist = await self.listenbrainz.get_discovery_playlist(self.config.LISTENBRAINZ_USERNAME)
        
        if not discovery_playlist:
            self.logger.warning("No Weekly Discovery playlist found")
            return []
        
        # Extract artists from playlist
        playlist_artists = await self.listenbrainz.extract_artists_from_playlist(discovery_playlist)
        
        if not playlist_artists:
            self.logger.warning("No artists found in Weekly Discovery playlist")
            return []
        
        self.logger.info(f"Found {len(playlist_artists)} artists in Weekly Discovery playlist")
        stats.total_candidates = len(playlist_artists)
        
        # Process playlist artists with filtering
        processed_artists = []
        skipped_no_mbid = []
        
        for artist in playlist_artists:
            artist_name = artist['name']
            artist_mbid = artist.get('mbid')
            
            # Apply filtering using shared utility
            if artist_mbid:
                should_include, reason = self.utils.filter_artist_candidate(
                    artist_mbid, artist_name, existing_mbids, existing_names, excluded_mbids
                )
                
                if not should_include:
                    if reason == "already_in_lidarr_mbid" or reason == "already_in_lidarr_name":
                        stats.filtered_already_in_lidarr += 1
                    elif reason == "in_exclusions":
                        stats.filtered_in_exclusions += 1
                    self.logger.debug(f"Skipping artist ({reason}): {artist_name}")
                    continue
                
                # Create artist entry using shared utility
                artist_entry = self.utils.create_artist_entry(
                    mbid=artist_mbid,
                    name=artist_name,
                    source="discovery_listenbrainz",
                    track_title=artist.get('track_title', '')
                )
                processed_artists.append(artist_entry)
            else:
                # No MBID - queue for MusicBrainz lookup
                skipped_no_mbid.append(artist)
        
        self.logger.info(f"Artists with MBIDs: {len(processed_artists)}, without MBIDs: {len(skipped_no_mbid)}")
        
        # Process artists without MBIDs through MusicBrainz using shared utility
        musicbrainz_recovered = []
        if skipped_no_mbid:
            musicbrainz_recovered = await self.utils.process_artists_through_musicbrainz(
                skipped_no_mbid, existing_mbids, existing_names, excluded_mbids,
                "discovery_listenbrainz"
            )
            
            if musicbrainz_recovered:
                self.logger.info(f"MusicBrainz recovered {len(musicbrainz_recovered)} additional artists")
                processed_artists.extend(musicbrainz_recovered)
        
        stats.valid_candidates = len(processed_artists)
        stats.musicbrainz_recovered = len(musicbrainz_recovered)
        
        # Apply random sampling using shared utility
        # Use command-specific limit if available, otherwise fall back to global config
        limit = 5  # Default fallback
        if hasattr(self, 'config_json') and self.config_json and 'limit' in self.config_json:
            limit = self.config_json['limit']
        elif hasattr(self.config, 'DISCOVERY_LISTENBRAINZ_LIMIT'):
            limit = self.config.DISCOVERY_LISTENBRAINZ_LIMIT
        
        output_artists, limited_count, random_sampling = self.utils.apply_random_sampling(
            processed_artists, limit, "discovery_listenbrainz"
        )
        
        stats.final_count = len(output_artists)
        stats.limited_count = limited_count
        stats.random_sampling_applied = random_sampling
        
        # Clean up HTTP sessions
        await self.listenbrainz.close()
        if self.musicbrainz:
            await self.musicbrainz.close()
        
        # Store and log statistics using shared utility
        self.last_run_stats = stats.to_dict()
        self.last_run_stats['playlist_title'] = discovery_playlist.get('title', 'Unknown')
        
        self.utils.log_filtering_statistics("ListenBrainz Discovery", stats.to_dict())
        
        # Add playlist-specific logging
        self._log_playlist_specific_stats(stats, discovery_playlist)
        
        self.logger.info(f"Final result: {len(output_artists)} unique artists for output")
        return output_artists
    
    def _log_playlist_specific_stats(self, stats: FilteringStats, playlist: Dict[str, Any]):
        """Log playlist-specific statistics"""
        self.logger.info("=" * 70)
        self.logger.info("PLAYLIST-SPECIFIC STATISTICS")
        self.logger.info("=" * 70)
        
        playlist_title = playlist.get('title', 'Unknown')
        self.logger.info(f"Playlist: {playlist_title}")
        
        # Better effectiveness messaging
        if stats.total_candidates > 0:
            if stats.final_count > 0:
                effectiveness = (stats.final_count / stats.total_candidates * 100)
                self.logger.info(f"Discovery Effectiveness:              {effectiveness:.1f}% ({stats.final_count} new artists found)")
            else:
                # All candidates were filtered - this is actually good!
                filtered_count = stats.filtered_already_in_lidarr + stats.filtered_in_exclusions
                if filtered_count == stats.total_candidates:
                    self.logger.info(f"Discovery Effectiveness:              100% (All {stats.total_candidates} artists already in Lidarr or excluded)")
                else:
                    self.logger.info(f"Discovery Effectiveness:              0% (No new artists found - {stats.total_candidates} candidates processed)")
        
        # Breakdown of playlist processing
        artists_with_mbids = stats.valid_candidates - stats.musicbrainz_recovered
        artists_without_mbids = len(self.last_run_stats.get('artists_without_mbids', []))
        
        self.logger.info(f"Artists with MBIDs from playlist:     {artists_with_mbids:,}")
        self.logger.info(f"Artists without MBIDs from playlist:  {artists_without_mbids:,}")
        
        # Summary message
        if stats.final_count == 0:
            self.logger.info("✅ Discovery completed successfully - no new artists to add")
            self.logger.info("   (All discovered artists are already in Lidarr or excluded)")
        else:
            self.logger.info(f"✅ Discovery completed successfully - {stats.final_count} new artists found")
        
        self.logger.info("=" * 70)
    
    def _save_results(self, artists: List[Dict[str, Any]], filename: str = None):
        """Save results to JSON file"""
        if filename is None:
            filename = self.config.LISTENBRAINZ_OUTPUT_FILE
            
        # Ensure output directory exists
        os.makedirs(os.path.dirname(filename), exist_ok=True)
            
        with open(filename, 'w', encoding='utf-8') as f:
            if self.config.PRETTY_PRINT_JSON:
                json.dump(artists, f, indent=2, ensure_ascii=False)
            else:
                json.dump(artists, f, ensure_ascii=False)
            
        self.logger.info(f"Results saved to {filename}")
