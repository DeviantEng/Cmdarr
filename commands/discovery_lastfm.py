#!/usr/bin/env python3
"""
Similar Artists Discovery Command
Queries Lidarr artists and finds similar artists via Last.fm and MusicBrainz
REFACTORED: Uses utils/discovery.py to eliminate code duplication
"""

import json
import os
from typing import List, Dict, Any

from .command_base import BaseCommand
from clients.client_lidarr import LidarrClient
from clients.client_lastfm import LastFMClient
from clients.client_musicbrainz import MusicBrainzClient
from utils.discovery import DiscoveryUtils, FilteringStats


class DiscoveryLastfmCommand(BaseCommand):
    """Command to discover similar artists for Lidarr import using shared utilities"""
    
    def __init__(self, config=None):
        super().__init__(config)
        self.lidarr = LidarrClient(self.config)
        self.lastfm = LastFMClient(self.config)
        self.musicbrainz = MusicBrainzClient(self.config) if self.config.MUSICBRAINZ_ENABLED else None
        
        # Initialize shared utilities
        self.utils = DiscoveryUtils(self.config, self.lidarr, self.musicbrainz)
        
        # Store statistics for reporting
        self.last_run_stats = {}
    
    def get_description(self) -> str:
        """Return command description for help text."""
        return "Discover similar artists from Last.fm and MusicBrainz for Lidarr import with exclusion filtering"
    
    def get_logger_name(self) -> str:
        """Return logger name for this command."""
        return "discovery_lastfm"
    
    async def execute(self) -> bool:
        """Execute the similar artists discovery process"""
        try:
            self.logger.info("Starting similar artists discovery process")
            
            # Clean up expired cache entries
            await self.utils.cleanup_expired_cache()
            
            # Discover similar artists with shared utilities
            similar_artists = await self._discover_similar_artists()
            
            # Save results
            self._save_results(similar_artists)
            
            self.logger.info("Similar artists discovery completed successfully")
            return True
            
        except Exception as e:
            self.logger.error(f"Similar artists discovery failed: {e}")
            return False
    
    async def _discover_similar_artists(self) -> List[Dict[str, Any]]:
        """Main processing function using shared utilities"""
        
        # Get Lidarr context (existing artists + exclusions)
        existing_mbids, existing_names, excluded_mbids = await self.utils.get_lidarr_context()
        
        # Get all Lidarr artists for Last.fm processing
        lidarr_artists = await self.lidarr.get_all_artists()
        artist_lookup = {artist['musicBrainzId']: artist['artistName'] for artist in lidarr_artists}
        
        # Statistics tracking
        stats = FilteringStats()
        stats.exclusions_count = len(excluded_mbids)
        
        # Get raw similar artists from Last.fm
        self.logger.info("Querying Last.fm for similar artists...")
        all_raw_similar, all_skipped_artists = await self._fetch_lastfm_similar_artists(artist_lookup)
        
        # Process skipped artists through MusicBrainz
        musicbrainz_recovered = []
        if all_skipped_artists:
            musicbrainz_recovered = await self.utils.process_artists_through_musicbrainz(
                all_skipped_artists, existing_mbids, existing_names, excluded_mbids,
                "discovery_lastfm"
            )
            
            # Add recovered artists to raw similar list
            for recovered in musicbrainz_recovered:
                all_raw_similar.append({
                    'name': recovered['ArtistName'],
                    'mbid': recovered['MusicBrainzId'],
                    'match': recovered.get('lastfmMatchScore', '0.0'),
                    'url': '',
                    'source_artist': recovered.get('similarArtistTo', ''),
                    'musicbrainz_recovered': True
                })
        
        # Deduplicate raw similar artists
        deduplicated_raw = self.utils.deduplicate_by_mbid(all_raw_similar, 'match')
        stats.total_candidates = len(deduplicated_raw)
        stats.musicbrainz_recovered = len(musicbrainz_recovered)
        
        # Filter candidates against Lidarr state and exclusions
        final_artists = []
        for similar in deduplicated_raw:
            mbid = similar['mbid']
            name = similar['name']
            
            # Apply filtering logic
            should_include, reason = self.utils.filter_artist_candidate(
                mbid, name, existing_mbids, existing_names, excluded_mbids
            )
            
            if not should_include:
                if reason == "already_in_lidarr_mbid" or reason == "already_in_lidarr_name":
                    stats.filtered_already_in_lidarr += 1
                elif reason == "in_exclusions":
                    stats.filtered_in_exclusions += 1
                continue
            
            # Check minimum match score
            try:
                match_score = float(similar['match'])
                # Use command-specific min_match_score if available, otherwise fall back to global config
                min_match_score = 0.0  # Default fallback
                if hasattr(self, 'config_json') and self.config_json and 'min_match_score' in self.config_json:
                    min_match_score = self.config_json['min_match_score']
                elif hasattr(self.config, 'LASTFM_MIN_MATCH_SCORE'):
                    min_match_score = self.config.LASTFM_MIN_MATCH_SCORE
                
                if match_score < min_match_score:
                    stats.filtered_low_score += 1
                    continue
            except (ValueError, TypeError):
                stats.filtered_low_score += 1
                continue
            
            # Create artist entry using shared utility
            artist_entry = self.utils.create_artist_entry(
                mbid=mbid,
                name=name,
                    source="discovery_lastfm",
                similarArtistTo=similar['source_artist'],
                lastfmMatchScore=similar['match']
            )
            
            if similar.get('musicbrainz_recovered'):
                artist_entry["recoveredVia"] = "musicbrainz_fuzzy_match"
            
            final_artists.append(artist_entry)
        
        stats.valid_candidates = len(final_artists)
        
        # Apply random sampling using shared utility
        # Use command-specific limit if available, otherwise fall back to global config
        limit = 5  # Default fallback
        if hasattr(self, 'config_json') and self.config_json and 'limit' in self.config_json:
            limit = self.config_json['limit']
        elif hasattr(self.config, 'DISCOVERY_LASTFM_LIMIT'):
            limit = self.config.DISCOVERY_LASTFM_LIMIT
        
        output_artists, limited_count, random_sampling = self.utils.apply_random_sampling(
            final_artists, limit, "discovery_lastfm"
        )
        
        stats.final_count = len(output_artists)
        stats.limited_count = limited_count
        stats.random_sampling_applied = random_sampling
        
        # Clean up HTTP sessions
        await self.lastfm.close()
        if self.musicbrainz:
            await self.musicbrainz.close()
        
        # Store and log statistics
        self.last_run_stats = stats.to_dict()
        self.utils.log_filtering_statistics("Last.fm Discovery", stats.to_dict())
        
        self.logger.info(f"Final result: {len(output_artists)} unique similar artists for output")
        return output_artists
    
    async def _fetch_lastfm_similar_artists(self, artist_lookup: Dict[str, str]) -> tuple:
        """Fetch similar artists from Last.fm with fallback to name-based search"""
        all_raw_similar = []
        all_skipped_artists = []
        failed_lookups = []
        
        # Tracking statistics
        lastfm_mbid_success = 0
        total_similar_returned = 0
        
        for mbid, artist_name in artist_lookup.items():
            try:
                # Get similar artists from Last.fm (with name fallback and caching)
                lastfm_similar, skipped_artists = await self.lastfm.get_similar_artists(mbid, artist_name)
                
                if lastfm_similar or skipped_artists:
                    lastfm_mbid_success += 1
                
                # Add source artist info to skipped artists
                for skipped in skipped_artists:
                    skipped['source_artist'] = artist_name
                    skipped['source_mbid'] = mbid
                    all_skipped_artists.append(skipped)
                
                # Add all raw similar artists
                for similar in lastfm_similar:
                    similar['source_artist'] = artist_name
                    similar['source_mbid'] = mbid
                    all_raw_similar.append(similar)
                
                total_similar_returned += len(lastfm_similar) + len(skipped_artists)
                
                if not lastfm_similar and not skipped_artists:
                    failed_lookups.append((mbid, artist_name))
                    
            except Exception as e:
                self.logger.error(f"Error processing artist {artist_name} (MBID: {mbid}): {e}")
                failed_lookups.append((mbid, artist_name))
        
        # Log initial results
        self.logger.info(f"{lastfm_mbid_success} artists processed successfully, {len(failed_lookups)} failed lookups")
        self.logger.info(f"Retrieved {total_similar_returned} total similar artist suggestions")
        
        # Log validation calls for failed lookups if enabled
        if failed_lookups and self.config.GENERATE_DEBUG_VALIDATION_CALLS:
            self._log_validation_calls(failed_lookups)
        
        return all_raw_similar, all_skipped_artists
    
    def _log_validation_calls(self, failed_lookups: List[tuple]):
        """Generate debug validation calls for failed MBID lookups"""
        self.logger.debug(f"Failed MBID lookups - validation calls for {len(failed_lookups)} artists:")
        for mbid, artist_name in failed_lookups:
            self.logger.debug(f"  Artist: \"{artist_name}\" MBID: {mbid}")
            self.logger.debug(f"    Check existence: http://ws.audioscrobbler.com/2.0/?method=artist.getinfo&mbid={mbid}&api_key={{API_KEY}}&format=json")
            self.logger.debug(f"    Check by name: http://ws.audioscrobbler.com/2.0/?method=artist.getinfo&artist={artist_name.replace(' ', '%20')}&api_key={{API_KEY}}&format=json")
    
    def _save_results(self, artists: List[Dict[str, Any]], filename: str = None):
        """Save results to JSON file"""
        if filename is None:
            filename = self.config.OUTPUT_FILE
            
        # Ensure output directory exists
        os.makedirs(os.path.dirname(filename), exist_ok=True)
            
        with open(filename, 'w', encoding='utf-8') as f:
            if self.config.PRETTY_PRINT_JSON:
                json.dump(artists, f, indent=2, ensure_ascii=False)
            else:
                json.dump(artists, f, ensure_ascii=False)
            
        self.logger.info(f"Results saved to {filename}")
