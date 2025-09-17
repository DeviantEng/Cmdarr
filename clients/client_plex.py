#!/usr/bin/env python3
"""
Plex API Client with SQLite caching and Library Cache optimization
Refactored to use BaseAPIClient for reduced code duplication
Enhanced with dramatic performance improvements via library caching
OPTIMIZED: Reduced memory usage by storing only essential track data
"""

import requests
import time
import logging
import xml.etree.ElementTree as ET
from typing import List, Dict, Any, Optional, Tuple
from urllib.parse import quote_plus
from cache_manager import get_cache_manager
from .client_base import BaseAPIClient
from utils.cache_client import create_cache_client


class PlexClient(BaseAPIClient):
    """Client for Plex Media Server operations with optimized library cache"""
    
    def __init__(self, config):
        # Plex uses synchronous requests, so we'll override the async behavior
        super().__init__(
            config=config,
            client_name='plex',
            base_url=config.PLEX_URL.rstrip("/"),
            rate_limit=1.0,  # Conservative rate limiting
            headers={}
        )
        
        self.token = config.PLEX_TOKEN
        
        # Initialize cache - enable based on library cache setting
        self.cache_enabled = config.get('LIBRARY_CACHE_PLEX_ENABLED', False)
        self.cache = get_cache_manager() if self.cache_enabled else None
        
        # Initialize centralized cache client
        self.cache_client = create_cache_client('plex', config)
        
        # Register with library cache manager for per-client stats if library cache is enabled
        if config.get('LIBRARY_CACHE_PLEX_ENABLED', False):
            self._register_with_cache_manager()
    
    def _register_with_cache_manager(self) -> None:
        """Register this client with the library cache manager for per-client stats"""
        self.cache_client.register_with_cache_manager(self)
    
    def _record_cache_hit(self) -> None:
        """Record a library cache hit"""
        self.cache_client.record_cache_hit()
    
    def _record_cache_miss(self) -> None:
        """Record a library cache miss"""
        self.cache_client.record_cache_miss()
    
    # ==== LIBRARY CACHE INTERFACE METHODS ====
    # Required by LibraryCacheManager for optimization
    
    def get_cache_key(self, library_key: str = None) -> str:
        """Generate cache key for library cache"""
        if library_key:
            return f"plex:{self.base_url}:library:{library_key}"
        else:
            # Default to first music library
            try:
                music_libraries = self.get_music_libraries()
                if music_libraries:
                    default_library_key = music_libraries[0]['key']
                    return f"plex:{self.base_url}:library:{default_library_key}"
                else:
                    return f"plex:{self.base_url}:library:default"
            except:
                return f"plex:{self.base_url}:library:default"
    
    def get_cache_ttl(self) -> int:
        """Get cache TTL in days for library cache"""
        return getattr(self.config, 'LIBRARY_CACHE_TTL_DAYS', 30)
    
    def build_library_cache(self, library_key: str = None) -> Dict[str, Any]:
        """
        Build optimized library cache with minimal memory footprint
        
        Returns cache data with structure:
        {
            "library_key": "2",
            "total_tracks": 45000,
            "tracks": [...],  # Minimal track data only
            "artist_index": {...},  # Direct artist -> rating_keys mapping
            "track_index": {...}   # Direct track title -> rating_keys mapping
        }
        """
        try:
            # Get target library
            if not library_key:
                music_libraries = self.get_music_libraries()
                if not music_libraries:
                    self.logger.error("No music libraries found for cache building")
                    return {}
                library_key = music_libraries[0]['key']
                self.logger.info(f"Using default music library: {music_libraries[0]['title']}")
            
            self.logger.info(f"Building optimized library cache for library {library_key}...")
            start_time = time.time()
            
            # Fetch all tracks from library with minimal data
            all_tracks = self._fetch_minimal_library_tracks(library_key)
            
            if not all_tracks:
                self.logger.warning(f"No tracks found in library {library_key}")
                return {}
            
            # Build optimized cache structure
            cache_data = {
                "library_key": library_key,
                "total_tracks": len(all_tracks),
                "tracks": all_tracks,
                "artist_index": {},
                "track_index": {},
                "built_at": time.time()
            }
            
            # Create optimized search indexes (direct mappings)
            self._build_optimized_indexes(cache_data)
            
            build_time = time.time() - start_time
            
            # Estimate memory usage
            estimated_mb = self._estimate_cache_memory(cache_data)
            self.logger.info(f"Built optimized library cache: {len(all_tracks):,} tracks in {build_time:.1f}s (~{estimated_mb}MB)")
            
            return cache_data
            
        except Exception as e:
            self.logger.error(f"Failed to build library cache: {e}")
            return {}
    
    def _fetch_minimal_library_tracks(self, library_key: str) -> List[Dict[str, Any]]:
        """Fetch all tracks from a library with minimal data for memory optimization"""
        all_tracks = []
        container_start = 0
        container_size = 1000  # Larger batches for efficiency
        
        while True:
            try:
                params = {
                    "type": 10,  # Track type
                    "X-Plex-Container-Start": container_start,
                    "X-Plex-Container-Size": container_size
                }
                
                results = self._get(f"/library/sections/{library_key}/all", params=params)
                media_container = results.get("MediaContainer", {})
                tracks = media_container.get("Metadata", [])
                
                if not tracks:
                    break
                
                # Extract ONLY essential track data for minimal memory usage
                for track in tracks:
                    # Store only what's absolutely needed for matching
                    track_data = {
                        "key": track.get("ratingKey"),  # Shorter field name
                        "title": (track.get("title", "") or "").lower().strip(),
                        "artist": (track.get("grandparentTitle", "") or "").lower().strip(),
                        "album": (track.get("parentTitle", "") or "").lower().strip()[:50],  # Truncate long album names
                        "duration": track.get("duration", 0)
                    }
                    
                    # Skip tracks with missing essential data
                    if track_data["key"] and track_data["title"] and track_data["artist"]:
                        all_tracks.append(track_data)
                
                # Progress logging every 25k tracks
                if len(all_tracks) % 25000 == 0 and len(all_tracks) > 0:
                    self.logger.debug(f"Fetched {len(all_tracks):,} tracks so far...")
                
                # Check if we got less than requested (end of results)
                if len(tracks) < container_size:
                    break
                
                container_start += container_size
                
            except Exception as e:
                self.logger.error(f"Error fetching tracks at position {container_start}: {e}")
                break
        
        self.logger.info(f"Fetched {len(all_tracks):,} valid tracks from library")
        return all_tracks
    
    def _build_optimized_indexes(self, cache_data: Dict[str, Any]) -> None:
        """Build optimized search indexes for ultra-fast lookups"""
        tracks = cache_data["tracks"]
        artist_index = {}
        track_index = {}
        
        for track in tracks:
            rating_key = track["key"]
            artist = track["artist"]
            title = track["title"]
            
            # Direct artist mapping for fastest lookup
            if artist:
                if artist not in artist_index:
                    artist_index[artist] = []
                artist_index[artist].append(rating_key)
            
            # Direct track title mapping
            if title:
                if title not in track_index:
                    track_index[title] = []
                track_index[title].append(rating_key)
        
        cache_data["artist_index"] = artist_index
        cache_data["track_index"] = track_index
        
        self.logger.debug(f"Built optimized indexes: {len(artist_index):,} artists, {len(track_index):,} track titles")
    
    def _estimate_cache_memory(self, cache_data: Dict[str, Any]) -> float:
        """Estimate memory usage of optimized cache in MB"""
        try:
            # More accurate estimation for optimized structure
            track_count = len(cache_data.get("tracks", []))
            
            # Optimized track: ~60 bytes average (key=8, title=20, artist=15, album=15, duration=2)
            tracks_mb = (track_count * 60) / (1024 * 1024)
            
            # Indexes: roughly 40% overhead for artist/track mappings
            indexes_mb = tracks_mb * 0.4
            
            # Metadata and structure overhead
            overhead_mb = 2.0
            
            total_mb = tracks_mb + indexes_mb + overhead_mb
            return round(total_mb, 1)
            
        except:
            # Fallback estimation
            track_count = len(cache_data.get("tracks", []))
            estimated_mb = (track_count * 80) / (1024 * 1024)  # Conservative estimate
            return round(estimated_mb, 1)
    
    def process_cached_library(self, cached_data: Dict[str, Any]) -> Dict[str, Any]:
        """Process cached library data for use (no transformation needed for Plex)"""
        return cached_data
    
    def search_cached_library(self, track_name: str, artist_name: str, cached_data: Dict[str, Any]) -> Optional[str]:
        """
        Ultra-fast search in optimized cached library data
        
        Returns:
            Track ratingKey if found, None otherwise
        """
        if not cached_data or "tracks" not in cached_data:
            return None
        
        tracks = cached_data["tracks"]
        artist_index = cached_data.get("artist_index", {})
        track_index = cached_data.get("track_index", {})
        
        track_lower = track_name.lower().strip()
        artist_lower = artist_name.lower().strip()
        
        # Strategy 1: Direct index lookups (fastest)
        candidate_keys = set()
        
        # Get candidates by artist (direct lookup)
        if artist_lower in artist_index:
            candidate_keys.update(artist_index[artist_lower])
        
        # Get candidates by track title (direct lookup)
        if track_lower in track_index:
            track_candidates = set(track_index[track_lower])
            
            # If we have both artist and track matches, use intersection for best results
            if candidate_keys:
                candidate_keys = candidate_keys.intersection(track_candidates)
            else:
                candidate_keys = track_candidates
        
        # Strategy 2: If direct lookup found candidates, score them
        if candidate_keys:
            best_match = None
            best_score = 0
            
            for track in tracks:
                if track["key"] in candidate_keys:
                    score = self._score_track_match_optimized(track, track_lower, artist_lower)
                    if score > best_score:
                        best_score = score
                        best_match = track["key"]
            
            if best_match and best_score >= 100:  # Require high confidence for direct matches
                return best_match
        
        # Strategy 3: Fuzzy matching fallback (only if no direct matches)
        if not candidate_keys:
            best_match = None
            best_score = 0
            
            # Sample-based fuzzy search to avoid full scan
            sample_size = min(5000, len(tracks))  # Limit fuzzy search scope
            track_sample = tracks[:sample_size] if len(tracks) > sample_size else tracks
            
            for track in track_sample:
                score = self._score_track_match_optimized(track, track_lower, artist_lower)
                if score > best_score:
                    best_score = score
                    best_match = track["key"]
            
            if best_match and best_score >= 120:  # Higher threshold for fuzzy matches
                return best_match
        
        return None
    
    def _score_track_match_optimized(self, track: Dict[str, Any], target_track: str, target_artist: str) -> int:
        """
        Optimized track matching score using minimal track data
        
        Returns score from 0-200 (higher is better)
        """
        score = 0
        
        plex_track = track.get("title", "")
        plex_artist = track.get("artist", "")
        
        # Score track title match
        if plex_track == target_track:
            score += 100  # Exact match
        elif target_track in plex_track or plex_track in target_track:
            score += 70   # Partial match
        elif self._fuzzy_match(plex_track, target_track):
            score += 50   # Fuzzy match
        
        # Score artist name match
        if plex_artist == target_artist:
            score += 100  # Exact match
        elif target_artist in plex_artist or plex_artist in target_artist:
            score += 70   # Partial match
        elif self._fuzzy_match(plex_artist, target_artist):
            score += 50   # Fuzzy match
        
        return score
    
    def verify_track_exists(self, rating_key: str) -> bool:
        """
        Verify that a track still exists in Plex (for cache validation)
        
        Returns:
            True if track exists, False otherwise
        """
        try:
            result = self._get(f"/library/metadata/{rating_key}")
            media_container = result.get("MediaContainer", {})
            metadata = media_container.get("Metadata", [])
            return len(metadata) > 0
        except Exception:
            return False
    
    # ==== ENHANCED SEARCH METHODS ====
    
    def search_for_track(self, track_name, artist_name, mbids=None, cached_data=None):
        """
        Search for a track by name and artist with cache-first approach
        Enhanced with optimized library cache for dramatic performance improvements
        """
        # Check if library cache is enabled for this client
        library_cache_enabled = self.config.get('LIBRARY_CACHE_PLEX_ENABLED', False)
        
        # Try cached search first if available and library cache is enabled
        if cached_data and library_cache_enabled:
            cached_result = self.search_cached_library(track_name, artist_name, cached_data)
            if cached_result:
                self.logger.debug(f"Cache hit: {artist_name} - {track_name}")
                # Record cache hit
                self._record_cache_hit()
                return cached_result
        
        # Fallback to live API search (original implementation)
        if library_cache_enabled:
            self.logger.debug(f"Cache miss, using live API search: {artist_name} - {track_name}")
            # Record cache miss
            self._record_cache_miss()
        else:
            self.logger.debug(f"Using live API search: {artist_name} - {track_name}")
        
        return self._search_for_track_live(track_name, artist_name, mbids)
    
    def _search_for_track_live(self, track_name, artist_name, mbids=None):
        """
        Original live API search implementation (fallback when cache unavailable)
        """
        music_libraries = self.get_music_libraries()
        if not music_libraries:
            self.logger.warning("No music libraries found")
            return None

        # Try different search strategies
        search_queries = [
            f"{artist_name} {track_name}",      # Artist + Track
            f"{track_name} {artist_name}",      # Track + Artist
            track_name,                         # Just track name
            artist_name,                        # Just artist name
            # Add partial searches for better matching
            " ".join(track_name.split()[:3]),   # First 3 words of track
            " ".join(track_name.split()[:2]),   # First 2 words of track
            " ".join(track_name.split()[-3:]),  # Last 3 words of track
            " ".join(track_name.split()[1:4]),  # Middle words of track
        ]

        best_match = None
        best_score = 0

        for library in music_libraries:
            library_key = library["key"]

            for query in search_queries:
                tracks = self.search_tracks_in_library(library_key, query)

                for track in tracks:
                    score = self._score_track_match(track, track_name, artist_name, mbids)

                    if score > best_score:
                        best_score = score
                        best_match = track

        if best_match and best_score >= 50:  # Minimum threshold for a match
            return best_match["ratingKey"]

        return None
    
    def sync_playlist(self, title: str, tracks: List[Dict[str, Any]], summary: str = "", **kwargs) -> Dict[str, Any]:
        """
        Sync a playlist to Plex with optimized library cache
        
        Args:
            title: Playlist title
            tracks: List of track dictionaries with 'artist', 'album', 'track' keys
            summary: Playlist description
            **kwargs: Additional parameters (library_key, update_existing, library_cache_manager)
            
        Returns:
            Dict with keys: success, action, total_tracks, found_tracks, message
        """
        try:
            self.logger.info(f"Syncing playlist '{title}' with {len(tracks)} tracks")

            # Extract kwargs
            library_key = kwargs.get('library_key')
            update_existing = kwargs.get('update_existing', True)
            library_cache_manager = kwargs.get('library_cache_manager')

            # Get optimized library cache if available
            cached_data = None
            if hasattr(self, '_cached_library') and self._cached_library:
                # Use cached library passed from playlist sync command
                cached_data = self._cached_library
                track_count = cached_data.get('total_tracks', 0)
                self.logger.info(f"Using cached library with {track_count:,} tracks")
            elif library_cache_manager:
                cached_data = library_cache_manager.get_library_cache('plex', library_key)
                if cached_data:
                    track_count = cached_data.get('total_tracks', 0)
                    self.logger.info(f"Using optimized library cache with {track_count:,} tracks")
                else:
                    self.logger.warning("Library cache not available, falling back to live API searches")
            else:
                self.logger.warning("No library cache available, falling back to live API searches")

            # Find tracks with progress tracking
            found_track_keys = []
            failed_matches = []
            processed = 0

            for i, track in enumerate(tracks):
                artist = track.get('artist', '')
                track_name = track.get('track', '')

                if not artist or not track_name:
                    continue

                processed += 1
                progress = f"[{processed}/{len(tracks)}]"

                # Search using cache-optimized method
                rating_key = self.search_for_track(track_name, artist, cached_data=cached_data)

                if rating_key:
                    found_track_keys.append(rating_key)
                    self.logger.debug(f"{progress} ✅ {artist} - {track_name}")
                else:
                    failed_matches.append(f"{artist} - {track_name}")
                    self.logger.debug(f"{progress} ❌ {artist} - {track_name}")

            tracks_found = len(found_track_keys)
            tracks_total = len(tracks)

            self.logger.info(f"Track matching results: {tracks_found}/{tracks_total} found")

            # Verify cache freshness if many tracks weren't found
            if library_cache_manager and cached_data and tracks_found < tracks_total * 0.6:
                self.logger.info("Low match rate detected, verifying cache freshness...")
                sample_keys = found_track_keys[:5] if found_track_keys else []
                library_cache_manager.verify_and_refresh_cache('plex', library_key, sample_keys)

            # Handle empty playlist case
            if not found_track_keys:
                self.logger.warning(f"No tracks found in Plex library for playlist '{title}'")
                
                cleanup_empty = getattr(self.config, 'PLAYLIST_SYNC_LISTENBRAINZ_CURATED_CLEANUP', True)
                
                if cleanup_empty:
                    self.logger.info(f"Empty playlist cleanup enabled - will not create empty playlist '{title}'")
                    return {
                        'success': True,
                        'action': 'skipped_empty',
                        'total_tracks': tracks_total,
                        'found_tracks': 0,
                        'message': f"Skipped creating empty playlist '{title}'"
                    }
                else:
                    self.logger.info(f"Empty playlist cleanup disabled - skipping creation of empty playlist '{title}'")
                    return {
                        'success': True,
                        'action': 'skipped_empty',
                        'total_tracks': tracks_total,
                        'found_tracks': 0,
                        'message': f"Skipped creating empty playlist '{title}'"
                    }

            # Create/update playlist using proven method
            success = self.create_or_update_playlist(title, found_track_keys, summary)
            
            if success:
                match_rate = (tracks_found / tracks_total * 100) if tracks_total > 0 else 0
                self.logger.info(f"Successfully synced playlist '{title}': {tracks_found}/{tracks_total} tracks ({match_rate:.1f}% success rate)")
                return {
                    'success': True,
                    'action': 'synced',
                    'total_tracks': tracks_total,
                    'found_tracks': tracks_found,
                    'message': f"Successfully synced playlist '{title}' with {tracks_found} tracks"
                }
            else:
                self.logger.error(f"Failed to sync playlist '{title}'")
                return {
                    'success': False,
                    'action': 'failed',
                    'total_tracks': tracks_total,
                    'found_tracks': tracks_found,
                    'message': f"Failed to sync playlist '{title}'"
                }

        except Exception as e:
            self.logger.error(f"Error syncing playlist '{title}': {e}")
            return {
                'success': False,
                'action': 'error',
                'total_tracks': len(tracks),
                'found_tracks': 0,
                'message': f"Error syncing playlist '{title}': {str(e)}"
            }
    
    # ==== ORIGINAL PLEX API METHODS ====
    # Keeping all existing proven functionality
    
    def _get_cache_key(self, operation: str, *args) -> str:
        """Generate cache key for Plex requests"""
        key_parts = [operation] + [str(arg) for arg in args]
        return ":".join(key_parts)
    
    def _get(self, path, params=None):
        """GET request to Plex API - copied from proven working implementation"""
        if params is None:
            params = {}
        params["X-Plex-Token"] = self.token
        url = f"{self.base_url}{path}"
        headers = {
            "Accept": "application/json",
        }
        
        try:
            r = requests.get(url, params=params, headers=headers, timeout=self.config.PLEX_TIMEOUT)
            r.raise_for_status()

            # Handle both XML and JSON responses
            content_type = r.headers.get('content-type', '').lower()
            if 'xml' in content_type:
                return self._parse_xml_response(r.text)
            elif r.text.strip():
                try:
                    return r.json()
                except ValueError:
                    self.logger.warning(f"Non-JSON response from {path}: {r.text[:100]}")
                    return {}
            else:
                self.logger.warning(f"Empty response from {path}")
                return {}
                
        except requests.exceptions.RequestException as e:
            self.logger.error(f"Request failed for {path}: {e}")
            raise

    def _post(self, path, params=None, data=None):
        """POST request to Plex API - copied from proven working implementation"""
        if params is None:
            params = {}
        params["X-Plex-Token"] = self.token
        url = f"{self.base_url}{path}"
        headers = {
            "Accept": "application/json",
        }
        
        try:
            r = requests.post(url, params=params, data=data, headers=headers, timeout=self.config.PLEX_TIMEOUT)
            r.raise_for_status()

            # Handle both XML and JSON responses
            content_type = r.headers.get('content-type', '').lower()
            if 'xml' in content_type:
                return self._parse_xml_response(r.text)
            elif r.text.strip():
                try:
                    return r.json()
                except ValueError:
                    self.logger.warning(f"Non-JSON response from {path}: {r.text[:100]}")
                    return {}
            else:
                self.logger.warning(f"Empty response from {path}")
                return {}
                
        except requests.exceptions.RequestException as e:
            self.logger.error(f"POST request failed for {path}: {e}")
            raise

    def _put(self, path, params=None, data=None):
        """PUT request to Plex API - copied from proven working implementation"""
        if params is None:
            params = {}
        params["X-Plex-Token"] = self.token
        url = f"{self.base_url}{path}"
        headers = {
            "Accept": "application/json",
        }
        
        try:
            r = requests.put(url, params=params, data=data, headers=headers, timeout=self.config.PLEX_TIMEOUT)
            r.raise_for_status()

            # Handle both XML and JSON responses
            content_type = r.headers.get('content-type', '').lower()
            if 'xml' in content_type:
                return self._parse_xml_response(r.text)
            elif r.text.strip():
                try:
                    return r.json()
                except ValueError:
                    return {}
            else:
                return {}
                
        except requests.exceptions.RequestException as e:
            self.logger.error(f"PUT request failed for {path}: {e}")
            raise

    def _delete(self, path, params=None):
        """DELETE request to Plex API - copied from proven working implementation"""
        if params is None:
            params = {}
        params["X-Plex-Token"] = self.token
        url = f"{self.base_url}{path}"
        headers = {
            "Accept": "application/json",
        }
        
        try:
            r = requests.delete(url, params=params, headers=headers, timeout=self.config.PLEX_TIMEOUT)
            r.raise_for_status()
            return {} if not r.content else {}
            
        except requests.exceptions.RequestException as e:
            self.logger.error(f"DELETE request failed for {path}: {e}")
            raise

    def _parse_xml_response(self, xml_text):
        """Parse XML response and convert to JSON-like structure - copied from proven working implementation"""
        try:
            root = ET.fromstring(xml_text)
            result = {"MediaContainer": self._xml_element_to_dict(root)}
            return result
        except ET.ParseError as e:
            self.logger.error(f"Error parsing XML: {e}")
            return {}

    def _xml_element_to_dict(self, element):
        """Convert XML element to dictionary - copied from proven working implementation"""
        result = {}

        # Add attributes
        if element.attrib:
            result.update(element.attrib)

        # Handle child elements
        children = list(element)
        if children:
            child_dict = {}
            for child in children:
                child_data = self._xml_element_to_dict(child)
                if child.tag in child_dict:
                    # Multiple children with same tag - make it a list
                    if not isinstance(child_dict[child.tag], list):
                        child_dict[child.tag] = [child_dict[child.tag]]
                    child_dict[child.tag].append(child_data)
                else:
                    child_dict[child.tag] = child_data

            # For MediaContainer, put child elements in appropriate arrays for compatibility
            if element.tag == "MediaContainer":
                metadata_items = []
                directory_items = []

                for child in children:
                    child_data = self._xml_element_to_dict(child)
                    if child.tag in ["Playlist", "Track", "Artist", "Album", "Video"]:
                        metadata_items.append(child_data)
                    elif child.tag == "Directory":
                        directory_items.append(child_data)
                    else:
                        # Other child elements go directly into result
                        if child.tag in child_dict:
                            if not isinstance(result.get(child.tag), list):
                                result[child.tag] = [result.get(child.tag, child_dict[child.tag])]
                            result[child.tag].append(child_data)
                        else:
                            result[child.tag] = child_data

                if metadata_items:
                    result["Metadata"] = metadata_items
                if directory_items:
                    result["Directory"] = directory_items
                    # Also add directories as Metadata for compatibility with library sections
                    if not metadata_items:
                        result["Metadata"] = directory_items
            else:
                result.update(child_dict)

        # Add text content if present
        if element.text and element.text.strip():
            if children:
                result["text"] = element.text.strip()
            else:
                return element.text.strip()

        return result

    def get_music_libraries(self):
        """Get all music library sections - copied from proven working implementation"""
        try:
            # Check cache first
            cache_key = self._get_cache_key("music_libraries")
            if self.cache_enabled and self.cache:
                cached_result = self.cache.get(cache_key, 'plex')
                if cached_result is not None:
                    self.logger.debug("Cache hit for music libraries")
                    return cached_result
            
            results = self._get("/library/sections")
            media_container = results.get("MediaContainer", {})

            # Handle both XML and JSON response formats
            # In XML, library sections are Directory elements
            sections = media_container.get("Directory", [])
            if not sections:
                # Fallback to Metadata for JSON responses
                sections = media_container.get("Metadata", [])

            music_sections = []
            for section in sections:
                section_type = section.get("type", "")
                section_title = section.get("title", "")
                section_key = section.get("key", "")

                # Check for music/audio library types
                # 'artist' type indicates a music library in Plex
                if section_type in ("artist", "music", "audio"):
                    music_sections.append({
                        "key": section_key,
                        "title": section_title,
                        "type": section_type
                    })

            # Cache the result
            if self.cache_enabled and self.cache:
                self.cache.set(cache_key, 'plex', music_sections, self.config.CACHE_PLEX_TTL_DAYS)

            self.logger.debug(f"Found {len(music_sections)} music libraries")
            return music_sections

        except Exception as e:
            self.logger.error(f"Error getting music libraries: {e}")
            return []

    def search_tracks_in_library(self, library_key, query):
        """Search for tracks in a specific library section - copied from proven working implementation"""
        params = {
            "type": 10,  # Track type
            "query": query
        }

        try:
            results = self._get(f"/library/sections/{library_key}/search", params=params)
            media_container = results.get("MediaContainer", {})
            tracks = media_container.get("Metadata", [])
            return tracks
        except Exception as e:
            self.logger.error(f"Error searching library {library_key}: {e}")
            return []

    def _score_track_match(self, track, target_track_name, target_artist_name, mbids=None):
        """
        Score how well a Plex track matches our target track.
        Copied from proven working implementation.
        Returns a score from 0-200 (higher is better).
        """
        score = 0

        # Get track info from Plex metadata
        plex_track_title = track.get("title", "").lower()
        plex_artist_name = track.get("grandparentTitle", "").lower()  # Artist is grandparent
        plex_album_name = track.get("parentTitle", "").lower()        # Album is parent

        target_track_lower = target_track_name.lower()
        target_artist_lower = target_artist_name.lower()

        # Score track title match
        if plex_track_title == target_track_lower:
            score += 100  # Exact match
        elif target_track_lower in plex_track_title or plex_track_title in target_track_lower:
            score += 70   # Partial match
        elif self._fuzzy_match(plex_track_title, target_track_lower):
            score += 50   # Fuzzy match

        # Score artist name match
        if plex_artist_name == target_artist_lower:
            score += 100  # Exact match
        elif target_artist_lower in plex_artist_name or plex_artist_name in target_artist_lower:
            score += 70   # Partial match
        elif self._fuzzy_match(plex_artist_name, target_artist_lower):
            score += 50   # Fuzzy match

        # Bonus for MusicBrainz ID match if available
        if mbids:
            plex_guid = track.get("guid", "").lower()
            for mbid in mbids:
                if mbid.lower() in plex_guid:
                    score += 50  # MusicBrainz ID bonus
                    break

        return score

    def _fuzzy_match(self, str1, str2, threshold=0.8):
        """
        Simple fuzzy string matching using character overlap.
        Copied from proven working implementation.
        Returns True if strings are similar enough.
        """
        if not str1 or not str2:
            return False

        # Remove common words that might cause false matches
        common_words = ['the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with', 'by', 'from', 'up', 'about', 'into', 'over', 'after']

        def clean_string(s):
            words = s.split()
            return ' '.join([w for w in words if w not in common_words])

        clean_str1 = clean_string(str1)
        clean_str2 = clean_string(str2)

        # Character overlap ratio
        set1 = set(clean_str1.replace(' ', ''))
        set2 = set(clean_str2.replace(' ', ''))

        if not set1 or not set2:
            return False

        overlap = len(set1.intersection(set2))
        total = len(set1.union(set2))

        return (overlap / total) >= threshold

    # PLAYLIST METHODS - Copied exactly from proven working implementation

    def find_playlist_by_name(self, playlist_name):
        """Find a playlist by name. Returns playlist metadata if found, None otherwise."""
        try:
            results = self._get("/playlists")
            media_container = results.get("MediaContainer", {})
            playlists = media_container.get("Metadata", [])

            for playlist in playlists:
                if playlist.get("title", "").lower() == playlist_name.lower():
                    return playlist

            return None
        except Exception as e:
            self.logger.error(f"Error finding playlist '{playlist_name}': {e}")
            return None

    def create_playlist(self, title, track_rating_keys, summary=""):
        """
        Create a new playlist with the given tracks.
        Uses hybrid approach - create with 1 track, then add the rest.
        COPIED EXACTLY from proven working implementation.
        """
        try:
            if not track_rating_keys:
                self.logger.warning("No tracks provided for playlist creation")
                return False

            self.logger.info(f"Creating playlist '{title}' using hybrid method (1 track + add remaining)...")

            # Step 1: Create playlist with first track only
            first_track = track_rating_keys[0]
            uri = f"library://{self.base_url.split('://')[1]}/item/library%2Fmetadata%2F{first_track}"

            params = {
                "X-Plex-Token": self.token,
                "title": title,
                "type": "audio",
                "uri": uri
            }

            if summary:
                params["summary"] = summary

            self.logger.debug(f"Creating playlist with first track...")
            headers = {"Accept": "application/json"}
            response = requests.post(f"{self.base_url}/playlists", params=params, headers=headers, timeout=self.config.PLEX_TIMEOUT)
            response.raise_for_status()

            self.logger.info(f"Created playlist with 1 track")

            # Step 2: Add remaining tracks if there are any
            if len(track_rating_keys) > 1:
                remaining_tracks = track_rating_keys[1:]
                self.logger.info(f"Adding {len(remaining_tracks)} remaining tracks...")

                # Find the created playlist to get its ratingKey
                time.sleep(2)  # Give Plex time to create the playlist

                created_playlist = self.find_playlist_by_name(title)
                if created_playlist:
                    playlist_rating_key = created_playlist["ratingKey"]
                    add_success = self.add_tracks_to_playlist(playlist_rating_key, remaining_tracks)

                    if add_success:
                        self.logger.info(f"Successfully created playlist '{title}' with {len(track_rating_keys)} tracks total")
                        return True
                    else:
                        self.logger.warning(f"Playlist created with 1 track, but failed to add {len(remaining_tracks)} remaining tracks")
                        return True  # Partial success is still success
                else:
                    self.logger.error(f"Could not find created playlist to add remaining tracks")
                    return False
            else:
                self.logger.info(f"Successfully created playlist '{title}' with 1 track")
                return True

        except Exception as e:
            self.logger.error(f"Error creating playlist '{title}': {e}")
            return False

    def add_tracks_to_playlist(self, playlist_rating_key, track_rating_keys):
        """
        Add tracks to an existing playlist.
        This Plex server requires adding tracks ONE AT A TIME.
        COPIED EXACTLY from proven working implementation.
        """
        try:
            if not track_rating_keys:
                self.logger.warning("No tracks provided to add to playlist")
                return False

            self.logger.info(f"Adding {len(track_rating_keys)} tracks one by one...")

            total_added = 0

            for i, key in enumerate(track_rating_keys, 1):
                try:
                    # Add each track individually
                    uri = f"library://{self.base_url.split('://')[1]}/item/library%2Fmetadata%2F{key}"
                    params = {
                        "X-Plex-Token": self.token,
                        "uri": uri
                    }

                    add_url = f"{self.base_url}/playlists/{playlist_rating_key}/items"
                    headers = {"Accept": "application/json"}
                    response = requests.put(add_url, params=params, headers=headers, timeout=self.config.PLEX_TIMEOUT)
                    response.raise_for_status()

                    total_added += 1

                    # Progress indicator every 10 tracks
                    if i % 10 == 0 or i == len(track_rating_keys):
                        self.logger.debug(f"Added {i}/{len(track_rating_keys)} tracks")

                    # Small delay to avoid overwhelming the server
                    time.sleep(0.2)

                except Exception as track_error:
                    self.logger.warning(f"Failed to add track {i} (key: {key}): {track_error}")
                    continue

            if total_added > 0:
                self.logger.info(f"Successfully added {total_added}/{len(track_rating_keys)} tracks to playlist")
                return True
            else:
                self.logger.error(f"Failed to add any tracks to playlist")
                return False

        except Exception as e:
            self.logger.error(f"Error adding tracks to playlist: {e}")
            return False

    def delete_playlist(self, playlist_rating_key):
        """Delete a playlist. COPIED EXACTLY from proven working implementation."""
        try:
            self._delete(f"/playlists/{playlist_rating_key}")
            self.logger.info(f"Deleted playlist")
            return True
        except Exception as e:
            self.logger.error(f"Error deleting playlist: {e}")
            return False

    def create_or_update_playlist(self, title, track_rating_keys, summary=""):
        """
        Create a new playlist or update an existing one with the same name.
        Enhanced with playlist validation to avoid unnecessary recreation.
        """
        try:
            # Check if playlist already exists
            existing_playlist = self.find_playlist_by_name(title)

            if existing_playlist:
                self.logger.info(f"Found existing playlist '{title}', validating content...")
                
                # Get existing playlist track rating keys
                existing_track_keys = self.get_playlist_track_rating_keys(existing_playlist["ratingKey"])
                
                # Compare with new tracks
                if self._compare_playlist_tracks(existing_track_keys, track_rating_keys):
                    self.logger.info(f"Playlist '{title}' already exists with identical content, skipping recreation")
                    return True
                else:
                    self.logger.info(f"Playlist '{title}' content differs, updating playlist")
                    if not self.delete_playlist(existing_playlist["ratingKey"]):
                        self.logger.error(f"Failed to delete existing playlist")
                        return False

                    # Wait a moment for deletion to complete
                    time.sleep(2)

            self.logger.info(f"Creating new playlist '{title}'")
            return self.create_playlist(title, track_rating_keys, summary)

        except Exception as e:
            self.logger.error(f"Error creating or updating playlist '{title}': {e}")
            return False

    def get_playlist_tracks(self, playlist_rating_key):
        """Get all tracks in a playlist for verification purposes."""
        try:
            result = self._get(f"/playlists/{playlist_rating_key}/items")
            media_container = result.get("MediaContainer", {})
            tracks = media_container.get("Metadata", [])
            return tracks
        except Exception as e:
            self.logger.error(f"Error getting playlist tracks: {e}")
            return []

    def get_playlist_track_rating_keys(self, playlist_rating_key):
        """Get rating keys of all tracks in a playlist for comparison purposes."""
        try:
            tracks = self.get_playlist_tracks(playlist_rating_key)
            return [track.get("ratingKey") for track in tracks if track.get("ratingKey")]
        except Exception as e:
            self.logger.error(f"Error getting playlist track rating keys: {e}")
            return []

    def get_playlist_track_count(self, playlist_rating_key):
        """Get the number of tracks in a playlist."""
        try:
            tracks = self.get_playlist_tracks(playlist_rating_key)
            return len(tracks)
        except Exception as e:
            self.logger.error(f"Error getting playlist track count: {e}")
            return 0

    def _compare_playlist_tracks(self, existing_track_keys: List[str], new_track_keys: List[str]) -> bool:
        """
        Compare existing playlist tracks with new tracks to determine if they're identical.
        
        Args:
            existing_track_keys: List of rating keys from existing playlist
            new_track_keys: List of rating keys for new playlist
            
        Returns:
            True if playlists are identical, False otherwise
        """
        try:
            # Quick length check first
            if len(existing_track_keys) != len(new_track_keys):
                return False
            
            # Convert to sets for comparison (order doesn't matter)
            existing_set = set(existing_track_keys)
            new_set = set(new_track_keys)
            
            # Check if sets are identical
            return existing_set == new_set
            
        except Exception as e:
            self.logger.error(f"Error comparing playlist tracks: {e}")
            return False

    async def test_connection(self) -> bool:
        """Test connection to Plex Media Server"""
        try:
            self.logger.info("Testing connection to Plex Media Server...")

            # Test basic server connection
            result = self._get("/")

            # Test library access
            libraries = self.get_music_libraries()

            # Test playlist access
            playlists_result = self._get("/playlists")
            media_container = playlists_result.get("MediaContainer", {})
            playlists = media_container.get("Metadata", [])

            if result:
                # Get server info
                media_container = result.get('MediaContainer', {})
                server_name = media_container.get('friendlyName', 'Unknown')
                server_version = media_container.get('version', 'Unknown')
                
                self.logger.info(f"Connected to Plex server '{server_name}' (version {server_version})")
                
                if libraries:
                    self.logger.info(f"Found {len(libraries)} music libraries: {[lib['title'] for lib in libraries]}")
                else:
                    self.logger.warning("No music libraries found - playlist sync may not work")
                
                return True
            else:
                self.logger.error("Plex API test failed - no valid response")
                return False

        except Exception as e:
            self.logger.error(f"Failed to connect to Plex: {e}")
            return False

    async def get_api_stats(self) -> Dict[str, Any]:
        """Get basic API usage statistics"""
        stats = await super().get_api_stats()
        stats.update({
            'server_url': self.config.PLEX_URL,
            'timeout': self.config.PLEX_TIMEOUT,
            'ignore_tls': self.config.PLEX_IGNORE_TLS,
        })
        return stats
    
    def validate_playlist_exists(self, title: str) -> Dict[str, Any]:
        """
        Validate if a playlist exists and return detailed information about it.
        Returns dict with 'exists', 'count', 'playlists', 'total_tracks', 'track_inventory'
        """
        try:
            # Find all playlists with the given name
            existing_playlists = self.find_all_playlists_by_name(title)
            
            if not existing_playlists:
                return {
                    'exists': False,
                    'count': 0,
                    'playlists': [],
                    'total_tracks': 0,
                    'track_inventory': set()
                }
            
            # Get detailed information about each playlist
            playlist_details = []
            total_tracks = 0
            all_track_keys = set()
            
            for playlist in existing_playlists:
                playlist_rating_key = playlist.get('ratingKey', '')
                tracks = self.get_playlist_tracks(playlist_rating_key)
                track_keys = [track.get('ratingKey') for track in tracks if track.get('ratingKey')]
                
                playlist_details.append({
                    'id': playlist_rating_key,
                    'name': playlist.get('title', ''),
                    'track_count': len(tracks),
                    'track_keys': track_keys
                })
                
                total_tracks += len(tracks)
                all_track_keys.update(track_keys)
            
            return {
                'exists': True,
                'count': len(existing_playlists),
                'playlists': playlist_details,
                'total_tracks': total_tracks,
                'track_inventory': all_track_keys
            }
            
        except Exception as e:
            self.logger.error(f"Error validating playlist '{title}': {e}")
            return {
                'exists': False,
                'count': 0,
                'playlists': [],
                'total_tracks': 0,
                'track_inventory': set()
            }
    
    def find_all_playlists_by_name(self, playlist_name: str) -> List[Dict[str, Any]]:
        """Find all playlists with the given name (case-insensitive)"""
        try:
            results = self._get("/playlists")
            media_container = results.get("MediaContainer", {})
            playlists = media_container.get("Metadata", [])
            
            matching_playlists = []
            for playlist in playlists:
                if playlist.get("title", "").lower() == playlist_name.lower():
                    matching_playlists.append(playlist)
            
            return matching_playlists
        except Exception as e:
            self.logger.error(f"Error finding playlists by name '{playlist_name}': {e}")
            return []