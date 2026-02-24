#!/usr/bin/env python3
"""
Deezer API Client
Handles authentication and playlist operations for Deezer
"""

import aiohttp
import json
import time
from typing import Dict, List, Optional, Any
from urllib.parse import urlencode

from .client_base import BaseAPIClient
from utils.playlist_parser import parse_playlist_url


class DeezerClient(BaseAPIClient):
    """Client for Deezer API operations"""
    
    def __init__(self, config):
        super().__init__(
            config=config,
            client_name='deezer',
            base_url='https://api.deezer.com',
            rate_limit=50.0,  # Deezer allows 50 requests per 5 seconds
            headers={}
        )
        
        self.app_id = config.DEEZER_APP_ID if hasattr(config, 'DEEZER_APP_ID') else None
        self.app_secret = config.DEEZER_APP_SECRET if hasattr(config, 'DEEZER_APP_SECRET') else None
        self.access_token = None
        self.token_expires_at = 0
        
        # Deezer public API doesn't require authentication
        self.logger.info("Deezer client initialized - public API access enabled")
    
    async def _get_access_token(self) -> bool:
        """Get Deezer access token - not required for public playlists"""
        # Deezer allows public access to playlists without authentication
        # We'll use a simple identifier for logging purposes
        self.access_token = "public_access"
        self.token_expires_at = time.time() + (24 * 60 * 60)  # 24 hours
        
        self.logger.info("Using public access for Deezer playlists (no authentication required)")
        return True
    
    async def _ensure_valid_token(self) -> bool:
        """Ensure we have a valid access token"""
        if not self.access_token or time.time() >= self.token_expires_at:
            return await self._get_access_token()
        return True
    
    async def _make_request(self, endpoint: str, params: Dict[str, str] = None, 
                           method: str = 'GET', **kwargs) -> Optional[Dict[str, Any]]:
        """Override to handle Deezer public API (no authentication required)"""
        # Deezer public API doesn't require authentication
        # We can make requests directly without access tokens
        
        # Call parent method
        return await super()._make_request(endpoint, params, method, **kwargs)
    
    async def get_playlist_info(self, url: str) -> Dict[str, Any]:
        """
        Get playlist metadata from Deezer URL
        
        Args:
            url: Deezer playlist URL
            
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
            
            # Fetch playlist info from Deezer
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
            result = await self._get(f"/playlist/{playlist_id}")
            
            if result and not result.get('error'):
                return {
                    'success': True,
                    'name': result.get('title', 'Unknown Playlist'),
                    'description': result.get('description', ''),
                    'owner': result.get('creator', {}).get('name', 'Unknown'),
                    'track_count': result.get('nb_tracks', 0),
                    'playlist_id': playlist_id,
                    'public': True,  # Deezer playlists are generally public
                    'collaborative': False,  # Deezer doesn't have collaborative playlists
                    'fans': result.get('fans', 0),
                    'duration': result.get('duration', 0)
                }
            else:
                error_msg = result.get('error', {}).get('message', 'Unknown error') if result else 'No response'
                return {
                    'success': False,
                    'error': f'Failed to fetch playlist from Deezer: {error_msg}'
                }
                
        except Exception as e:
            self.logger.error(f"Error fetching playlist info: {e}")
            return {
                'success': False,
                'error': f"Failed to fetch playlist: {str(e)}"
            }
    
    async def get_playlist_tracks(self, url: str) -> Dict[str, Any]:
        """
        Get all tracks from a Deezer playlist
        
        Args:
            url: Deezer playlist URL
            
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
            
            # Fetch tracks from Deezer using the async method
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
            index = 0
            limit = 25  # Deezer's max per request
            
            while True:
                params = {
                    'limit': limit,
                    'index': index
                }
                
                result = await self._get(f"/playlist/{playlist_id}/tracks", params=params)
                
                if not result or result.get('error'):
                    break
                
                tracks = result.get('data', [])
                if not tracks:
                    break
                
                # Process tracks
                for track in tracks:
                    if track and track.get('title'):  # Skip null tracks
                        artist = track.get('artist', {})
                        artist_name = artist.get('name', 'Unknown Artist') if artist else 'Unknown Artist'
                        
                        # Normalize text for consistent matching
                        from utils.text_normalizer import normalize_text
                        artist_name = normalize_text(artist_name)
                        track_name = normalize_text(track.get('title', 'Unknown Track'))
                        album_name = normalize_text(track.get('album', {}).get('title', 'Unknown Album'))
                        
                        all_tracks.append({
                            'artist': artist_name,
                            'track': track_name,
                            'album': album_name,
                            'duration': track.get('duration', 0),
                            'explicit_lyrics': track.get('explicit_lyrics', False)
                        })
                
                # Check if we got less than requested (end of results)
                if len(tracks) < limit:
                    break
                
                index += limit
                
                # Safety check to prevent infinite loops
                if index > 10000:  # Reasonable playlist limit
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
        """Test connection to Deezer API"""
        try:
            self.logger.info("Testing connection to Deezer API...")
            
            # Deezer public API doesn't require authentication
            # Test with a public endpoint
            result = await self._get("/track/3135556")  # "Bohemian Rhapsody" by Queen
            
            if result and not result.get('error'):
                self.logger.info("Successfully connected to Deezer API")
                return True
            else:
                error_msg = result.get('error', {}).get('message', 'Unknown error') if result else 'No response'
                self.logger.error(f"Deezer API test failed: {error_msg}")
                return False
                
        except Exception as e:
            self.logger.error(f"Failed to connect to Deezer: {e}")
            return False
        finally:
            # Ensure session is closed
            await self.close()
    
    async def get_api_stats(self) -> Dict[str, Any]:
        """Get Deezer API usage statistics"""
        stats = await super().get_api_stats()
        stats.update({
            'app_id_configured': bool(self.app_id),
            'app_secret_configured': bool(self.app_secret),
            'public_access': True,  # Deezer uses public API
            'authentication_required': False
        })
        return stats
    
    async def close(self):
        """Close HTTP session"""
        try:
            if self.session and not self.session.closed:
                await self.session.close()
        except Exception as e:
            self.logger.warning(f"Error closing Deezer client session: {e}")
        finally:
            self.session = None
    
    def __del__(self):
        """Ensure session is closed when object is destroyed"""
        try:
            if hasattr(self, 'session') and self.session and not self.session.closed:
                # Note: This is a synchronous cleanup - the session should already be closed
                # This is just a safety net for cases where async cleanup didn't happen
                pass
        except Exception:
            # Ignore errors during destruction
            pass
