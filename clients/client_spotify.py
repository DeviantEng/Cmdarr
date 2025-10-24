#!/usr/bin/env python3
"""
Spotify API Client
Handles authentication and playlist operations for Spotify
"""

import aiohttp
import base64
import json
import time
from typing import Dict, List, Optional, Any
from urllib.parse import urlencode

from .client_base import BaseAPIClient
from utils.playlist_parser import parse_playlist_url


class SpotifyClient(BaseAPIClient):
    """Client for Spotify API operations"""
    
    def __init__(self, config, execution_id=None):
        super().__init__(
            config=config,
            client_name='spotify',
            base_url='https://api.spotify.com/v1',
            rate_limit=10.0,  # Spotify allows 10 requests per second
            headers={},
            execution_id=execution_id
        )
        
        self.client_id = config.SPOTIFY_CLIENT_ID
        self.client_secret = config.SPOTIFY_CLIENT_SECRET
        self.access_token = None
        self.token_expires_at = 0
        
        if not self.client_id or not self.client_secret:
            self.logger.warning("Spotify credentials not configured")
    
    async def _get_access_token(self) -> bool:
        """Get Spotify access token using Client Credentials flow"""
        if not self.client_id or not self.client_secret:
            self.logger.error("Spotify Client ID and Secret not configured")
            return False
        
        try:
            # Prepare credentials
            credentials = f"{self.client_id}:{self.client_secret}"
            encoded_credentials = base64.b64encode(credentials.encode()).decode()
            
            # Prepare request
            url = "https://accounts.spotify.com/api/token"
            headers = {
                "Authorization": f"Basic {encoded_credentials}",
                "Content-Type": "application/x-www-form-urlencoded"
            }
            data = {
                "grant_type": "client_credentials"
            }
            
            # Ensure session exists
            if not self.session:
                self.session = aiohttp.ClientSession(headers=self.headers)
            
            # Make request
            async with self.session.post(url, headers=headers, data=data) as response:
                if response.status == 200:
                    token_data = await response.json()
                    self.access_token = token_data["access_token"]
                    expires_in = token_data["expires_in"]
                    self.token_expires_at = time.time() + expires_in - 60  # Refresh 1 minute early
                    
                    self.logger.info("Successfully obtained Spotify access token")
                    return True
                else:
                    error_text = await response.text()
                    self.logger.error(f"Failed to get Spotify access token: {response.status} - {error_text}")
                    return False
                    
        except Exception as e:
            self.logger.error(f"Error getting Spotify access token: {e}")
            return False
    
    async def _ensure_valid_token(self) -> bool:
        """Ensure we have a valid access token"""
        if not self.access_token or time.time() >= self.token_expires_at:
            return await self._get_access_token()
        return True
    
    async def _make_request(self, endpoint: str, params: Dict[str, str] = None, 
                           method: str = 'GET', **kwargs) -> Optional[Dict[str, Any]]:
        """Override to add Spotify authentication"""
        # Ensure we have a valid token
        if not await self._ensure_valid_token():
            return None
        
        # Add authorization header
        if not self.headers:
            self.headers = {}
        self.headers["Authorization"] = f"Bearer {self.access_token}"
        
        # Call parent method
        return await super()._make_request(endpoint, params, method, **kwargs)
    
    async def get_playlist_info(self, url: str) -> Dict[str, Any]:
        """
        Get playlist metadata from Spotify URL
        
        Args:
            url: Spotify playlist URL
            
        Returns:
            Dict with playlist metadata or error info
        """
        try:
            # Parse URL to get playlist ID
            parsed = parse_playlist_url(url)
            if not parsed['valid']:
                return {
                    'success': False,
                    'error': parsed['error']
                }
            
            playlist_id = parsed['playlist_id']
            
            # Fetch playlist info from Spotify
            return await self._get_playlist_info_async(playlist_id)
            
        except Exception as e:
            self.logger.error(f"Error getting playlist info: {e}")
            return {
                'success': False,
                'error': f"Failed to fetch playlist info: {str(e)}"
            }
    
    async def _get_playlist_info_async(self, playlist_id: str) -> Dict[str, Any]:
        """Async helper to get playlist info"""
        try:
            result = await self._get(f"/playlists/{playlist_id}")
            
            if result:
                return {
                    'success': True,
                    'name': result.get('name', 'Unknown Playlist'),
                    'description': result.get('description', ''),
                    'owner': result.get('owner', {}).get('display_name', 'Unknown'),
                    'track_count': result.get('tracks', {}).get('total', 0),
                    'playlist_id': playlist_id,
                    'public': result.get('public', False),
                    'collaborative': result.get('collaborative', False)
                }
            else:
                return {
                    'success': False,
                    'error': 'Failed to fetch playlist from Spotify'
                }
                
        except Exception as e:
            self.logger.error(f"Error fetching playlist info: {e}")
            return {
                'success': False,
                'error': f"Failed to fetch playlist: {str(e)}"
            }
    
    async def get_playlist_tracks(self, url: str) -> Dict[str, Any]:
        """
        Get all tracks from a Spotify playlist
        
        Args:
            url: Spotify playlist URL
            
        Returns:
            Dict with tracks list or error info
        """
        try:
            # Parse URL to get playlist ID
            parsed = parse_playlist_url(url)
            if not parsed['valid']:
                return {
                    'success': False,
                    'error': parsed['error']
                }
            
            playlist_id = parsed['playlist_id']
            
            # Fetch tracks from Spotify using the async method
            return await self._get_playlist_tracks_async(playlist_id)
            
        except Exception as e:
            self.logger.error(f"Error getting playlist tracks: {e}")
            return {
                'success': False,
                'error': f"Failed to fetch playlist tracks: {str(e)}"
            }
    
    async def _get_playlist_tracks_async(self, playlist_id: str) -> Dict[str, Any]:
        """Async helper to get all playlist tracks with pagination"""
        try:
            all_tracks = []
            offset = 0
            limit = 100  # Spotify's max per request
            
            while True:
                params = {
                    'limit': limit,
                    'offset': offset,
                    'fields': 'items(track(name,artists(name),album(name)))'
                }
                
                result = await self._get(f"/playlists/{playlist_id}/tracks", params=params)
                
                if not result:
                    break
                
                tracks = result.get('items', [])
                if not tracks:
                    break
                
                # Process tracks
                for item in tracks:
                    track = item.get('track', {})
                    if track and track.get('name'):  # Skip null tracks
                        artists = track.get('artists', [])
                        artist_name = artists[0].get('name', 'Unknown Artist') if artists else 'Unknown Artist'
                        
                        # Extract album name before normalization
                        raw_album_name = track.get('album', {}).get('name', 'Unknown Album')
                        
                        # Normalize text for consistent matching
                        from utils.text_normalizer import normalize_text
                        artist_name = normalize_text(artist_name)
                        track_name = normalize_text(track.get('name', 'Unknown Track'))
                        album_name = normalize_text(raw_album_name)
                        
                        # Debug log album extraction
                        self.logger.debug(f"🎵 SPOTIFY EXTRACT: '{track_name}' by '{artist_name}' from album '{album_name}' (raw: '{raw_album_name}')")
                        
                        all_tracks.append({
                            'artist': artist_name,
                            'track': track_name,
                            'album': album_name
                        })
                
                # Check if we got less than requested (end of results)
                if len(tracks) < limit:
                    break
                
                offset += limit
                
                # Safety check to prevent infinite loops
                if offset > 10000:  # Spotify playlist limit
                    self.logger.warning("Reached safety limit for playlist tracks")
                    break
            
            return {
                'success': True,
                'tracks': all_tracks,
                'total_tracks': len(all_tracks)
            }
            
        except Exception as e:
            self.logger.error(f"Error fetching playlist tracks: {e}")
            return {
                'success': False,
                'error': f"Failed to fetch tracks: {str(e)}"
            }
    
    async def test_connection(self) -> bool:
        """Test connection to Spotify API"""
        try:
            self.logger.info("Testing connection to Spotify API...")
            
            # Try to get access token
            if not await self._ensure_valid_token():
                self.logger.error("Failed to obtain Spotify access token")
                return False
            
            # Test with a public endpoint that works with Client Credentials
            # Using a well-known track ID to test API access
            result = await self._get("/tracks/4iV5W9uYEdYUVa79Axb7Rh")  # "Never Gonna Give You Up" by Rick Astley
            
            if result:
                self.logger.info("Successfully connected to Spotify API")
                return True
            else:
                self.logger.error("Spotify API test failed - no valid response")
                return False
                
        except Exception as e:
            self.logger.error(f"Failed to connect to Spotify: {e}")
            return False
        finally:
            # Ensure session is closed
            if self.session:
                await self.session.close()
                self.session = None
    
    async def get_api_stats(self) -> Dict[str, Any]:
        """Get Spotify API usage statistics"""
        stats = await super().get_api_stats()
        stats.update({
            'client_id_configured': bool(self.client_id),
            'client_secret_configured': bool(self.client_secret),
            'access_token_valid': bool(self.access_token and time.time() < self.token_expires_at)
        })
        return stats
    
    async def close(self):
        """Close HTTP session"""
        if self.session:
            await self.session.close()
            self.session = None
