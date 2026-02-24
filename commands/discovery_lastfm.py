#!/usr/bin/env python3
"""
Similar Artists Discovery Command
Queries Lidarr artists and finds similar artists via Last.fm and MusicBrainz
REFACTORED: Uses utils/discovery.py to eliminate code duplication
Samples X Lidarr artists, gets Y similar per artist - configurable for performance.
Time-based exclusion: artists queried recently (configurable days) are skipped.
"""

import json
import os
import random
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import List, Dict, Any, Set, Tuple

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
            similar_artists, sampled_mbids = await self._discover_similar_artists()
            
            # Save results
            self._save_results(similar_artists)
            
            # Record sampled artists for time-based exclusion
            if sampled_mbids:
                self._save_queried_artists(sampled_mbids)
            
            self.logger.info("Similar artists discovery completed successfully")
            return True
            
        except Exception as e:
            self.logger.error(f"Similar artists discovery failed: {e}")
            return False
    
    def _get_queried_file_path(self) -> Path:
        """Path to JSON file storing recently queried artist MBIDs."""
        output_dir = Path(self.config.OUTPUT_FILE).parent
        return output_dir / "discovery_lastfm_queried.json"

    def _load_queried_artists(self, cooldown_days: int) -> Set[str]:
        """Load artist MBIDs queried within cooldown_days. Prunes expired entries."""
        path = self._get_queried_file_path()
        if not path.exists():
            return set()
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except (json.JSONDecodeError, OSError) as e:
            self.logger.warning(f"Could not load queried artists file: {e}")
            return set()
        cutoff = datetime.now(timezone.utc) - timedelta(days=cooldown_days)
        cutoff_iso = cutoff.isoformat()
        recent = set()
        pruned = {}
        for mbid, queried_at in (data or {}).items():
            if queried_at >= cutoff_iso:
                recent.add(mbid)
                pruned[mbid] = queried_at
        if len(pruned) < len(data or {}):
            self._write_queried_file(pruned)
        return recent

    def _write_queried_file(self, data: Dict[str, str]) -> None:
        """Write queried artists to JSON file."""
        path = self._get_queried_file_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=0)
        except OSError as e:
            self.logger.warning(f"Could not save queried artists file: {e}")

    def _save_queried_artists(self, mbids: List[str]) -> None:
        """Append sampled MBIDs with current timestamp. Prunes old entries."""
        path = self._get_queried_file_path()
        cfg = getattr(self, 'config_json', None) or {}
        cooldown_days = max(1, int(cfg.get('artist_cooldown_days', 30)))
        cutoff = datetime.now(timezone.utc) - timedelta(days=cooldown_days)
        cutoff_iso = cutoff.isoformat()
        now_iso = datetime.now(timezone.utc).isoformat()
        existing = {}
        if path.exists():
            try:
                with open(path, "r", encoding="utf-8") as f:
                    existing = json.load(f) or {}
            except (json.JSONDecodeError, OSError):
                pass
        for mbid in mbids:
            existing[mbid] = now_iso
        pruned = {k: v for k, v in existing.items() if v >= cutoff_iso}
        self._write_queried_file(pruned)

    async def _discover_similar_artists(self) -> Tuple[List[Dict[str, Any]], List[str]]:
        """Main processing function using shared utilities. Returns (output_artists, sampled_mbids)."""
        
        # Get Lidarr context (existing artists + exclusions)
        existing_mbids, existing_names, excluded_mbids = await self.utils.get_lidarr_context()
        
        # Get all Lidarr artists for Last.fm processing
        lidarr_artists = await self.lidarr.get_all_artists()
        artist_lookup = {a['musicBrainzId']: a['artistName'] for a in lidarr_artists if a.get('musicBrainzId')}
        
        # Command config: artists_to_query (X), similar_per_artist (Y), artist_cooldown_days, etc.
        cfg = getattr(self, 'config_json', None) or {}
        artists_to_query = max(1, int(cfg.get('artists_to_query', 3)))
        similar_per_artist = max(1, int(cfg.get('similar_per_artist') or cfg.get('similar_count', 1)))
        cooldown_days = max(1, int(cfg.get('artist_cooldown_days', 30)))
        
        # Load recently queried artists (time-based exclusion)
        recently_queried = self._load_queried_artists(cooldown_days)
        if recently_queried:
            self.logger.info(f"Excluding {len(recently_queried)} artists queried within last {cooldown_days} days")
        
        # Filter to artists not in cooldown
        artist_items = [(m, n) for m, n in artist_lookup.items() if m not in recently_queried]
        if len(artist_items) < artists_to_query:
            if artist_items:
                self.logger.info(f"Only {len(artist_items)} artists available (cooldown), using all")
            else:
                self.logger.info("All artists in cooldown, sampling from full library")
                artist_items = list(artist_lookup.items())
        
        # Sample X artists from Lidarr
        if len(artist_items) <= artists_to_query:
            sampled_lookup = dict(artist_items)
        else:
            sampled = random.sample(artist_items, artists_to_query)
            sampled_lookup = dict(sampled)
        
        sampled_mbids = list(sampled_lookup.keys())
        
        self.logger.info(
            f"Sampling {len(sampled_lookup)} of {len(artist_lookup)} Lidarr artists, "
            f"requesting {similar_per_artist} similar per artist"
        )
        
        # Statistics tracking
        stats = FilteringStats()
        stats.exclusions_count = len(excluded_mbids)
        
        # Get raw similar artists from Last.fm (only for sampled artists)
        self.logger.info("Querying Last.fm for similar artists...")
        all_raw_similar, all_skipped_artists = await self._fetch_lastfm_similar_artists(
            sampled_lookup, similar_per_artist
        )
        
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
            
            # Check minimum match score (0-1, default 0.9)
            try:
                match_score = float(similar['match'])
                cfg = getattr(self, 'config_json', None) or {}
                min_match_score = float(cfg.get('min_match_score', 0.9))
                if hasattr(self.config, 'LASTFM_MIN_MATCH_SCORE') and 'min_match_score' not in cfg:
                    min_match_score = float(self.config.LASTFM_MIN_MATCH_SCORE)
                min_match_score = max(0.0, min(1.0, min_match_score))
                
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
        cfg = getattr(self, 'config_json', None) or {}
        limit = int(cfg.get('limit', 5))
        if limit <= 0:
            limit = getattr(self.config, 'DISCOVERY_LASTFM_LIMIT', 5)
        
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
        return output_artists, sampled_mbids
    
    async def _fetch_lastfm_similar_artists(
        self, artist_lookup: Dict[str, str], similar_per_artist: int = 1
    ) -> tuple:
        """Fetch similar artists from Last.fm with fallback to name-based search.
        
        Args:
            artist_lookup: Dict of mbid -> artist_name (already sampled to X artists)
            similar_per_artist: Number of similar artists to request per Lidarr artist (Y)
        """
        all_raw_similar = []
        all_skipped_artists = []
        failed_lookups = []
        
        # Tracking statistics
        lastfm_mbid_success = 0
        total_similar_returned = 0
        
        for mbid, artist_name in artist_lookup.items():
            try:
                # Get similar artists from Last.fm (with name fallback and caching)
                lastfm_similar, skipped_artists = await self.lastfm.get_similar_artists(
                    mbid, artist_name, limit=similar_per_artist
                )
                
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
