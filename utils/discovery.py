#!/usr/bin/env python3
"""
Discovery Utilities
Shared functions for discovery commands to eliminate code duplication
Handles exclusion filtering, random sampling, and common processing patterns
"""

import random
import logging
from typing import List, Dict, Any, Set, Tuple, Optional
# Import clients only when needed to avoid circular imports


class DiscoveryUtils:
    """Shared utilities for discovery commands"""
    
    def __init__(self, config, lidarr_client, musicbrainz_client=None):
        self.config = config
        self.lidarr = lidarr_client
        self.musicbrainz = musicbrainz_client
        self.logger = logging.getLogger('cmdarr.discovery_utils')
    
    async def get_lidarr_context(self) -> Tuple[Set[str], Set[str], Set[str]]:
        """
        Get current Lidarr context for filtering
        
        Returns:
            Tuple of (existing_mbids, existing_names_lower, excluded_mbids)
        """
        # Get existing artists from Lidarr
        self.logger.info("Fetching existing artists from Lidarr...")
        lidarr_artists = await self.lidarr.get_all_artists()
        existing_mbids = set(artist['musicBrainzId'] for artist in lidarr_artists)
        existing_names = set(artist['artistName'].lower() for artist in lidarr_artists)
        
        self.logger.info(f"Retrieved {len(lidarr_artists)} existing artists from Lidarr")
        
        # Get Import List Exclusions
        self.logger.info("Fetching Import List Exclusions from Lidarr...")
        excluded_mbids = await self.lidarr.get_import_list_exclusions()
        self.logger.info(f"Retrieved {len(excluded_mbids)} Import List Exclusions")
        
        return existing_mbids, existing_names, excluded_mbids
    
    def filter_artist_candidate(self, artist_mbid: str, artist_name: str, 
                               existing_mbids: Set[str], existing_names: Set[str], 
                               excluded_mbids: Set[str]) -> Tuple[bool, str]:
        """
        Filter individual artist candidate against Lidarr state and exclusions
        
        Args:
            artist_mbid: Artist MusicBrainz ID
            artist_name: Artist name
            existing_mbids: Set of MBIDs already in Lidarr
            existing_names: Set of artist names already in Lidarr (lowercase)
            excluded_mbids: Set of MBIDs in Import List Exclusions
            
        Returns:
            Tuple of (should_include: bool, reason: str)
        """
        # Check if already in Lidarr (by MBID)
        if artist_mbid and artist_mbid in existing_mbids:
            return False, "already_in_lidarr_mbid"
        
        # Check if already in Lidarr (by name)
        if artist_name.lower() in existing_names:
            return False, "already_in_lidarr_name"
        
        # Check if in Import List Exclusions
        if artist_mbid and artist_mbid in excluded_mbids:
            return False, "in_exclusions"
        
        return True, "valid"
    
    def apply_random_sampling(self, candidates: List[Dict[str, Any]], 
                             limit: int, command_name: str) -> Tuple[List[Dict[str, Any]], int, bool]:
        """
        Apply random sampling to candidate list for variety
        
        Args:
            candidates: List of artist candidates
            limit: Maximum number to return (0 = no limit)
            command_name: Name of calling command for logging
            
        Returns:
            Tuple of (sampled_artists, limited_count, random_sampling_applied)
        """
        if limit <= 0 or len(candidates) <= limit:
            return candidates, 0, False
        
        # Apply random sampling for variety
        random.shuffle(candidates)
        sampled = candidates[:limit]
        limited_count = len(candidates) - len(sampled)
        
        self.logger.info(f"Applied random sampling for {command_name}: {len(sampled)} of {len(candidates)} artists (variety boost)")
        
        return sampled, limited_count, True
    
    async def process_artists_through_musicbrainz(self, artists_without_mbids: List[Dict[str, Any]], 
                                                 existing_mbids: Set[str], existing_names: Set[str],
                                                 excluded_mbids: Set[str], 
                                                 source_name: str) -> List[Dict[str, Any]]:
        """
        Process artists without MBIDs through MusicBrainz fuzzy matching with filtering
        
        Args:
            artists_without_mbids: List of artists missing MBIDs
            existing_mbids: Set of MBIDs already in Lidarr
            existing_names: Set of artist names already in Lidarr
            excluded_mbids: Set of excluded MBIDs
            source_name: Source identifier for recovered artists
            
        Returns:
            List of recovered artist dictionaries
        """
        if not self.config.MUSICBRAINZ_ENABLED or not self.musicbrainz:
            return []
        
        recovered_artists = []
        processed_count = 0
        success_count = 0
        excluded_during_recovery = 0
        
        # Group by name to avoid duplicate lookups
        unique_artists = {}
        for artist in artists_without_mbids:
            name = artist.get('name', artist.get('artistName', ''))
            if name and name not in unique_artists:
                unique_artists[name] = artist
        
        self.logger.info(f"Processing {len(unique_artists)} unique artist names through MusicBrainz...")
        
        for artist_name, artist_data in unique_artists.items():
            try:
                # Fuzzy search in MusicBrainz
                mb_result = await self.musicbrainz.fuzzy_search_artist(artist_name)
                processed_count += 1
                
                if mb_result:
                    mbid = mb_result['mbid']
                    similarity = mb_result['similarity_score']
                    mb_name = mb_result['name']
                    
                    # Apply the same filtering logic
                    should_include, reason = self.filter_artist_candidate(
                        mbid, mb_name, existing_mbids, existing_names, excluded_mbids
                    )
                    
                    if not should_include:
                        if reason == "in_exclusions":
                            excluded_during_recovery += 1
                        self.logger.debug(f"MusicBrainz match for '{artist_name}' filtered: {reason}")
                        continue
                    
                    # Check for duplicates in this recovery session
                    if any(ra['MusicBrainzId'] == mbid for ra in recovered_artists):
                        self.logger.debug(f"MusicBrainz match for '{artist_name}' already recovered: {mbid}")
                        continue
                    
                    success_count += 1
                    
                    # Create recovered artist entry
                    recovered_artist = {
                        "MusicBrainzId": mbid,
                        "ArtistName": mb_name,
                        "source": source_name,
                        "musicbrainz_similarity": f"{similarity:.3f}",
                        "recoveredVia": "musicbrainz_fuzzy_match",
                        "original_name": artist_name
                    }
                    
                    # Add source-specific fields if available
                    if 'track_title' in artist_data:
                        recovered_artist['track_title'] = artist_data['track_title']
                    if 'source_artist' in artist_data:
                        recovered_artist['similarArtistTo'] = artist_data['source_artist']
                        recovered_artist['lastfmMatchScore'] = artist_data.get('match', '0.0')
                    
                    recovered_artists.append(recovered_artist)
                    
                    self.logger.debug(f"Recovered '{artist_name}' -> '{mb_name}' (MBID: {mbid}, similarity: {similarity:.3f})")
                else:
                    self.logger.debug(f"No MusicBrainz match found for '{artist_name}'")
                    
            except Exception as e:
                self.logger.error(f"Error processing '{artist_name}' through MusicBrainz: {e}")
        
        # Log recovery results
        self.logger.info(f"MusicBrainz processing complete: {success_count}/{processed_count} artists recovered")
        if excluded_during_recovery > 0:
            self.logger.info(f"✅ Blocked {excluded_during_recovery} excluded artists during MusicBrainz recovery")
        
        return recovered_artists
    
    def deduplicate_by_mbid(self, artists: List[Dict[str, Any]], 
                           score_field: str = 'match') -> List[Dict[str, Any]]:
        """
        Remove duplicate artists by MBID, keeping the one with highest score
        
        Args:
            artists: List of artist dictionaries
            score_field: Field name containing match score
            
        Returns:
            Deduplicated list of artists
        """
        seen_mbids = {}
        
        # Determine MBID field name
        if artists:
            mbid_field = 'MusicBrainzId' if 'MusicBrainzId' in artists[0] else 'mbid'
        else:
            mbid_field = 'mbid'
        
        for artist in artists:
            mbid = artist.get(mbid_field)
            if not mbid:
                continue
                
            if mbid not in seen_mbids:
                seen_mbids[mbid] = artist
            else:
                # Keep the one with higher score
                try:
                    current_score = float(artist.get(score_field, 0))
                    existing_score = float(seen_mbids[mbid].get(score_field, 0))
                    if current_score > existing_score:
                        seen_mbids[mbid] = artist
                except (ValueError, TypeError):
                    # If scores can't be compared, keep the first one
                    pass
        
        return list(seen_mbids.values())
    
    def log_filtering_statistics(self, command_name: str, stats: Dict[str, Any]):
        """
        Log standardized filtering statistics
        
        Args:
            command_name: Name of the discovery command
            stats: Dictionary containing filtering statistics
        """
        self.logger.info("=" * 70)
        self.logger.info(f"{command_name.upper()} FILTERING STATISTICS")
        self.logger.info("=" * 70)
        
        # Source data
        if 'total_candidates' in stats:
            self.logger.info(f"Total Candidates:                     {stats['total_candidates']:,}")
        if 'exclusions_count' in stats:
            self.logger.info(f"Import List Exclusions:               {stats['exclusions_count']:,}")
        
        # Filtering breakdown
        if 'filtered_already_in_lidarr' in stats:
            self.logger.info(f"Filtered - Already in Lidarr:         {stats['filtered_already_in_lidarr']:,}")
        if 'filtered_in_exclusions' in stats:
            self.logger.info(f"Filtered - Import List Exclusions:    {stats['filtered_in_exclusions']:,}")
        if 'filtered_low_score' in stats:
            self.logger.info(f"Filtered - Low Match Score:           {stats['filtered_low_score']:,}")
        
        # Results
        if 'valid_candidates' in stats:
            self.logger.info(f"Valid Candidates:                     {stats['valid_candidates']:,}")
        if 'musicbrainz_recovered' in stats:
            self.logger.info(f"MusicBrainz Recovered:                {stats['musicbrainz_recovered']:,}")
        if 'final_count' in stats:
            self.logger.info(f"Final Output Count:                   {stats['final_count']:,}")
        
        # Sampling info
        if stats.get('random_sampling_applied'):
            limited = stats.get('limited_count', 0)
            self.logger.info(f"Random Sampling Applied:              {limited:,} artists limited")
        
        # Impact analysis
        exclusions_blocked = stats.get('filtered_in_exclusions', 0)
        if exclusions_blocked > 0:
            total = stats.get('total_candidates', 1)
            impact = (exclusions_blocked / total * 100)
            self.logger.info(f"Exclusion Filter Impact:              {impact:.1f}% of candidates blocked")
            self.logger.info(f"✅ Exclusion filtering prevented {exclusions_blocked} unwanted recommendations")
        
        if stats.get('random_sampling_applied'):
            self.logger.info(f"✅ Random sampling applied for discovery variety")
        
        # Overall success message
        final_count = stats.get('final_count', 0)
        total_candidates = stats.get('total_candidates', 0)
        
        if final_count > 0:
            self.logger.info(f"🎯 SUCCESS: {final_count} new artists discovered and ready for import")
        elif total_candidates > 0:
            filtered_total = stats.get('filtered_already_in_lidarr', 0) + stats.get('filtered_in_exclusions', 0)
            if filtered_total == total_candidates:
                self.logger.info(f"🎯 SUCCESS: All {total_candidates} discovered artists are already in Lidarr or excluded")
                self.logger.info("   This indicates your music library is well-curated!")
            else:
                self.logger.info(f"🎯 SUCCESS: Discovery completed - no new artists found from {total_candidates} candidates")
        else:
            self.logger.info("🎯 SUCCESS: Discovery completed successfully")
        
        self.logger.info("=" * 70)
    
    def create_artist_entry(self, mbid: str, name: str, source: str, **kwargs) -> Dict[str, Any]:
        """
        Create standardized artist entry for output
        
        Args:
            mbid: MusicBrainz ID
            name: Artist name
            source: Source identifier
            **kwargs: Additional fields to include
            
        Returns:
            Standardized artist dictionary
        """
        entry = {
            "MusicBrainzId": mbid,
            "ArtistName": name,
            "source": source
        }
        
        # Add optional fields
        for key, value in kwargs.items():
            if value is not None:
                entry[key] = value
        
        return entry
    
    async def cleanup_expired_cache(self):
        """Clean up expired cache entries"""
        if self.config.CACHE_ENABLED:
            from cache_manager import get_cache_manager
            cache = get_cache_manager()
            expired_count = cache.cleanup_expired()
            if expired_count > 0:
                self.logger.info(f"Cleaned up {expired_count} expired cache entries")


class FilteringStats:
    """Helper class to track filtering statistics"""
    
    def __init__(self):
        self.total_candidates = 0
        self.exclusions_count = 0
        self.filtered_already_in_lidarr = 0
        self.filtered_in_exclusions = 0
        self.filtered_low_score = 0
        self.valid_candidates = 0
        self.musicbrainz_recovered = 0
        self.final_count = 0
        self.limited_count = 0
        self.random_sampling_applied = False
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for logging"""
        return {
            'total_candidates': self.total_candidates,
            'exclusions_count': self.exclusions_count,
            'filtered_already_in_lidarr': self.filtered_already_in_lidarr,
            'filtered_in_exclusions': self.filtered_in_exclusions,
            'filtered_low_score': self.filtered_low_score,
            'valid_candidates': self.valid_candidates,
            'musicbrainz_recovered': self.musicbrainz_recovered,
            'final_count': self.final_count,
            'limited_count': self.limited_count,
            'random_sampling_applied': self.random_sampling_applied
        }
