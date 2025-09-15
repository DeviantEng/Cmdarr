#!/usr/bin/env python3
"""
ListenBrainz API Client with SQLite caching
Refactored to use BaseAPIClient for reduced code duplication
"""

import aiohttp
from typing import List, Dict, Any, Optional
from urllib.parse import urlencode
from .client_base import BaseAPIClient


class ListenBrainzClient(BaseAPIClient):
    """Client for ListenBrainz API operations"""
    
    def __init__(self, config):
        # Headers for authenticated requests
        headers = {
            'Authorization': f'Token {config.get("LISTENBRAINZ_TOKEN", "")}',
            'Content-Type': 'application/json'
        }
        
        super().__init__(
            config=config,
            client_name='listenbrainz',
            base_url="https://api.listenbrainz.org/1/",
            rate_limit=5.0,  # Conservative rate limiting
            headers=headers
        )
    
    def _get_cache_key(self, username: str, playlist_type: str) -> str:
        """Generate cache key for ListenBrainz requests"""
        # For curated playlists, include date to ensure daily playlists are fresh
        if playlist_type == 'curated_playlists':
            from datetime import datetime
            date_str = datetime.now().strftime('%Y-%m-%d')
            return f"playlist:{username}:{playlist_type}:{date_str}"
        else:
            return f"playlist:{username}:{playlist_type}"
    
    async def _make_request(self, endpoint: str, params: Dict[str, str] = None) -> Optional[Dict[str, Any]]:
        """Make rate-limited HTTP request to ListenBrainz API using HTTP utilities"""
        # Ensure session exists
        if not self.session:
            self.session = aiohttp.ClientSession(headers=self.headers)
        
        # Use the request builder for cleaner code
        builder = self._create_request_builder()
        
        return await (builder
                     .endpoint(endpoint)
                     .params(**(params or {}))
                     .execute(self.session))
    
    async def get_user_playlists(self, username: str) -> List[Dict[str, Any]]:
        """Get all playlists for a user"""
        try:
            # Check cache first
            cache_key = f"user_playlists:{username}"
            if self.cache_enabled and self.cache:
                cached_result = self.cache.get(cache_key, 'listenbrainz')
                if cached_result is not None:
                    self.logger.debug(f"Cache hit for user playlists: {username}")
                    return cached_result
            
            response = await self._make_request(f"user/{username}/playlists")
            
            if not response or 'playlists' not in response:
                self.logger.warning(f"No playlists found for user: {username}")
                return []
            
            playlists = response['playlists']
            
            # Cache the result
            if self.cache_enabled and self.cache:
                self.cache.set(cache_key, 'listenbrainz', playlists, self.config.get('CACHE_LISTENBRAINZ_TTL_DAYS', 3))
            
            self.logger.debug(f"Found {len(playlists)} playlists for user: {username}")
            return playlists
            
        except Exception as e:
            self.logger.error(f"Error getting playlists for user {username}: {e}")
            return []
    
    async def get_user_recommendation_playlists(self, username: str) -> List[Dict[str, Any]]:
        """Get recommendation playlists created for a user (Weekly Discovery, Daily Jams, etc.)"""
        try:
            all_playlists = []
            offset = 0
            count = 50
            
            while True:
                params = {"count": str(count), "offset": str(offset)}
                response = await self._make_request(f"user/{username}/playlists/createdfor", params)
                
                if not response or 'playlists' not in response:
                    break
                
                playlists = response['playlists']
                if not playlists:
                    break
                    
                all_playlists.extend(playlists)
                
                # Check if we've got all playlists
                if len(playlists) < count:
                    break
                    
                offset += count
            
            self.logger.debug(f"Found {len(all_playlists)} recommendation playlists for user: {username}")
            return all_playlists
            
        except Exception as e:
            self.logger.error(f"Error getting recommendation playlists for user {username}: {e}")
            return []
    
    async def get_curated_playlists(self, username: str) -> Dict[str, Optional[Dict[str, Any]]]:
        """
        Get all three curated playlists for a user: Weekly Exploration, Weekly Jams, Daily Jams
        
        Returns:
            Dictionary with keys 'weekly_exploration', 'weekly_jams', 'daily_jams'
            Values are playlist dictionaries or None if not found
        """
        try:
            # Check cache first
            cache_key = self._get_cache_key(username, 'curated_playlists')
            if self.cache_enabled and self.cache:
                cached_result = self.cache.get(cache_key, 'listenbrainz')
                if cached_result is not None:
                    self.logger.debug(f"Cache hit for curated playlists: {username}")
                    return cached_result
            
            # Get system-generated playlists (created for user)
            rec_playlists = await self.get_user_recommendation_playlists(username)
            
            # Initialize result dictionary
            curated_playlists = {
                'weekly_exploration': None,
                'weekly_jams': None,
                'daily_jams': None
            }
            
            # Search for each curated playlist type
            for playlist_wrapper in rec_playlists:
                # Extract the actual playlist data from the wrapper
                playlist = playlist_wrapper.get("playlist", {})
                title = playlist.get("title", "").lower()
                
                # Identify playlist types based on title
                if any(term in title for term in ["weekly exploration", "weekly discovery"]):
                    if curated_playlists['weekly_exploration'] is None:
                        # Get full playlist details with tracks
                        full_playlist = await self._get_full_playlist_from_identifier(playlist)
                        curated_playlists['weekly_exploration'] = full_playlist
                        self.logger.debug(f"Found Weekly Exploration playlist: {playlist.get('title')}")
                
                elif "weekly jams" in title:
                    if curated_playlists['weekly_jams'] is None:
                        # Get full playlist details with tracks
                        full_playlist = await self._get_full_playlist_from_identifier(playlist)
                        curated_playlists['weekly_jams'] = full_playlist
                        self.logger.debug(f"Found Weekly Jams playlist: {playlist.get('title')}")
                
                elif "daily jams" in title:
                    if curated_playlists['daily_jams'] is None:
                        # Get full playlist details with tracks
                        full_playlist = await self._get_full_playlist_from_identifier(playlist)
                        curated_playlists['daily_jams'] = full_playlist
                        self.logger.debug(f"Found Daily Jams playlist: {playlist.get('title')}")
            
            # Count found playlists
            found_count = sum(1 for playlist in curated_playlists.values() if playlist is not None)
            self.logger.info(f"Found {found_count}/3 curated playlists for user: {username}")
            
            # Cache the result
            if self.cache_enabled and self.cache:
                self.cache.set(cache_key, 'listenbrainz', curated_playlists, self.config.get('CACHE_LISTENBRAINZ_TTL_DAYS', 3))
            
            return curated_playlists
            
        except Exception as e:
            self.logger.error(f"Error getting curated playlists for {username}: {e}")
            return {
                'weekly_exploration': None,
                'weekly_jams': None,
                'daily_jams': None
            }
    
    async def _get_full_playlist_from_identifier(self, playlist: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Get full playlist details from a playlist with identifier"""
        try:
            playlist_identifier = playlist.get('identifier', '')
            if not playlist_identifier:
                self.logger.error("Could not extract playlist identifier")
                return None
            
            # Extract MBID from identifier URL
            playlist_mbid = playlist_identifier.split('/')[-1] if '/' in playlist_identifier else playlist_identifier
            
            # Get full playlist details
            return await self.get_playlist_details(playlist_mbid)
            
        except Exception as e:
            self.logger.error(f"Error getting full playlist details: {e}")
            return None
    
    async def get_discovery_playlist(self, username: str) -> Optional[Dict[str, Any]]:
        """Find and return the Weekly Discovery playlist for a user (legacy method)"""
        try:
            curated = await self.get_curated_playlists(username)
            return curated.get('weekly_exploration')
        except Exception as e:
            self.logger.error(f"Error getting Weekly Discovery playlist for {username}: {e}")
            return None
    
    async def get_playlist_details(self, playlist_mbid: str) -> Optional[Dict[str, Any]]:
        """Get detailed playlist information including tracks"""
        try:
            response = await self._make_request(f"playlist/{playlist_mbid}")
            
            if not response or 'playlist' not in response:
                self.logger.warning(f"Playlist not found: {playlist_mbid}")
                return None
            
            playlist = response['playlist']
            track_count = len(playlist.get('track', []))
            
            self.logger.debug(f"Retrieved playlist '{playlist.get('title', 'Unknown')}' with {track_count} tracks")
            return playlist
            
        except Exception as e:
            self.logger.error(f"Error getting playlist details for {playlist_mbid}: {e}")
            return None
    
    async def extract_tracks_from_playlist(self, playlist: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Extract tracks from playlist in format suitable for music players
        
        Returns:
            List of track dictionaries with 'artist', 'album', 'track', 'mbid' keys
        """
        try:
            tracks = []
            
            playlist_tracks = playlist.get('track', [])
            self.logger.info(f"Processing {len(playlist_tracks)} tracks from playlist '{playlist.get('title', 'Unknown')}'")
            
            for track in playlist_tracks:
                # Get basic track information
                track_title = track.get('title', '')
                artist_name = track.get('creator', '')
                
                # Extract additional metadata from extension data
                album_name = ''
                artist_mbid = None
                track_mbid = None
                
                if 'extension' in track:
                    mb_track_data = track['extension'].get('https://musicbrainz.org/doc/jspf#track', {})
                    additional_metadata = mb_track_data.get('additional_metadata', {})
                    
                    # Get album name
                    album_name = additional_metadata.get('release_name', '')
                    
                    # Get track MBID
                    track_mbid = additional_metadata.get('track_mbid')
                    
                    # Get artist MBID from artists list
                    artists_list = additional_metadata.get('artists', [])
                    if artists_list and len(artists_list) > 0:
                        artist_mbid = artists_list[0].get('artist_mbid')
                
                # Skip if no essential data
                if not track_title or not artist_name:
                    self.logger.debug(f"Skipping track with missing essential data")
                    continue
                
                tracks.append({
                    'artist': artist_name,
                    'album': album_name,
                    'track': track_title,
                    'artist_mbid': artist_mbid,
                    'track_mbid': track_mbid,
                    'source': 'listenbrainz'
                })
            
            self.logger.info(f"Extracted {len(tracks)} valid tracks from playlist")
            return tracks
            
        except Exception as e:
            self.logger.error(f"Error extracting tracks from playlist: {e}")
            return []
    
    async def extract_artists_from_playlist(self, playlist: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Extract unique artists from playlist tracks with MBIDs (legacy method for discovery)"""
        try:
            artists = []
            seen_mbids = set()
            skipped_no_mbid = 0
            
            tracks = playlist.get('track', [])
            self.logger.info(f"Processing {len(tracks)} tracks from playlist '{playlist.get('title', 'Unknown')}'")
            
            for track in tracks:
                # Get artist information from track
                artist_name = track.get('creator', '')
                
                # Extract MBID from track extension data (ListenBrainz format)
                artist_mbid = None
                if 'extension' in track:
                    mb_track_data = track['extension'].get('https://musicbrainz.org/doc/jspf#track', {})
                    additional_metadata = mb_track_data.get('additional_metadata', {})
                    artists_list = additional_metadata.get('artists', [])
                    
                    if artists_list and len(artists_list) > 0:
                        # Take the first artist's MBID
                        artist_mbid = artists_list[0].get('artist_mbid')
                
                # Skip if no artist name
                if not artist_name:
                    continue
                
                # Skip if no MBID (unexpected for ListenBrainz)
                if not artist_mbid:
                    skipped_no_mbid += 1
                    self.logger.debug(f"Skipping artist '{artist_name}' - no MBID found (unexpected)")
                    continue
                
                # Skip if we've already seen this artist MBID
                if artist_mbid in seen_mbids:
                    continue
                
                seen_mbids.add(artist_mbid)
                
                artists.append({
                    'name': artist_name,
                    'mbid': artist_mbid,
                    'track_title': track.get('title', ''),
                    'source': 'listenbrainz_weekly_exploration'
                })
            
            if skipped_no_mbid > 0:
                self.logger.warning(f"Skipped {skipped_no_mbid} artists without MBIDs (this is unexpected for ListenBrainz)")
            
            self.logger.info(f"Extracted {len(artists)} unique artists with MBIDs from playlist")
            
            return artists
            
        except Exception as e:
            self.logger.error(f"Error extracting artists from playlist: {e}")
            return []
    
    async def test_connection(self) -> bool:
        """Test connection to ListenBrainz API"""
        try:
            self.logger.info("Testing connection to ListenBrainz API...")
            
            # Test with a simple API call
            response = await self._make_request("stats/sitewide/artists")
            
            if response and 'payload' in response:
                self.logger.info("Connected to ListenBrainz API successfully")
                return True
            else:
                self.logger.error("ListenBrainz API test failed - no valid response")
                return False
                
        except Exception as e:
            self.logger.error(f"Failed to connect to ListenBrainz API: {e}")
            return False
    
    async def get_api_stats(self) -> Dict[str, Any]:
        """Get basic API usage statistics"""
        stats = await super().get_api_stats()
        stats.update({
            'username': self.config.LISTENBRAINZ_USERNAME,
        })
        return stats