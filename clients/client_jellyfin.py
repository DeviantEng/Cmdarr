#!/usr/bin/env python3
"""
Jellyfin API Client for playlist management
Based on Jellyfin REST API documentation
"""

import requests
import time
import logging
from typing import List, Dict, Any, Optional
from urllib.parse import quote_plus
from cache_manager import get_cache_manager
from .client_base import BaseAPIClient
from utils.cache_client import create_cache_client


class JellyfinClient(BaseAPIClient):
    """Client for Jellyfin Media Server operations"""
    
    def __init__(self, config):
        jellyfin_url = config.get('JELLYFIN_URL', 'http://localhost:8096')
        
        super().__init__(
            config=config,
            client_name='jellyfin',
            base_url=jellyfin_url.rstrip("/") if jellyfin_url else 'http://localhost:8096',
            rate_limit=1.0,  # Conservative rate limiting
            headers={
                'X-Emby-Token': config.get('JELLYFIN_TOKEN', ''),
                'Content-Type': 'application/json'
            }
        )
        
        self.logger.debug(f"JellyfinClient init - JELLYFIN_URL from config: {jellyfin_url}")
        self.logger.debug(f"JellyfinClient init - final base_url: {self.base_url}")
        
        self.token = config.get('JELLYFIN_TOKEN', '')
        self.user_id = config.get('JELLYFIN_USER_ID', '')
        
        # Initialize cache (always enabled)
        self.cache_enabled = True
        self.cache = get_cache_manager()
        
        # Initialize centralized cache client
        self.cache_client = create_cache_client('jellyfin', config)
        
        # Load cached library if library cache is enabled
        if config.get('LIBRARY_CACHE_JELLYFIN_ENABLED', False):
            self._load_cached_library()
    
    def get_cache_key(self, library_key: str = None) -> str:
        """Generate cache key for library cache"""
        # Include base URL to handle multiple Jellyfin instances
        if self.base_url is None:
            self.logger.error(f"base_url is None in get_cache_key for library_key: {library_key}")
            # Fallback to a default base URL
            base_url = "localhost_8096"
        else:
            base_url = self.base_url.replace('http://', '').replace('https://', '').replace('/', '_')
        
        self.logger.debug(f"get_cache_key - base_url: {base_url}, library_key: {library_key}")
        
        if library_key:
            return f"jellyfin:{base_url}:library:{library_key}"
        else:
            return f"jellyfin:{base_url}:library:default"
    
    def _get_cache_key(self, operation: str, *args) -> str:
        """Generate cache key for Jellyfin API operations"""
        # Include base URL to handle multiple Jellyfin instances
        if self.base_url is None:
            self.logger.error(f"base_url is None in _get_cache_key for operation: {operation}")
            # Fallback to a default base URL
            base_url = "localhost_8096"
        else:
            base_url = self.base_url.replace('http://', '').replace('https://', '').replace('/', '_')
        
        key_parts = [base_url, operation] + [str(arg) if arg is not None else 'none' for arg in args]
        return ':'.join(key_parts)
    
    def get_cache_ttl(self) -> int:
        """Get cache TTL in days for Jellyfin"""
        return self.config.get('CACHE_JELLYFIN_TTL_DAYS', 7)
    
    def _load_cached_library(self) -> None:
        """Load cached library data if available"""
        try:
            from utils.library_cache_manager import get_library_cache_manager
            cache_manager = get_library_cache_manager(self.config)
            
            # Register this client with the cache manager using centralized cache client
            self.cache_client.register_with_cache_manager(self)
            
            # Try to get cached library data
            cached_data = cache_manager.get_library_cache('jellyfin')
            
            if cached_data:
                self._cached_library = cached_data
                self.logger.info(f"Loaded cached library with {cached_data.get('total_tracks', 0)} tracks")
            else:
                self.logger.info("No cached library data available, will use live API searches")
                self._cached_library = None
                
        except Exception as e:
            self.logger.warning(f"Failed to load cached library: {e}")
            self._cached_library = None
    
    def _record_cache_hit(self) -> None:
        """Record a library cache hit"""
        self.cache_client.record_cache_hit()
    
    def _record_cache_miss(self) -> None:
        """Record a library cache miss"""
        self.cache_client.record_cache_miss()
    
    # ==== SYNCHRONOUS HTTP METHODS (like Plex client) ====
    
    def _get_sync(self, path: str, params: Dict[str, Any] = None) -> Optional[Dict[str, Any]]:
        """GET request to Jellyfin API using synchronous requests (like Plex)"""
        if params is None:
            params = {}
            
        headers = {
            'X-Emby-Token': self.token,
            'Content-Type': 'application/json'
        }
        
        try:
            response = requests.get(
                f"{self.base_url}{path}",
                params=params,
                headers=headers,
                timeout=30
            )
            response.raise_for_status()
            
            if response.status_code == 200:
                try:
                    return response.json()
                except ValueError:
                    self.logger.warning(f"Non-JSON response from {path}: {response.text[:100]}")
                    return {}
            return {}
        except requests.exceptions.RequestException as e:
            self.logger.error(f"Sync GET request failed for {path}: {e}")
            raise
    
    def _post_sync(self, path: str, params: Dict[str, Any] = None, json_data: Dict[str, Any] = None) -> Optional[Dict[str, Any]]:
        """POST request to Jellyfin API using synchronous requests (like Plex)"""
        if params is None:
            params = {}
            
        headers = {
            'X-Emby-Token': self.token,
            'Content-Type': 'application/json'
        }
        
        try:
            response = requests.post(
                f"{self.base_url}{path}",
                params=params,
                json=json_data,
                headers=headers,
                timeout=30
            )
            response.raise_for_status()
            
            if response.status_code in [200, 201, 204]:
                try:
                    return response.json() if response.text.strip() else {}
                except ValueError:
                    return {}  # OK for operations that don't return JSON
            return {}
        except requests.exceptions.RequestException as e:
            self.logger.error(f"Sync POST request failed for {path}: {e}")
            raise
    
    def test_connection(self) -> bool:
        """Test connection to Jellyfin server"""
        try:
            # First test basic connectivity with system info
            system_response = self._get_sync("/System/Info")
            if not system_response:
                self.logger.error("Failed to connect to Jellyfin server - system info not available")
                return False
            
            self.logger.info(f"Connected to Jellyfin server: {system_response.get('ServerName', 'Unknown')}")
            
            # Test authentication by getting user info with the configured user ID
            response = self._get_sync(f"/Users/{self.user_id}")
            if response and response.get('Id'):
                self.logger.info(f"Successfully connected to Jellyfin server")
                return True
            else:
                self.logger.error("Failed to connect to Jellyfin server - invalid user ID")
                self.logger.info("To find your Jellyfin user ID:")
                self.logger.info("1. Go to your Jellyfin web interface")
                self.logger.info("2. Go to Dashboard > Users")
                self.logger.info("3. Click on your user account")
                self.logger.info("4. The user ID will be in the URL or user details")
                self.logger.info("5. Update the JELLYFIN_USER_ID configuration with this ID")
                return False
        except Exception as e:
            self.logger.error(f"Connection test failed: {e}")
            return False
    
    def authenticate(self) -> bool:
        """Authenticate with Jellyfin server"""
        try:
            # Test authentication by getting user info
            response = self._get_sync(f"/Users/{self.user_id}")
            if response and response.get('Id'):
                self.logger.info(f"Successfully authenticated with Jellyfin server")
                return True
            else:
                self.logger.error("Failed to authenticate with Jellyfin server")
                return False
        except Exception as e:
            self.logger.error(f"Authentication failed: {e}")
            return False
    
    def get_server_info(self) -> Dict[str, Any]:
        """Get Jellyfin server information"""
        try:
            response = self._get_sync("/System/Info")
            if response:
                server_name = response.get('ServerName', 'Unknown')
                version = response.get('Version', 'Unknown')
                self.logger.info(f"Connected to Jellyfin server '{server_name}' (version {version})")
                return {
                    'server_name': server_name,
                    'version': version,
                    'id': response.get('Id'),
                    'system_info': response
                }
            return {}
        except Exception as e:
            self.logger.error(f"Failed to get server info: {e}")
            return {}
    
    def search_tracks_sync(self, query: str, limit: int = 50) -> List[Dict[str, Any]]:
        """Search for tracks in Jellyfin library"""
        self.logger.debug(f"=== SEARCH_TRACKS CALLED with query: '{query}', limit: {limit} ===")
        try:
            # Check cache first
            if self.cache_enabled:
                cache_key = self._get_cache_key("search_tracks", query, limit)
                cached_result = self.cache.get(cache_key, 'jellyfin')
                if cached_result is not None:
                    self.logger.debug(f"Cache hit for search_tracks: {query}, returning {len(cached_result)} cached tracks")
                    return cached_result
                else:
                    self.logger.debug(f"Cache miss for search_tracks: {query}")
            
            params = {
                'searchTerm': query,  # Use lowercase like web interface
                'includeItemTypes': 'Audio',
                'recursive': 'true',
                'limit': limit,
                'userId': self.user_id,
                'fields': 'PrimaryImageAspectRatio,CanDelete,MediaSourceCount',
                'imageTypeLimit': '1',
                'enableTotalRecordCount': 'false'
            }
            
            self.logger.debug(f"Searching Jellyfin API with params: {params}")
            self.logger.debug(f"Making HTTP request to /Items with user_id: {self.user_id}")
            self.logger.debug(f"Base URL: {self.base_url}")
            
            # Debug: Show the actual URL that will be constructed
            import urllib.parse
            full_url = f"{self.base_url}/Items"
            query_string = urllib.parse.urlencode(params)
            self.logger.debug(f"Full URL: {full_url}?{query_string}")
            
            try:
                response = self._get_sync("/Items", params=params)
                self.logger.debug(f"Jellyfin API response: {response}")
            except Exception as e:
                self.logger.error(f"HTTP request failed: {e}")
                import traceback
                self.logger.error(f"Traceback: {traceback.format_exc()}")
                return []
            
            tracks = []
            if response and 'Items' in response:
                tracks = self._extract_tracks_from_response(response['Items'])
                self.logger.debug(f"Found {len(tracks)} tracks with Audio search")
            
            # Cache the results
            if self.cache_enabled:
                cache_key = self._get_cache_key("search_tracks", query, limit)
                self.cache.set(cache_key, 'jellyfin', tracks, self.get_cache_ttl())
                self.logger.debug(f"Cached {len(tracks)} tracks for query: {query}")
            
            return tracks
        except Exception as e:
            self.logger.error(f"Failed to search tracks: {e}")
            import traceback
            self.logger.error(f"Traceback: {traceback.format_exc()}")
            return []
    
    def _extract_tracks_from_response(self, items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Extract track data from Jellyfin API response items"""
        tracks = []
        for item in items:
            if item.get('Type') == 'Audio':
                track_data = {
                    'id': item.get('Id'),
                    'name': item.get('Name'),
                    'artist': item.get('AlbumArtist', item.get('Artists', ['Unknown'])[0] if item.get('Artists') and len(item.get('Artists', [])) > 0 else 'Unknown'),
                    'album': item.get('Album', 'Unknown'),
                    'duration': item.get('RunTimeTicks', 0) // 10000000 if item.get('RunTimeTicks') else 0,
                    'path': item.get('Path'),
                    'year': item.get('ProductionYear')
                }
                tracks.append(track_data)
                self.logger.debug(f"Found track: '{track_data['artist']}' - '{track_data['name']}'")
        return tracks
    
    def find_track_by_artist_and_title_sync(self, artist: str, title: str, album: str = "") -> Optional[Dict[str, Any]]:
        """Find a specific track by artist and title with improved fuzzy matching"""
        self.logger.debug(f"=== FIND_TRACK_BY_ARTIST_AND_TITLE CALLED: '{artist}' - '{title}' ===")
        try:
            # First try to use cached library if available
            if hasattr(self, '_cached_library') and self._cached_library:
                self.logger.debug("Using cached library for track search")
                track_id = self.search_cached_library(title, artist, self._cached_library, album)
                if track_id:
                    # Find the track data from the cached tracks
                    tracks = self._cached_library.get('tracks', [])
                    for track in tracks:
                        if track.get('id') == track_id:
                            self.logger.debug(f"Found track in cache: '{track['artist']}' - '{track['name']}'")
                            # Record cache hit
                            self._record_cache_hit()
                            return track
                
                # Cache miss - no match found in cached library
                self.logger.debug("No match found in cached library")
                self._record_cache_miss()
            else:
                # Cache miss - no cached library available
                self.logger.debug("No cached library available")
                self._record_cache_miss()
            
            # Fallback to live API search if cache not available or no match found
            self.logger.debug("Using live API search for track")
            
            # Normalize search terms
            normalized_artist = self._normalize_text(artist)
            normalized_title = self._normalize_text(title)
            normalized_album = self._normalize_text(album) if album else ""
            
            self.logger.debug(f"Normalized search: '{normalized_artist}' - '{normalized_title}' - '{normalized_album}'")
            
            # Search for the track using title only (Jellyfin search works better with individual terms)
            self.logger.debug(f"Searching by title: '{title}'")
            tracks = self.search_tracks_sync(title, limit=50)
            self.logger.debug(f"Title search returned {len(tracks)} tracks")
            
            # Log what tracks were found for analysis
            if tracks:
                track_list = [f"{t['artist']} - {t['name']}" for t in tracks[:3]]
                self.logger.debug(f"Title search found tracks: {track_list}")
            
            # Try multiple matching strategies
            match = self._find_best_match(tracks, normalized_artist, normalized_title, artist, title, normalized_album, album)
            if match:
                return match
            
            # If no match, try searching by artist only
            self.logger.debug(f"No match found with title search, trying artist search: '{artist}'")
            artist_tracks = self.search_tracks_sync(artist, limit=50)
            self.logger.debug(f"Artist search returned {len(artist_tracks)} tracks")
            
            match = self._find_best_match(artist_tracks, normalized_artist, normalized_title, artist, title, normalized_album, album)
            if match:
                return match
            
            # If still no match, try searching by both artist and title
            self.logger.debug(f"No match found, trying combined search: '{artist} {title}'")
            combined_tracks = self.search_tracks_sync(f"{artist} {title}", limit=50)
            self.logger.debug(f"Combined search returned {len(combined_tracks)} tracks")
            
            match = self._find_best_match(combined_tracks, normalized_artist, normalized_title, artist, title, normalized_album, album)
            if match:
                return match
            
            # Strategy 5: Try searching with just key words from title and artist
            self.logger.debug("No match found, trying key word search...")
            artist_words = [w for w in normalized_artist.split() if len(w) > 2][:3]  # Take up to 3 significant words
            title_words = [w for w in normalized_title.split() if len(w) > 2][:3]   # Take up to 3 significant words
            
            if artist_words or title_words:
                key_words = artist_words + title_words
                key_word_query = ' '.join(key_words)
                self.logger.debug(f"Key word search: '{key_word_query}'")
                keyword_tracks = self.search_tracks_sync(key_word_query, limit=50)
                self.logger.debug(f"Key word search returned {len(keyword_tracks)} tracks")
                
                match = self._find_best_match(keyword_tracks, normalized_artist, normalized_title, artist, title, normalized_album, album)
                if match:
                    return match
            
            # Strategy 6: Relaxed fuzzy matching with lower threshold
            self.logger.debug("No match found, trying relaxed fuzzy matching...")
            all_unique_tracks = {}
            for track_list in [tracks, artist_tracks, combined_tracks]:
                for track in track_list:
                    all_unique_tracks[track['id']] = track
            
            if keyword_tracks:  # Add keyword tracks if they exist
                for track in keyword_tracks:
                    all_unique_tracks[track['id']] = track
            
            all_tracks = list(all_unique_tracks.values())
            self.logger.debug(f"Trying relaxed matching on {len(all_tracks)} unique tracks")
            match = self._find_best_match_relaxed(all_tracks, normalized_artist, normalized_title, artist, title, normalized_album, album)
            if match:
                return match
            
            # Strategy 7: Ultra-relaxed matching - requires artist match to avoid cross-artist false matches
            self.logger.debug("No match found, trying ultra-relaxed matching...")
            match = self._find_best_match_ultra_relaxed(all_tracks, normalized_title, title, normalized_artist)
            if match:
                return match
            
            # Strategy 8: Focused fallback strategies (in order of preference)
            self.logger.debug("No match found, trying focused fallback strategies...")
            
            # Strategy 8a: Full search (artist + title)
            self.logger.debug("Strategy 8a: Full search (artist + title)")
            full_query = f"{artist} {title}"
            self.logger.debug(f"Full search: '{full_query}'")
            full_tracks = self.search_tracks_sync(full_query, limit=50)
            self.logger.debug(f"Full search returned {len(full_tracks)} tracks")
            
            if full_tracks:
                match = self._find_best_match_ultra_relaxed(full_tracks, normalized_title, title, normalized_artist)
                if match:
                    self.logger.info(f"Full search match found: '{match['artist']}' - '{match['name']}' for '{artist}' - '{title}'")
                    return match
            
            # Strategy 8b: Truncated search (artist + shortened title, max 25 chars)
            self.logger.debug("Strategy 8b: Truncated search (artist + shortened title)")
            truncated_title = self._truncate_title_for_search(title, 25 - len(artist) - 1)  # -1 for space
            if truncated_title != title:
                truncated_query = f"{artist} {truncated_title}"
                self.logger.debug(f"Truncated search: '{truncated_query}'")
                truncated_tracks = self.search_tracks_sync(truncated_query, limit=50)
                self.logger.debug(f"Truncated search returned {len(truncated_tracks)} tracks")
                
                if truncated_tracks:
                    match = self._find_best_match_ultra_relaxed(truncated_tracks, normalized_title, title, normalized_artist)
                    if match:
                        self.logger.info(f"Truncated search match found: '{match['artist']}' - '{match['name']}' for '{artist}' - '{title}'")
                        return match
            
            # Strategy 8c: Title-only search with artist validation
            self.logger.debug("Strategy 8c: Title-only search with artist validation")
            title_only_match = self._try_title_only_search_with_validation(title, artist, normalized_artist, normalized_title)
            if title_only_match:
                return title_only_match
            
            # Strategy 8d: Progressive title word removal (handle Jellyfin API limitations)
            self.logger.debug("Strategy 8d: Progressive title word removal")
            progressive_match = self._try_progressive_title_word_removal(title, artist, normalized_artist, normalized_title)
            if progressive_match:
                return progressive_match
            
            self.logger.info(f"❌ TRACK NOT FOUND: '{artist}' - '{title}'")
            self.logger.info(f"   📋 Search attempts made:")
            self.logger.info(f"     1️⃣ Title search: '{title}' ({len(tracks)} results)")
            self.logger.info(f"     2️⃣ Artist search: '{artist}' ({len(artist_tracks) if 'artist_tracks' in locals() else 0} results)")
            self.logger.info(f"     3️⃣ Combined search: '{artist} {title}' ({len(combined_tracks) if 'combined_tracks' in locals() else 0} results)")
            if 'keyword_tracks' in locals():
                self.logger.info(f"     4️⃣ Keyword search: {len(keyword_tracks)} results")
            self.logger.info(f"     5️⃣ Relaxed fuzzy matching: {len(all_tracks)} unique tracks")
            self.logger.info(f"     6️⃣ Ultra-relaxed matching: {len(all_tracks)} tracks")
            if 'full_tracks' in locals():
                self.logger.info(f"     7️⃣ Full search: '{artist} {title}' ({len(full_tracks)} results)")
            if 'truncated_tracks' in locals():
                self.logger.info(f"     8️⃣ Truncated search: {len(truncated_tracks)} results")
            self.logger.info(f"     9️⃣ Title-only search: '{title}' with artist validation")
            self.logger.info(f"     🔟 Progressive title word removal: Multiple variants tried")
            self.logger.info(f"   🔍 All search strategies (1-10) failed to find a match above 25% similarity")
            self.logger.debug(f"No match found for: '{artist}' - '{title}'")
            return None
        except Exception as e:
            self.logger.error(f"Failed to find track: {e}")
            return None
    
    def _normalize_text(self, text: str) -> str:
        """Normalize text for better matching by removing special characters and standardizing"""
        if not text:
            return ''
        
        # Convert to lowercase and strip whitespace
        normalized = str(text).lower().strip()
        
        # Handle music-specific patterns first
        import re
        # Remove featuring/feat patterns (more comprehensive)
        normalized = re.sub(r'\s*\(feat\.?\s+[^)]+\)\s*', ' ', normalized)
        normalized = re.sub(r'\s*\(ft\.?\s+[^)]+\)\s*', ' ', normalized)
        normalized = re.sub(r'\s*feat\.?\s+.*$', ' ', normalized)
        normalized = re.sub(r'\s*ft\.?\s+.*$', ' ', normalized)
        
        # Handle collaboration formats - normalize "&" to "feat"
        normalized = re.sub(r'\s*&\s*', ' feat ', normalized)
        normalized = re.sub(r'\s*featuring\s+', ' feat ', normalized)
        
        # Handle common version/remix patterns more aggressively
        normalized = re.sub(r'\s*\(reimagined\)\s*', ' ', normalized, flags=re.IGNORECASE)
        normalized = re.sub(r'\s*\(remastered?\)\s*', ' ', normalized, flags=re.IGNORECASE)
        normalized = re.sub(r'\s*\(radio edit\)\s*', ' ', normalized, flags=re.IGNORECASE)
        normalized = re.sub(r'\s*\(clean\)\s*', ' ', normalized, flags=re.IGNORECASE)
        normalized = re.sub(r'\s*\(explicit\)\s*', ' ', normalized, flags=re.IGNORECASE)
        
        # Remove version/remix information
        normalized = re.sub(r'\s*\(.*?(remix|mix|edit|version|remaster|radio|clean|explicit|instrumental|acoustic|live|demo).*?\)\s*', ' ', normalized, flags=re.IGNORECASE)
        normalized = re.sub(r'\s*\[.*?(remix|mix|edit|version|remaster|radio|clean|explicit|instrumental|acoustic|live|demo).*?\]\s*', ' ', normalized, flags=re.IGNORECASE)
        
        # Remove parentheses and brackets content
        normalized = re.sub(r'\s*\([^)]*\)\s*', ' ', normalized)
        normalized = re.sub(r'\s*\[[^\]]*\]\s*', ' ', normalized)
        
        # Apply centralized punctuation normalization
        from utils.text_normalizer import normalize_text
        normalized = normalize_text(normalized)
        
        # Replace multiple spaces with single space
        normalized = re.sub(r'\s+', ' ', normalized)
        
        # Remove common words that might cause matching issues
        common_words = ['the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with', 'by']
        words = normalized.split()
        words = [word for word in words if word not in common_words and len(word) > 1]
        normalized = ' '.join(words)
        
        return normalized.strip()
    
    def _find_best_match(self, tracks: List[Dict[str, Any]], normalized_artist: str, normalized_title: str, 
                        original_artist: str, original_title: str, normalized_album: str = "", original_album: str = "") -> Optional[Dict[str, Any]]:
        """Find the best matching track using multiple strategies"""
        if not tracks:
            return None
        
        # Strategy 1: Exact match (case-insensitive) - with album bonus
        for track in tracks:
            if (track['artist'].lower() == original_artist.lower() and 
                track['name'].lower() == original_title.lower()):
                
                # Check album match for bonus scoring
                album_bonus = 0
                if original_album and track.get('album'):
                    track_album_norm = self._normalize_text(track['album'])
                    if track_album_norm == normalized_album:
                        album_bonus = 0.2  # 20% bonus for exact album match
                    elif normalized_album in track_album_norm or track_album_norm in normalized_album:
                        album_bonus = 0.1  # 10% bonus for partial album match
                
                self.logger.debug(f"Exact match found: '{track['artist']}' - '{track['name']}' (album bonus: {album_bonus:.1%})")
                return track
        
        # Strategy 2: Normalized exact match - with album bonus
        for track in tracks:
            track_artist_norm = self._normalize_text(track['artist'])
            track_title_norm = self._normalize_text(track['name'])
            
            if (track_artist_norm == normalized_artist and 
                track_title_norm == normalized_title):
                
                # Check album match for bonus scoring
                album_bonus = 0
                if normalized_album and track.get('album'):
                    track_album_norm = self._normalize_text(track['album'])
                    if track_album_norm == normalized_album:
                        album_bonus = 0.2  # 20% bonus for exact album match
                    elif normalized_album in track_album_norm or track_album_norm in normalized_album:
                        album_bonus = 0.1  # 10% bonus for partial album match
                
                self.logger.debug(f"Normalized exact match found: '{track['artist']}' - '{track['name']}' (album bonus: {album_bonus:.1%})")
                return track
        
        # Strategy 3: Partial match (both artist and title contain search terms) - with album bonus
        for track in tracks:
            if (normalized_artist in self._normalize_text(track['artist']) and 
                normalized_title in self._normalize_text(track['name'])):
                
                # Check album match for bonus scoring
                album_bonus = 0
                if normalized_album and track.get('album'):
                    track_album_norm = self._normalize_text(track['album'])
                    if track_album_norm == normalized_album:
                        album_bonus = 0.2  # 20% bonus for exact album match
                    elif normalized_album in track_album_norm or track_album_norm in normalized_album:
                        album_bonus = 0.1  # 10% bonus for partial album match
                
                self.logger.debug(f"Partial match found: '{track['artist']}' - '{track['name']}' (album bonus: {album_bonus:.1%})")
                return track
        
        # Strategy 4: Fuzzy match using similarity - with album scoring
        best_match = None
        best_score = 0
        
        for track in tracks:
            artist_score = self._calculate_similarity(normalized_artist, self._normalize_text(track['artist']))
            title_score = self._calculate_similarity(normalized_title, self._normalize_text(track['name']))
            
            # Album scoring (bonus)
            album_score = 0
            if normalized_album and track.get('album'):
                track_album_norm = self._normalize_text(track['album'])
                album_score = self._calculate_similarity(normalized_album, track_album_norm)
            
            # Combined score (weighted average with album bonus)
            combined_score = (artist_score * 0.5) + (title_score * 0.4) + (album_score * 0.1)
            
            if combined_score > best_score and combined_score > 0.7:  # 70% similarity threshold
                best_score = combined_score
                best_match = track
        
        if best_match:
            self.logger.debug(f"Fuzzy match found (score: {best_score:.2f}): '{best_match['artist']}' - '{best_match['name']}'")
            return best_match
        
        return None
    
    def _find_best_match_relaxed(self, tracks: List[Dict[str, Any]], normalized_artist: str, normalized_title: str, 
                                original_artist: str, original_title: str, normalized_album: str = "", original_album: str = "") -> Optional[Dict[str, Any]]:
        """Find the best matching track using relaxed fuzzy matching with lower thresholds"""
        if not tracks:
            return None
        
        best_match = None
        best_score = 0
        
        for track in tracks:
            track_artist_norm = self._normalize_text(track['artist'])
            track_title_norm = self._normalize_text(track['name'])
            
            # Calculate multiple similarity measures
            artist_jaccard = self._calculate_similarity(normalized_artist, track_artist_norm)
            title_jaccard = self._calculate_similarity(normalized_title, track_title_norm)
            
            # Character-based similarity for titles (handles minor spelling differences)
            title_char_sim = self._calculate_character_similarity(normalized_title, track_title_norm)
            
            # Word order independence for titles
            title_word_sim = self._calculate_word_order_similarity(normalized_title, track_title_norm)
            
            # Best title similarity from multiple measures
            title_best = max(title_jaccard, title_char_sim, title_word_sim)
            
            # Album scoring (bonus)
            album_score = 0
            if normalized_album and track.get('album'):
                track_album_norm = self._normalize_text(track['album'])
                album_score = self._calculate_similarity(normalized_album, track_album_norm)
            
            # Combined score with album bonus (adjusted weights to accommodate album)
            combined_score = (artist_jaccard * 0.35) + (title_best * 0.55) + (album_score * 0.1)

            # Require minimum artist match to avoid cross-artist false matches (e.g. Antidote/Braeker vs Antidote/Greywind)
            if artist_jaccard < 0.2:
                continue

            # Relaxed threshold (was 0.7, now 0.5)
            if combined_score > best_score and combined_score > 0.5:
                best_score = combined_score
                best_match = track
                self.logger.debug(f"Relaxed match candidate (score: {combined_score:.2f}): '{track['artist']}' - '{track['name']}' | Artist sim: {artist_jaccard:.2f}, Title sim: {title_best:.2f}, Album sim: {album_score:.2f}")
        
        if best_match:
            self.logger.debug(f"Relaxed fuzzy match found (score: {best_score:.2f}): '{best_match['artist']}' - '{best_match['name']}'")
            return best_match
        
        return None
    
    def _calculate_character_similarity(self, text1: str, text2: str) -> float:
        """Calculate character-level similarity using simple overlap ratio"""
        if not text1 or not text2:
            return 0.0
        
        # Remove spaces and convert to lowercase for character comparison
        chars1 = set(text1.replace(' ', '').lower())
        chars2 = set(text2.replace(' ', '').lower())
        
        if not chars1 or not chars2:
            return 0.0
        
        intersection = chars1.intersection(chars2)
        union = chars1.union(chars2)
        
        return len(intersection) / len(union) if union else 0.0
    
    def _calculate_word_order_similarity(self, text1: str, text2: str) -> float:
        """Calculate similarity ignoring word order (useful for 'Title (Remix)' vs 'Remix Title' cases)"""
        if not text1 or not text2:
            return 0.0
        
        words1 = set(text1.split())
        words2 = set(text2.split())
        
        if not words1 or not words2:
            return 0.0
        
        # Higher weight for exact word matches regardless of order
        intersection = words1.intersection(words2)
        union = words1.union(words2)
        
        similarity = len(intersection) / len(union) if union else 0.0
        
        # Boost score if most words match (handles cases like "Song Title" vs "Title Song")
        if len(intersection) >= min(len(words1), len(words2)) * 0.8:
            similarity *= 1.2  # 20% boost
        
        return min(similarity, 1.0)  # Cap at 1.0
    
    def _find_best_match_ultra_relaxed(self, tracks: List[Dict[str, Any]], normalized_title: str, original_title: str,
                                       normalized_artist: str = "") -> Optional[Dict[str, Any]]:
        """Ultra-relaxed matching - requires artist match to avoid cross-artist false matches (e.g. Antidote/Braeker vs Antidote/Greywind)"""
        if not tracks:
            return None

        best_match = None
        best_score = 0

        for track in tracks:
            track_title_norm = self._normalize_text(track['name'])
            track_artist_norm = self._normalize_text(track.get('artist', ''))

            # Require artist match - never match same title by different artist
            if normalized_artist and track_artist_norm:
                artist_score = self._calculate_similarity(normalized_artist, track_artist_norm)
                if artist_score < 0.2:  # Reject cross-artist matches (Braeker vs Greywind = 0)
                    continue

            # Multiple title similarity measures
            title_jaccard = self._calculate_similarity(normalized_title, track_title_norm)
            title_char_sim = self._calculate_character_similarity(normalized_title, track_title_norm)
            title_word_sim = self._calculate_word_order_similarity(normalized_title, track_title_norm)

            # Take the best title similarity
            title_score = max(title_jaccard, title_char_sim, title_word_sim)

            # Additional check for very short titles (like "ATTN.")
            if len(normalized_title.replace(' ', '')) <= 4 and len(track_title_norm.replace(' ', '')) <= 4:
                # For very short titles, be more lenient with character matching
                char_overlap = len(set(normalized_title.replace(' ', '')) & set(track_title_norm.replace(' ', '')))
                if char_overlap >= 2:  # At least 2 characters match
                    title_score = max(title_score, 0.6)  # Boost score for short titles

            # Very low threshold for ultra-relaxed matching (25% - even more relaxed)
            if title_score > best_score and title_score > 0.25:
                best_score = title_score
                best_match = track
                self.logger.debug(f"Ultra-relaxed match candidate (title score: {title_score:.2f}): '{track['artist']}' - '{track['name']}'")
        
        if best_match:
            self.logger.info(f"Ultra-relaxed match found (title score: {best_score:.2f}): '{best_match['artist']}' - '{best_match['name']}' for '{original_title}'")
            return best_match
        
        return None
    
    def _calculate_similarity(self, text1: str, text2: str) -> float:
        """Calculate similarity between two strings using simple character overlap"""
        if not text1 or not text2:
            return 0.0
        
        # Convert to sets of words
        words1 = set(text1.split())
        words2 = set(text2.split())
        
        if not words1 or not words2:
            return 0.0
        
        # Calculate Jaccard similarity
        intersection = words1.intersection(words2)
        union = words1.union(words2)
        
        return len(intersection) / len(union) if union else 0.0
    
    def create_playlist_sync(self, title: str, track_ids: List[str], summary: str = "") -> bool:
        """Create a new playlist with the given tracks using synchronous requests (like Plex)"""
        try:
            if not track_ids:
                self.logger.warning("No tracks provided for playlist creation")
                return False
            
            self.logger.info(f"Creating playlist '{title}' with {len(track_ids)} tracks")
            
            # Create playlist using synchronous requests (like working test script)
            # Filter out any None values, empty strings, and ensure all are strings
            valid_track_ids = [str(tid) for tid in track_ids if tid is not None and str(tid).strip()]
            if len(valid_track_ids) != len(track_ids):
                self.logger.warning(f"Filtered out {len(track_ids) - len(valid_track_ids)} invalid values from track_ids")
            
            playlist_data = {
                'Name': title,
                'Overview': summary,
                'Ids': ','.join(valid_track_ids),  # Comma-separated string like working test script
                'UserId': self.user_id,      # Include user ID
                'MediaType': 'Audio'         # Specify media type
            }
            
            self.logger.debug(f"Creating playlist with data: {playlist_data}")
            self.logger.debug(f"User ID being used: {self.user_id}")
            
            # Use synchronous requests like the working test script
            headers = {
                'X-Emby-Token': self.token,
                'Content-Type': 'application/json'
            }
            
            response = requests.post(
                f"{self.base_url}/Playlists",
                json=playlist_data,
                headers=headers,
                timeout=30
            )
            response.raise_for_status()
            
            if response.status_code in [200, 201]:
                response_data = response.json()
                if response_data and response_data.get('Id'):
                    playlist_id = response_data['Id']
                    self.logger.info(f"Successfully created playlist '{title}' with ID {playlist_id}")
                    # TODO: Re-enable cache invalidation after fixing the cache issue
                    # Temporarily disabled to prevent errors
                    if False and self.cache_enabled:
                        try:
                            cleared_count = self.cache.clear_cache('jellyfin')
                            self.logger.debug(f"Invalidated playlists cache after creating playlist '{title}' ({cleared_count} entries cleared)")
                        except Exception as cache_error:
                            self.logger.warning(f"Failed to clear cache after creating playlist '{title}': {cache_error}")
                    return True
                else:
                    self.logger.error(f"Failed to create playlist '{title}' - no ID in response")
                    return False
            else:
                self.logger.error(f"Failed to create playlist '{title}' - status {response.status_code}")
                return False
                
        except requests.exceptions.RequestException as e:
            self.logger.error(f"HTTP error creating playlist '{title}': {e}")
            return False
        except Exception as e:
            self.logger.error(f"Failed to create playlist '{title}': {e}")
            return False

    def create_playlist(self, title: str, track_ids: List[str], summary: str = "") -> bool:
        """Create a new playlist with the given tracks"""
        # Use synchronous method for reliability (like Plex)
        return self.create_playlist_sync(title, track_ids, summary)
    
    def get_playlists_sync(self) -> List[Dict[str, Any]]:
        """Get all playlists from Jellyfin using synchronous requests"""
        try:
            # Check cache first
            if self.cache_enabled:
                cache_key = self._get_cache_key("get_playlists")
                cached_result = self.cache.get(cache_key, 'jellyfin')
                if cached_result:
                    self.logger.debug("Cache hit for get_playlists")
                    # Extract playlists from cached data
                    if isinstance(cached_result, dict) and 'playlists' in cached_result:
                        return cached_result['playlists']
                    elif isinstance(cached_result, list):
                        # Handle old format for backward compatibility
                        return cached_result
                    else:
                        self.logger.warning("Invalid cached data format for get_playlists")
                        return []
            
            headers = {
                'X-Emby-Token': self.token,
                'Content-Type': 'application/json'
            }
            
            # Get playlists from the Playlists folder (not top-level folders)
            # First, we need to find the Playlists folder ID
            playlists_folder_id = None
            
            # Try to find the Playlists folder
            folder_params = {
                'UserId': self.user_id,
                'IncludeItemTypes': 'ManualPlaylistsFolder'
            }
            
            folder_response = requests.get(
                f"{self.base_url}/Items",
                params=folder_params,
                headers=headers,
                timeout=30
            )
            
            if folder_response.status_code == 200:
                folder_data = folder_response.json()
                if 'Items' in folder_data:
                    for item in folder_data['Items']:
                        if item.get('Name') == 'Playlists':
                            playlists_folder_id = item.get('Id')
                            break
            
            if not playlists_folder_id:
                self.logger.warning("Could not find Playlists folder, falling back to top-level search")
                params = {
                    'UserId': self.user_id,
                    'IncludeItemTypes': 'Playlist'
                }
            else:
                # Get playlists from the Playlists folder
                params = {
                    'UserId': self.user_id,
                    'ParentId': playlists_folder_id,
                    'Recursive': 'true'
                }
            
            response = requests.get(
                f"{self.base_url}/Items",
                params=params,
                headers=headers,
                timeout=30
            )
            response.raise_for_status()
            
            if response.status_code == 200:
                data = response.json()
                if data and 'Items' in data:
                    playlists = data['Items']
                    
                    # Cache the result
                    if self.cache_enabled:
                        cache_key = self._get_cache_key("get_playlists")
                        # Wrap list in dict for cache storage
                        cache_data = {'playlists': playlists, 'count': len(playlists)}
                        self.cache.set(cache_key, 'jellyfin', cache_data, ttl_days=self.get_cache_ttl())
                    
                    self.logger.debug(f"Retrieved {len(playlists)} playlists from Jellyfin")
                    return playlists
                else:
                    self.logger.warning("No playlists found in Jellyfin response")
                    return []
            else:
                self.logger.warning(f"No playlists found in Jellyfin response (status {response.status_code})")
                return []
                
        except requests.exceptions.RequestException as e:
            self.logger.error(f"HTTP error getting playlists from Jellyfin: {e}")
            return []
        except Exception as e:
            self.logger.error(f"Failed to get playlists from Jellyfin: {e}")
            return []

    def get_playlists(self) -> List[Dict[str, Any]]:
        """Get all playlists from Jellyfin"""
        return self.get_playlists_sync()

    def find_playlist_by_name_sync(self, playlist_name: str) -> Optional[Dict[str, Any]]:
        """Find a playlist by name using synchronous requests (returns first match)"""
        try:
            # Check cache first
            if self.cache_enabled:
                cache_key = self._get_cache_key("find_playlist", playlist_name)
                cached_result = self.cache.get(cache_key, 'jellyfin')
                if cached_result:
                    self.logger.debug(f"Cache hit for find_playlist: {playlist_name}")
                    return cached_result
            
            # Get all playlists using the same logic as get_playlists_sync
            all_playlists = self.get_playlists_sync()
            
            # Search through all playlists for the exact name match
            self.logger.debug(f"Searching for playlist '{playlist_name}' in {len(all_playlists)} playlists")
            for playlist in all_playlists:
                playlist_name_found = playlist.get('Name', '')
                self.logger.debug(f"Found playlist: '{playlist_name_found}'")
                if playlist_name_found == playlist_name:
                    self.logger.debug(f"Exact match found for playlist '{playlist_name}'")
                    # Cache the result
                    if self.cache_enabled:
                        cache_key = self._get_cache_key("find_playlist", playlist_name)
                        self.cache.set(cache_key, 'jellyfin', playlist, self.get_cache_ttl())
                    return playlist
            
            self.logger.debug(f"No exact match found for playlist '{playlist_name}'")
            return None
        except Exception as e:
            self.logger.error(f"Failed to find playlist '{playlist_name}': {e}")
            return None

    def find_all_playlists_by_name_sync(self, playlist_name: str) -> List[Dict[str, Any]]:
        """Find ALL playlists with a given name using synchronous requests"""
        try:
            # Get all playlists using the same logic as get_playlists_sync
            all_playlists = self.get_playlists_sync()
            
            # Search through all playlists for exact name matches
            matches = []
            self.logger.debug(f"Searching for ALL playlists named '{playlist_name}' in {len(all_playlists)} playlists")
            for playlist in all_playlists:
                playlist_name_found = playlist.get('Name', '')
                if playlist_name_found == playlist_name:
                    self.logger.debug(f"Found matching playlist: '{playlist_name_found}' (ID: {playlist.get('Id', 'Unknown')})")
                    matches.append(playlist)
            
            self.logger.debug(f"Found {len(matches)} playlists with name '{playlist_name}'")
            return matches
        except Exception as e:
            self.logger.error(f"Failed to find playlists with name '{playlist_name}': {e}")
            return []

    def find_playlist_by_name(self, playlist_name: str) -> Optional[Dict[str, Any]]:
        """Find a playlist by name"""
        return self.find_playlist_by_name_sync(playlist_name)
    
    def delete_playlist_sync(self, playlist_id: str) -> bool:
        """Delete a playlist by ID using synchronous requests"""
        try:
            headers = {
                'X-Emby-Token': self.token,
                'Content-Type': 'application/json'
            }
            
            response = requests.delete(
                f"{self.base_url}/Items/{playlist_id}",
                headers=headers,
                timeout=30
            )
            
            # Handle 404 specifically before raise_for_status()
            if response.status_code == 404:
                self.logger.info(f"Playlist {playlist_id} already deleted (404 - not found)")
                return True
            
            response.raise_for_status()
            
            if response.status_code in [200, 204]:
                self.logger.info(f"Successfully deleted playlist {playlist_id}")
                # TODO: Re-enable cache invalidation after fixing the cache issue
                # Temporarily disabled to prevent errors
                if False and self.cache_enabled:
                    try:
                        cleared_count = self.cache.clear_cache('jellyfin')
                        self.logger.debug(f"Invalidated playlists cache after deleting playlist {playlist_id} ({cleared_count} entries cleared)")
                    except Exception as cache_error:
                        self.logger.warning(f"Failed to clear cache after deleting playlist {playlist_id}: {cache_error}")
                return True
            else:
                self.logger.error(f"Failed to delete playlist {playlist_id} - status {response.status_code}")
                return False
        except requests.exceptions.RequestException as e:
            # 404 errors are OK - playlist is already gone (desired outcome)
            self.logger.debug(f"RequestException caught: type={type(e)}, str={str(e)}")
            if hasattr(e, 'response'):
                self.logger.debug(f"Exception has response: status_code={getattr(e.response, 'status_code', 'None')}")
            
            if hasattr(e, 'response') and e.response and e.response.status_code == 404:
                self.logger.info(f"Playlist {playlist_id} already deleted (404 - not found)")
                return True
            elif "404" in str(e) or "Not Found" in str(e):
                # Alternative way to catch 404s if response object isn't available
                self.logger.info(f"Playlist {playlist_id} already deleted (404 in error message)")
                return True
            else:
                self.logger.error(f"HTTP error deleting playlist {playlist_id}: {e}")
                return False
        except Exception as e:
            self.logger.error(f"Failed to delete playlist {playlist_id}: {e}")
            return False

    def delete_playlist(self, playlist_id: str) -> bool:
        """Delete a playlist by ID"""
        return self.delete_playlist_sync(playlist_id)
    
    def get_playlist_tracks_sync(self, playlist_id: str) -> List[Dict[str, Any]]:
        """Get tracks from a playlist using synchronous requests"""
        try:
            params = {
                'UserId': self.user_id
            }
            
            headers = {
                'X-Emby-Token': self.token,
                'Content-Type': 'application/json'
            }
            
            response = requests.get(
                f"{self.base_url}/Playlists/{playlist_id}/Items",
                params=params,
                headers=headers,
                timeout=30
            )
            
            # Handle 404 specifically before raise_for_status()
            if response.status_code == 404:
                self.logger.debug(f"Playlist {playlist_id} not found (404), returning empty track list")
                return []
            
            response.raise_for_status()
            
            if response.status_code == 200:
                data = response.json()
                if data and 'Items' in data:
                    tracks = []
                    for item in data['Items']:
                        if item.get('Type') == 'Audio':
                            tracks.append({
                                'id': item.get('Id'),
                                'name': item.get('Name'),
                                'artist': item.get('AlbumArtist', item.get('Artists', ['Unknown'])[0] if item.get('Artists') and len(item.get('Artists', [])) > 0 else 'Unknown'),
                                'album': item.get('Album', 'Unknown')
                            })
                    return tracks
            return []
        except requests.exceptions.RequestException as e:
            # 404 errors are OK - playlist doesn't exist or was deleted, return empty list
            if hasattr(e, 'response') and e.response and e.response.status_code == 404:
                self.logger.debug(f"Playlist {playlist_id} not found (404), returning empty track list")
                return []
            elif "404" in str(e) or "Not Found" in str(e):
                # Alternative way to catch 404s if response object isn't available
                self.logger.debug(f"Playlist {playlist_id} not found (404 in error message), returning empty track list")
                return []
            else:
                self.logger.error(f"HTTP error getting playlist tracks: {e}")
                return []
        except Exception as e:
            self.logger.error(f"Failed to get playlist tracks: {e}")
            return []

    def get_playlist_tracks(self, playlist_id: str) -> List[Dict[str, Any]]:
        """Get tracks from a playlist"""
        return self.get_playlist_tracks_sync(playlist_id)
    
    def _compare_playlist_tracks(self, existing_track_ids: List[str], new_track_ids: List[str]) -> bool:
        """
        Compare existing playlist tracks with new tracks to determine if they're identical.
        
        Args:
            existing_track_ids: List of track IDs from existing playlist
            new_track_ids: List of track IDs for new playlist
            
        Returns:
            True if playlists are identical, False otherwise
        """
        try:
            # Quick length check first
            if len(existing_track_ids) != len(new_track_ids):
                return False
            
            # Convert to sets for comparison (order doesn't matter)
            existing_set = set(existing_track_ids)
            new_set = set(new_track_ids)
            
            # Compare sets
            return existing_set == new_set
            
        except Exception as e:
            self.logger.error(f"Error comparing playlist tracks: {e}")
            return False
    
    def create_or_update_playlist_sync(self, title: str, track_ids: List[str], summary: str = "") -> bool:
        """
        Create a new playlist or update an existing one with the same name.
        Enhanced with playlist validation to avoid unnecessary recreation.
        Handles multiple duplicates by deleting ALL existing playlists with the same name.
        """
        try:
            # Validate input track IDs
            if not track_ids:
                self.logger.warning(f"No track IDs provided for playlist '{title}', skipping creation")
                return False
            
            # Filter out None values and validate track IDs
            valid_track_ids = [tid for tid in track_ids if tid is not None and tid.strip()]
            if not valid_track_ids:
                self.logger.warning(f"No valid track IDs provided for playlist '{title}', skipping creation")
                return False
            
            if len(valid_track_ids) != len(track_ids):
                self.logger.warning(f"Filtered out {len(track_ids) - len(valid_track_ids)} invalid track IDs for playlist '{title}'")
            
            # Check if playlists with this name already exist
            existing_playlists = self.find_all_playlists_by_name_sync(title)

            if existing_playlists:
                self.logger.info(f"Found {len(existing_playlists)} existing playlist(s) with name '{title}', validating content...")
                
                # Check if any existing playlist has identical content
                for existing_playlist in existing_playlists:
                    existing_track_ids = [track['id'] for track in self.get_playlist_tracks_sync(existing_playlist['Id'])]
                    
                    if self._compare_playlist_tracks(existing_track_ids, valid_track_ids):
                        self.logger.info(f"Playlist '{title}' already exists with identical content, skipping recreation")
                        # Delete any other duplicates with the same name
                        for other_playlist in existing_playlists:
                            if other_playlist['Id'] != existing_playlist['Id']:
                                self.logger.info(f"Deleting duplicate playlist '{title}' (ID: {other_playlist['Id']})")
                                self.delete_playlist_sync(other_playlist['Id'])
                        return True
                
                # Check if any existing playlist has tracks (not empty)
                has_existing_tracks = False
                for existing_playlist in existing_playlists:
                    existing_track_ids = [track['id'] for track in self.get_playlist_tracks_sync(existing_playlist['Id'])]
                    if existing_track_ids:
                        has_existing_tracks = True
                        break
                
                # If existing playlists have tracks and new track IDs are valid, keep existing
                if has_existing_tracks:
                    self.logger.info(f"Playlist '{title}' already exists with tracks, keeping existing and deleting duplicates")
                    # Delete any other duplicates with the same name
                    for other_playlist in existing_playlists:
                        other_track_ids = [track['id'] for track in self.get_playlist_tracks_sync(other_playlist['Id'])]
                        if not other_track_ids:  # Delete empty duplicates
                            self.logger.info(f"Deleting empty duplicate playlist '{title}' (ID: {other_playlist['Id']})")
                            self.delete_playlist_sync(other_playlist['Id'])
                    return True
                
                # No existing playlist has tracks, delete all existing ones and create new
                self.logger.info(f"Playlist '{title}' has no existing tracks, deleting all existing and creating new one")
                for existing_playlist in existing_playlists:
                    self.logger.info(f"Deleting existing playlist '{title}' (ID: {existing_playlist['Id']})")
                    if not self.delete_playlist_sync(existing_playlist['Id']):
                        self.logger.error(f"Failed to delete existing playlist {existing_playlist['Id']}")
                        return False

                # Wait a moment for deletions to complete
                import time
                time.sleep(2)

            self.logger.info(f"Creating new playlist '{title}'")
            return self.create_playlist_sync(title, valid_track_ids, summary)

        except Exception as e:
            self.logger.error(f"Error creating or updating playlist '{title}': {e}")
            return False
    
    def sync_playlist(self, title: str, tracks: List[Dict[str, Any]], summary: str = "", **kwargs) -> Dict[str, Any]:
        """
        Sync a playlist - create new or update existing
        Returns statistics about the operation
        """
        try:
            # Extract kwargs
            cleanup = kwargs.get('cleanup', True)
            empty_playlist_cleanup = kwargs.get('empty_playlist_cleanup', True)
            
            self.logger.info(f"Starting playlist sync for '{title}'")
            self.logger.debug(f"Received {len(tracks)} tracks to search for")
            
            # Find tracks in Jellyfin
            found_tracks = []
            unmatched_tracks = []
            self.logger.debug(f"Searching for {len(tracks)} tracks in Jellyfin library")
            for i, track in enumerate(tracks):
                try:
                    # ListenBrainz uses 'track' key for track title, not 'title'
                    track_title = track.get('track', track.get('title', 'Unknown Title'))
                    track_album = track.get('album', '')
                    self.logger.info(f"[{i+1}/{len(tracks)}] Searching: '{track['artist']}' - '{track_title}'")
                    jellyfin_track = self.find_track_by_artist_and_title_sync(track['artist'], track_title, track_album)
                    if jellyfin_track:
                        found_tracks.append(jellyfin_track)
                        self.logger.info(f"[{i+1}/{len(tracks)}] ✅ '{jellyfin_track['artist']}' - '{jellyfin_track['name']}'")
                    else:
                        unmatched_tracks.append(f"{track['artist']} - {track_title}")
                        self.logger.info(f"[{i+1}/{len(tracks)}] ❌ '{track['artist']}' - '{track_title}'")
                except Exception as e:
                    unmatched_tracks.append(f"{track.get('artist', 'Unknown')} - {track.get('track', track.get('title', 'Unknown'))}")
                    self.logger.error(f"Error searching for track {i+1}: {e}")
                    continue
            
            # Check if we should create empty playlist
            if not found_tracks and empty_playlist_cleanup:
                self.logger.info(f"Empty playlist cleanup enabled - will not create empty playlist '{title}'")
                return {
                    'success': True,
                    'action': 'skipped_empty',
                    'total_tracks': len(tracks),
                    'found_tracks': 0,
                    'unmatched_tracks': unmatched_tracks,
                    'message': f"Skipped creating empty playlist '{title}'"
                }
            
            # Get track IDs
            track_ids = [track['id'] for track in found_tracks]
            
            # Use the create_or_update_playlist_sync method for proper playlist management
            success = self.create_or_update_playlist_sync(title, track_ids, summary)
            
            if success:
                # Always report the actual tracks that were processed (like Plex does)
                match_rate = (len(found_tracks) / len(tracks) * 100) if len(tracks) > 0 else 0
                self.logger.info(f"Successfully synced playlist '{title}': {len(found_tracks)}/{len(tracks)} tracks ({match_rate:.1f}% success rate)")
                return {
                    'success': True,
                    'action': 'synced',
                    'total_tracks': len(tracks),
                    'found_tracks': len(found_tracks),
                    'unmatched_tracks': unmatched_tracks,
                    'message': f"Successfully synced playlist '{title}' with {len(found_tracks)} tracks"
                }
            else:
                return {
                    'success': False,
                    'action': 'failed',
                    'total_tracks': len(tracks),
                    'found_tracks': len(found_tracks),
                    'unmatched_tracks': unmatched_tracks,
                    'message': f"Failed to sync playlist '{title}'"
                }
                
        except Exception as e:
            import traceback
            self.logger.error(f"Failed to sync playlist '{title}': {e}")
            self.logger.error(f"Full traceback: {traceback.format_exc()}")
            return {
                'success': False,
                'action': 'failed',
                'total_tracks': len(tracks),
                'found_tracks': 0,
                'unmatched_tracks': [f"{track.get('artist', 'Unknown')} - {track.get('track', track.get('title', 'Unknown'))}" for track in tracks],
                'message': f"Failed to sync playlist '{title}': {str(e)}"
            }
    
    # ==== LIBRARY CACHE INTERFACE METHODS ====
    # Required by LibraryCacheManager for optimization
    
    def build_library_cache(self, library_key: str = None) -> Dict[str, Any]:
        """
        Build optimized library cache for Jellyfin music library
        
        Returns cache data with structure:
        {
            "library_key": "music_library_id",
            "total_tracks": 45000,
            "tracks": [...],  # Minimal track data only
            "artist_index": {...},  # Direct artist -> track_ids mapping
            "track_index": {...}   # Direct track title -> track_ids mapping
        }
        """
        try:
            self.logger.info(f"Building optimized library cache for Jellyfin library {library_key or 'default'}...")
            start_time = time.time()
            
            # Get all music items from Jellyfin
            params = {
                'IncludeItemTypes': 'Audio',
                'Recursive': 'true',
                'UserId': self.user_id,
                'Limit': 1000  # Start with reasonable batch size
            }
            
            all_tracks = []
            start_index = 0
            
            while True:
                params['StartIndex'] = start_index
                response = self._get_sync("/Items", params=params)
                
                if not response or 'Items' not in response:
                    break
                
                items = response['Items']
                if not items:
                    break
                
                # Process tracks
                for item in items:
                    if item.get('Type') == 'Audio':
                        track_data = {
                            'id': item.get('Id'),
                            'name': item.get('Name'),
                            'artist': item.get('AlbumArtist', 
                                       item.get('Artists', ['Unknown'])[0] if item.get('Artists') and len(item.get('Artists', [])) > 0 else 'Unknown'),
                            'album': item.get('Album', 'Unknown'),
                            'duration': item.get('RunTimeTicks', 0) // 10000000 if item.get('RunTimeTicks') else 0,
                            'path': item.get('Path'),
                            'year': item.get('ProductionYear')
                        }
                        
                        # Skip tracks with missing essential data
                        if track_data['id'] and track_data['name'] and track_data['artist']:
                            all_tracks.append(track_data)
                
                # Check if we have more items
                total_records = response.get('TotalRecordCount', 0)
                if start_index + len(items) >= total_records:
                    break
                
                start_index += len(items)
                self.logger.debug(f"Processed {start_index}/{total_records} tracks...")
            
            if not all_tracks:
                self.logger.warning("No tracks found in Jellyfin library")
                return {}
            
            # Build optimized cache structure
            cache_data = {
                "library_key": library_key or "default",
                "total_tracks": len(all_tracks),
                "tracks": all_tracks,
                "artist_index": {},
                "track_index": {},
                "built_at": time.time()
            }
            
            # Create optimized search indexes (direct mappings)
            self._build_optimized_indexes(cache_data)
            
            build_time = time.time() - start_time
            self.logger.info(f"Built Jellyfin library cache: {len(all_tracks):,} tracks in {build_time:.1f}s")
            
            return cache_data
            
        except Exception as e:
            self.logger.error(f"Failed to build Jellyfin library cache: {e}")
            return {}
    
    def _build_optimized_indexes(self, cache_data: Dict[str, Any]) -> None:
        """Build optimized search indexes for fast lookups"""
        try:
            tracks = cache_data.get('tracks', [])
            artist_index = {}
            track_index = {}
            
            for track in tracks:
                track_id = track.get('id')
                artist_raw = track.get('artist', '')
                track_name_raw = track.get('name', '')
                
                # Safely handle None values and convert to strings
                artist = str(artist_raw).lower().strip() if artist_raw is not None else ''
                track_name = str(track_name_raw).lower().strip() if track_name_raw is not None else ''
                
                if track_id and artist:
                    if artist not in artist_index:
                        artist_index[artist] = []
                    artist_index[artist].append(track_id)
                
                if track_id and track_name:
                    if track_name not in track_index:
                        track_index[track_name] = []
                    track_index[track_name].append(track_id)
            
            cache_data['artist_index'] = artist_index
            cache_data['track_index'] = track_index
            
            self.logger.debug(f"Built indexes: {len(artist_index)} artists, {len(track_index)} tracks")
            
        except Exception as e:
            self.logger.error(f"Failed to build optimized indexes: {e}")
    
    def process_cached_library(self, cached_data: Dict[str, Any]) -> Dict[str, Any]:
        """Process cached library data for use (no transformation needed for Jellyfin)"""
        return cached_data
    
    def search_cached_library(self, track_name: str, artist_name: str, cached_data: Dict[str, Any], album_name: str = "") -> Optional[str]:
        """
        Ultra-fast search in optimized cached library data with album scoring
        
        Returns:
            Track ID if found, None otherwise
        """
        try:
            tracks = cached_data.get('tracks', [])
            artist_index = cached_data.get('artist_index', {})
            track_index = cached_data.get('track_index', {})
            
            # Normalize search terms (safely handle None values)
            artist_key = str(artist_name).lower().strip() if artist_name is not None else ''
            track_key = str(track_name).lower().strip() if track_name is not None else ''
            album_key = str(album_name).lower().strip() if album_name is not None else ''
            
            # Strategy 1: Exact match with album bonus
            if artist_key in artist_index and track_key in track_index:
                artist_tracks = set(artist_index[artist_key])
                track_tracks = set(track_index[track_key])
                intersection = artist_tracks.intersection(track_tracks)
                
                if intersection:
                    # If we have album info, score the matches
                    if album_key:
                        best_match = None
                        best_score = 0
                        for track_id in intersection:
                            # Find the track data
                            track_data = next((t for t in tracks if t['id'] == track_id), None)
                            if track_data:
                                album_score = 0
                                if track_data.get('album'):
                                    track_album_norm = self._normalize_text(track_data['album'])
                                    if track_album_norm == album_key:
                                        album_score = 1.0  # Exact album match
                                    elif album_key in track_album_norm or track_album_norm in album_key:
                                        album_score = 0.7  # Partial album match
                                    elif self._fuzzy_match(album_key, track_album_norm):
                                        album_score = 0.5  # Fuzzy album match
                                
                                if album_score > best_score:
                                    best_score = album_score
                                    best_match = track_id
                        
                        if best_match:
                            return best_match
                    
                    # Fallback to first match if no album scoring
                    return list(intersection)[0]
            
            # Strategy 2: Fuzzy matching with album scoring
            best_match = None
            best_score = 0
            
            # Try fuzzy matching on artist
            for cached_artist in artist_index:
                if self._fuzzy_match(artist_key, cached_artist):
                    artist_tracks = set(artist_index[cached_artist])
                    if track_key in track_index:
                        track_tracks = set(track_index[track_key])
                        intersection = artist_tracks.intersection(track_tracks)
                        if intersection:
                            # Score matches with album bonus
                            for track_id in intersection:
                                track_data = next((t for t in tracks if t['id'] == track_id), None)
                                if track_data:
                                    score = 0.8  # Base score for fuzzy artist match
                                    
                                    # Add album bonus
                                    if album_key and track_data.get('album'):
                                        track_album_norm = self._normalize_text(track_data['album'])
                                        if track_album_norm == album_key:
                                            score += 0.2  # Album bonus
                                        elif album_key in track_album_norm or track_album_norm in album_key:
                                            score += 0.1  # Partial album bonus
                                    
                                    if score > best_score:
                                        best_score = score
                                        best_match = track_id
            
            # Try fuzzy matching on track name
            for cached_track in track_index:
                if self._fuzzy_match(track_key, cached_track):
                    track_tracks = set(track_index[cached_track])
                    if artist_key in artist_index:
                        artist_tracks = set(artist_index[artist_key])
                        intersection = artist_tracks.intersection(track_tracks)
                        if intersection:
                            # Score matches with album bonus
                            for track_id in intersection:
                                track_data = next((t for t in tracks if t['id'] == track_id), None)
                                if track_data:
                                    score = 0.8  # Base score for fuzzy track match
                                    
                                    # Add album bonus
                                    if album_key and track_data.get('album'):
                                        track_album_norm = self._normalize_text(track_data['album'])
                                        if track_album_norm == album_key:
                                            score += 0.2  # Album bonus
                                        elif album_key in track_album_norm or track_album_norm in album_key:
                                            score += 0.1  # Partial album bonus
                                    
                                    if score > best_score:
                                        best_score = score
                                        best_match = track_id
            
            return best_match
            
        except Exception as e:
            self.logger.error(f"Failed to search cached library: {e}")
            return None
    
    def _fuzzy_match(self, search_term: str, cached_term: str) -> bool:
        """Simple fuzzy matching for artist/track names"""
        if not search_term or not cached_term:
            return False
        
        # Exact match
        if search_term == cached_term:
            return True
        
        # Contains match
        if search_term in cached_term or cached_term in search_term:
            return True
        
        # Word boundary match (handle "The Beatles" vs "Beatles")
        search_words = set(search_term.split())
        cached_words = set(cached_term.split())
        
        # If most words match, consider it a match
        if len(search_words) > 0 and len(cached_words) > 0:
            overlap = len(search_words.intersection(cached_words))
            return overlap >= min(len(search_words), len(cached_words)) * 0.7
        
        return False
    
    def verify_track_exists(self, track_id: str) -> bool:
        """
        Verify that a track still exists in Jellyfin (for cache validation)
        
        Returns:
            True if track exists, False otherwise
        """
        try:
            response = self._get_sync(f"/Items/{track_id}")
            return response is not None and response.get('Id') == track_id
        except Exception as e:
            self.logger.debug(f"Track verification failed for {track_id}: {e}")
            return False
    
    def validate_playlist_exists(self, title: str) -> Dict[str, Any]:
        """
        Validate if a playlist exists and return detailed information about it.
        Returns dict with 'exists', 'count', 'playlists', 'total_tracks', 'track_inventory'
        """
        try:
            existing_playlists = self.find_all_playlists_by_name_sync(title)
            
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
            all_track_ids = set()
            
            for playlist in existing_playlists:
                playlist_id = playlist.get('Id', '')
                tracks = self.get_playlist_tracks_sync(playlist_id)
                track_ids = [track['id'] for track in tracks if track.get('id')]
                
                playlist_details.append({
                    'id': playlist_id,
                    'name': playlist.get('Name', ''),
                    'track_count': len(tracks),
                    'track_ids': track_ids
                })
                
                total_tracks += len(tracks)
                all_track_ids.update(track_ids)
            
            return {
                'exists': True,
                'count': len(existing_playlists),
                'playlists': playlist_details,
                'total_tracks': total_tracks,
                'track_inventory': all_track_ids
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
    
    def compare_playlist_content(self, title: str, new_track_ids: List[str]) -> Dict[str, Any]:
        """
        Compare new track IDs with existing playlist content.
        Returns dict with 'identical', 'similar', 'different', 'recommendation'
        """
        try:
            validation = self.validate_playlist_exists(title)
            
            if not validation['exists']:
                return {
                    'identical': False,
                    'similar': False,
                    'different': True,
                    'recommendation': 'create_new',
                    'existing_tracks': 0,
                    'new_tracks': len(new_track_ids),
                    'overlap': 0
                }
            
            # Check if any existing playlist has identical content
            new_track_set = set(new_track_ids)
            for playlist in validation['playlists']:
                existing_track_set = set(playlist['track_ids'])
                if existing_track_set == new_track_set:
                    return {
                        'identical': True,
                        'similar': True,
                        'different': False,
                        'recommendation': 'skip_creation',
                        'existing_tracks': len(existing_track_set),
                        'new_tracks': len(new_track_set),
                        'overlap': len(existing_track_set)
                    }
            
            # Calculate similarity
            total_existing_tracks = validation['track_inventory']
            overlap = len(new_track_set.intersection(total_existing_tracks))
            similarity_ratio = overlap / len(new_track_set) if new_track_set else 0
            
            if similarity_ratio >= 0.8:  # 80% or more overlap
                recommendation = 'update_existing'
            elif similarity_ratio >= 0.5:  # 50% or more overlap
                recommendation = 'review_manually'
            else:
                recommendation = 'create_new'
            
            return {
                'identical': False,
                'similar': similarity_ratio >= 0.5,
                'different': similarity_ratio < 0.5,
                'recommendation': recommendation,
                'existing_tracks': len(total_existing_tracks),
                'new_tracks': len(new_track_set),
                'overlap': overlap,
                'similarity_ratio': similarity_ratio
            }
            
        except Exception as e:
            self.logger.error(f"Error comparing playlist content for '{title}': {e}")
            return {
                'identical': False,
                'similar': False,
                'different': True,
                'recommendation': 'create_new',
                'existing_tracks': 0,
                'new_tracks': len(new_track_ids),
                'overlap': 0
            }
    
    def _try_progressive_title_search(self, title: str, artist: str, normalized_artist: str, normalized_title: str) -> Optional[Dict[str, Any]]:
        """Try progressive title shortening to handle Jellyfin truncation issues"""
        self.logger.debug("🔄 Strategy 8a: Progressive title shortening...")
        
        # Split title into words and try progressively shorter versions
        title_words = title.split()
        
        for i in range(len(title_words), 0, -1):  # Start with full title, then remove words
            shortened_title = ' '.join(title_words[:i])
            if len(shortened_title) < len(title):  # Only try if actually shortened
                self.logger.debug(f"   Trying shortened title: '{shortened_title}'")
                tracks = self.search_tracks_sync(shortened_title, limit=50)
                
                if tracks:
                    # Check if any track has the correct artist
                    for track in tracks:
                        track_artist_normalized = self._normalize_text(track['artist'])
                        if self._calculate_similarity(track_artist_normalized, normalized_artist) >= 0.7:
                            self.logger.info(f"✅ Progressive title match: '{track['artist']}' - '{track['name']}' for '{artist}' - '{title}'")
                            return track
        
        return None
    
    def _try_special_character_variants(self, title: str, artist: str, normalized_artist: str, normalized_title: str, normalized_album: str = "", album: str = "") -> Optional[Dict[str, Any]]:
        """Try different special character handling for problematic titles"""
        self.logger.debug("🔄 Strategy 8b: Special character variants...")
        
        # Create variants of the title with different character handling
        variants = []
        
        # Remove commas and replace with spaces
        if ',' in title:
            variants.append(title.replace(',', ' '))
        
        # Remove quotes
        if '"' in title or "'" in title:
            variants.append(title.replace('"', '').replace("'", ''))
        
        # Replace problematic characters
        if any(char in title for char in ['&', '(', ')', '[', ']']):
            import re
            variants.append(re.sub(r'[&\(\)\[\]]', ' ', title))
        
        # Try each variant
        for variant in variants:
            if variant != title:  # Only try if different
                self.logger.debug(f"   Trying variant: '{variant}'")
                tracks = self.search_tracks_sync(variant, limit=50)
                
                if tracks:
                    match = self._find_best_match(tracks, normalized_artist, normalized_title, artist, title, normalized_album, album)
                    if match:
                        self.logger.info(f"✅ Special character variant match: '{match['artist']}' - '{match['name']}' for '{artist}' - '{title}'")
                        return match
        
        return None
    
    def _try_title_only_with_artist_validation(self, title: str, artist: str, normalized_artist: str, normalized_title: str) -> Optional[Dict[str, Any]]:
        """Search by title only, then validate artist matches"""
        self.logger.debug("🔄 Strategy 8c: Title-only search with artist validation...")
        
        # Search by title only
        tracks = self.search_tracks_sync(title, limit=100)
        
        if not tracks:
            return None
        
        self.logger.debug(f"   Found {len(tracks)} tracks with title '{title}', validating artists...")
        
        # Find best artist match
        best_match = None
        best_score = 0
        
        for track in tracks:
            track_artist_normalized = self._normalize_text(track['artist'])
            artist_score = self._calculate_similarity(track_artist_normalized, normalized_artist)
            
            if artist_score > best_score:
                best_score = artist_score
                best_match = track
        
        # Accept if artist similarity is high enough
        if best_match and best_score >= 0.6:  # Lower threshold for title-only search
            self.logger.info(f"✅ Title-only match: '{best_match['artist']}' - '{best_match['name']}' (artist similarity: {best_score:.2f})")
            return best_match
        
        return None
    
    def _try_artist_only_with_title_validation(self, title: str, artist: str, normalized_artist: str, normalized_title: str) -> Optional[Dict[str, Any]]:
        """Search by artist only, then validate title matches"""
        self.logger.debug("🔄 Strategy 8d: Artist-only search with title validation...")
        
        # Search by artist only
        tracks = self.search_tracks_sync(artist, limit=100)
        
        if not tracks:
            return None
        
        self.logger.debug(f"   Found {len(tracks)} tracks with artist '{artist}', validating titles...")
        
        # Find best title match
        best_match = None
        best_score = 0
        
        for track in tracks:
            track_title_normalized = self._normalize_text(track['name'])
            title_score = self._calculate_similarity(track_title_normalized, normalized_title)
            
            if title_score > best_score:
                best_score = title_score
                best_match = track
        
        # Accept if title similarity is high enough
        if best_match and best_score >= 0.6:  # Lower threshold for artist-only search
            self.logger.info(f"✅ Artist-only match: '{best_match['artist']}' - '{best_match['name']}' (title similarity: {best_score:.2f})")
            return best_match
        
        return None
    
    def _truncate_title_for_search(self, title: str, max_length: int) -> str:
        """Truncate title to fit within max_length while preserving word boundaries"""
        if len(title) <= max_length:
            return title
        
        # Try to truncate at word boundaries
        words = title.split()
        truncated = ""
        
        for word in words:
            if len(truncated + word) + 1 <= max_length:  # +1 for space
                truncated += word + " "
            else:
                break
        
        # Remove trailing space and ensure we have something
        truncated = truncated.strip()
        if not truncated:
            truncated = title[:max_length].strip()
        
        self.logger.debug(f"Truncated '{title}' to '{truncated}' (max {max_length} chars)")
        return truncated
    
    def _try_title_only_search_with_validation(self, title: str, artist: str, normalized_artist: str, normalized_title: str) -> Optional[Dict[str, Any]]:
        """Search by title only, then validate artist matches"""
        self.logger.debug(f"   Searching by title only: '{title}'")
        
        # Search by title only
        tracks = self.search_tracks_sync(title, limit=50)
        
        if not tracks:
            self.logger.debug(f"   Title-only search returned 0 results")
            return None
        
        self.logger.debug(f"   Found {len(tracks)} tracks with title '{title}', validating artists...")
        
        # Find best artist match
        best_match = None
        best_score = 0
        
        for track in tracks:
            track_artist_normalized = self._normalize_text(track['artist'])
            artist_score = self._calculate_similarity(track_artist_normalized, normalized_artist)
            
            if artist_score > best_score:
                best_score = artist_score
                best_match = track
        
        # Accept if artist similarity is high enough
        if best_match and best_score >= 0.7:  # Higher threshold for title-only search
            self.logger.info(f"✅ Title-only match: '{best_match['artist']}' - '{best_match['name']}' (artist similarity: {best_score:.2f})")
            return best_match
        
        return None
    
    def _try_progressive_title_word_removal(self, title: str, artist: str, normalized_artist: str, normalized_title: str) -> Optional[Dict[str, Any]]:
        """Progressively remove words from title until we get search results"""
        self.logger.debug(f"   Trying progressive title word removal for: '{title}'")
        
        words = title.split()
        if len(words) <= 1:
            self.logger.debug(f"   Title '{title}' has only {len(words)} word(s), skipping progressive removal")
            return None
        
        # Try removing words from the end first (most common case)
        for i in range(len(words) - 1, 0, -1):  # Start with removing 1 word, then 2, etc.
            shortened_title = ' '.join(words[:i])
            if len(shortened_title) < 3:  # Skip very short titles
                continue
                
            self.logger.debug(f"   Trying shortened title: '{shortened_title}'")
            
            # Search with shortened title
            tracks = self.search_tracks_sync(shortened_title, limit=50)
            
            if tracks:
                self.logger.debug(f"   Found {len(tracks)} tracks with shortened title '{shortened_title}'")
                
                # Find best artist match
                best_match = None
                best_score = 0
                
                for track in tracks:
                    track_artist_normalized = self._normalize_text(track['artist'])
                    artist_score = self._calculate_similarity(track_artist_normalized, normalized_artist)
                    
                    if artist_score > best_score:
                        best_score = artist_score
                        best_match = track
                
                # Accept if artist similarity is high enough
                if best_match and best_score >= 0.7:
                    self.logger.info(f"✅ Progressive word removal match: '{best_match['artist']}' - '{best_match['name']}' (artist similarity: {best_score:.2f})")
                    return best_match
            else:
                self.logger.debug(f"   No results for shortened title: '{shortened_title}'")
        
        return None
