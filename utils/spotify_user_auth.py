#!/usr/bin/env python3
"""
Spotify User Authentication Utility
Manages Spotify user authentication tokens and refresh logic
"""

import aiohttp
import base64
import time
from typing import Optional, Dict, Any
from utils.logger import get_logger


class SpotifyUserAuth:
    """
    Manage Spotify user authentication tokens.
    Handles refresh token exchange and access token caching.
    """
    
    def __init__(self, config):
        """Initialize with config service reference"""
        self.config = config
        self.client_id = config.get('SPOTIFY_CLIENT_ID')
        self.client_secret = config.get('SPOTIFY_CLIENT_SECRET')
        self.refresh_token = config.get('SPOTIFY_USER_REFRESH_TOKEN')
        self.logger = get_logger('cmdarr.spotify_user_auth')
    
    def is_configured(self) -> bool:
        """Check if user authentication is configured"""
        return bool(self.refresh_token and self.client_id and self.client_secret)
    
    async def get_valid_token(self) -> Optional[str]:
        """
        Get a valid access token, refreshing if needed.
        Returns None if not configured or refresh fails.
        """
        if not self.is_configured():
            self.logger.warning("Spotify user auth not configured")
            return None
        
        # Check if we have a cached token that's still valid
        cached_token = self.config.get('SPOTIFY_USER_ACCESS_TOKEN')
        token_expires_at = self.config.get('SPOTIFY_USER_TOKEN_EXPIRES_AT', 0)
        
        if cached_token and not self._token_is_expired(token_expires_at):
            return cached_token
        
        # Need to refresh
        self.logger.info("Refreshing Spotify user access token")
        return await self._refresh_access_token()
    
    async def _refresh_access_token(self) -> Optional[str]:
        """
        Exchange refresh token for new access token.
        Saves new token to config service.
        """
        try:
            url = "https://accounts.spotify.com/api/token"
            
            # Prepare credentials
            credentials = f"{self.client_id}:{self.client_secret}"
            encoded_credentials = base64.b64encode(credentials.encode()).decode()
            
            headers = {
                "Authorization": f"Basic {encoded_credentials}",
                "Content-Type": "application/x-www-form-urlencoded"
            }
            
            data = {
                "grant_type": "refresh_token",
                "refresh_token": self.refresh_token
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.post(url, headers=headers, data=data) as response:
                    if response.status == 200:
                        token_data = await response.json()
                        access_token = token_data["access_token"]
                        expires_in = token_data.get("expires_in", 3600)
                        
                        # Cache the new token
                        expires_at = time.time() + expires_in
                        self.config.set('SPOTIFY_USER_ACCESS_TOKEN', access_token)
                        self.config.set('SPOTIFY_USER_TOKEN_EXPIRES_AT', str(int(expires_at)))
                        
                        self.logger.info("Successfully refreshed Spotify user access token")
                        return access_token
                    else:
                        error_text = await response.text()
                        self.logger.error(f"Failed to refresh token: {response.status} - {error_text}")
                        return None
        
        except Exception as e:
            self.logger.error(f"Error refreshing Spotify token: {e}")
            return None
    
    def _token_is_expired(self, expires_at: float) -> bool:
        """Check if token is expired (with 5-minute buffer)"""
        return time.time() >= (expires_at - 300)
    
    async def test_token(self) -> Dict[str, Any]:
        """
        Test if the configured token is valid.
        Returns status dict for UI feedback.
        """
        if not self.is_configured():
            return {
                'valid': False,
                'error': 'No refresh token configured'
            }
        
        token = await self.get_valid_token()
        if not token:
            return {
                'valid': False,
                'error': 'Failed to obtain access token - refresh token may be invalid'
            }
        
        # Test token with a simple API call
        try:
            url = "https://api.spotify.com/v1/me"
            headers = {"Authorization": f"Bearer {token}"}
            
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=headers) as response:
                    if response.status == 200:
                        user_data = await response.json()
                        return {
                            'valid': True,
                            'user_id': user_data.get('id'),
                            'display_name': user_data.get('display_name')
                        }
                    else:
                        return {
                            'valid': False,
                            'error': f'Token test failed: {response.status}'
                        }
        except Exception as e:
            return {
                'valid': False,
                'error': f'Token test error: {str(e)}'
            }
