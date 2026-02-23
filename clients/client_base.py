#!/usr/bin/env python3
"""
Base Client Class for API Clients
Eliminates code duplication across all API clients
"""

import aiohttp
import asyncio
import logging
import time
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List
from urllib.parse import urlencode
from cache_manager import get_cache_manager
from utils.http_client import HTTPClientUtils, HTTPRequestBuilder


class AsyncRateLimiter:
    """Unified async rate limiter for all API clients"""
    
    def __init__(self, requests_per_second: float):
        self.requests_per_second = requests_per_second
        self.min_interval = 1.0 / requests_per_second
        self.last_request_time = 0
        self.request_count = 0
        self._lock = asyncio.Lock()
    
    async def acquire(self):
        """Acquire permission to make a request"""
        async with self._lock:
            current_time = time.time()
            time_since_last = current_time - self.last_request_time
            
            if time_since_last < self.min_interval:
                sleep_time = self.min_interval - time_since_last
                await asyncio.sleep(sleep_time)
            
            self.last_request_time = time.time()
            self.request_count += 1


class BaseAPIClient(ABC):
    """Base class for all API clients with common functionality"""
    
    def __init__(self, config, client_name: str, base_url: str, 
                 rate_limit: float = 1.0, headers: Dict[str, str] = None):
        self.config = config
        self.client_name = client_name
        self.base_url = base_url.rstrip('/')
        self.logger = logging.getLogger(f'cmdarr.{client_name}')
            
        self.session = None
        self._rate_limiter = AsyncRateLimiter(rate_limit)
        
        # Default headers
        self.headers = headers or {}
        
        # Initialize cache (always enabled)
        self.cache_enabled = True
        self.cache = get_cache_manager()
    
    async def __aenter__(self):
        """Async context manager entry"""
        if not self.session:
            self.session = aiohttp.ClientSession(headers=self.headers)
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        if self.session:
            await self.session.close()
            self.session = None
    
    async def _make_request(self, endpoint: str, params: Dict[str, str] = None, 
                           method: str = 'GET', **kwargs) -> Optional[Dict[str, Any]]:
        """Make rate-limited HTTP request to API using HTTP utilities"""
        if params is None:
            params = {}
        
        # Build URL
        if endpoint.startswith('http'):
            url = endpoint
        else:
            url = HTTPClientUtils.build_api_url(self.base_url, endpoint)
        
        # Apply rate limiting
        await self._rate_limiter.acquire()
        
        # Ensure session exists
        if not self.session:
            self.session = aiohttp.ClientSession(headers=self.headers)
        
        # Use HTTP utilities for the actual request
        return await HTTPClientUtils.make_async_request(
            session=self.session,
            url=url,
            method=method,
            params=params,
            headers=self.headers,
            timeout=30,
            logger=self.logger,
            json=kwargs.get('json')  # Pass JSON data if provided
        )
    
    def _get_cache_key(self, operation: str, *args) -> str:
        """Generate cache key for requests"""
        key_parts = [operation] + [str(arg) for arg in args]
        return ":".join(key_parts)
    
    def _create_request_builder(self) -> HTTPRequestBuilder:
        """Create an HTTP request builder for this client"""
        return HTTPRequestBuilder(self.base_url, self.logger)
    
    async def test_connection(self) -> bool:
        """Test connection to API - must be implemented by subclasses"""
        raise NotImplementedError("Subclasses must implement test_connection")
    
    async def get_api_stats(self) -> Dict[str, Any]:
        """Get basic API usage statistics"""
        stats = {
            'client_name': self.client_name,
            'base_url': self.base_url,
            'total_requests_made': self._rate_limiter.request_count,
            'cache_enabled': self.cache_enabled
        }
        
        # Add cache stats if available
        if self.cache_enabled and self.cache:
            cache_stats = self.cache.get_stats()
            client_cache_count = cache_stats.get('cache_counts_by_source', {}).get(self.client_name, 0)
            stats['cache_entries'] = client_cache_count
        
        return stats
    
    async def _get(self, endpoint: str, params: Dict[str, str] = None, **kwargs) -> Optional[Dict[str, Any]]:
        """Convenience method for GET requests"""
        return await self._make_request(endpoint, params=params, method='GET', **kwargs)
    
    async def _post(self, endpoint: str, params: Dict[str, str] = None, json: Dict[str, Any] = None, **kwargs) -> Optional[Dict[str, Any]]:
        """Convenience method for POST requests"""
        return await self._make_request(endpoint, params=params, method='POST', json=json, **kwargs)
    
    async def _put(self, endpoint: str, params: Dict[str, str] = None, json: Dict[str, Any] = None, **kwargs) -> Optional[Dict[str, Any]]:
        """Convenience method for PUT requests"""
        return await self._make_request(endpoint, params=params, method='PUT', json=json, **kwargs)
    
    async def _delete(self, endpoint: str, params: Dict[str, str] = None, **kwargs) -> Optional[Dict[str, Any]]:
        """Convenience method for DELETE requests"""
        return await self._make_request(endpoint, params=params, method='DELETE', **kwargs)
    
    def sync_playlist(self, title: str, tracks: List[Dict[str, Any]], summary: str = "", **kwargs) -> Dict[str, Any]:
        """
        Standard playlist sync method - must be implemented by subclasses
        
        Args:
            title: Playlist title
            tracks: List of track dictionaries with 'artist', 'album', 'track' keys
            summary: Playlist description
            **kwargs: Additional client-specific parameters
            
        Returns:
            Dict with keys: success, action, total_tracks, found_tracks, message
        """
        raise NotImplementedError("Subclasses must implement sync_playlist")
    
    async def close(self):
        """Close the HTTP session"""
        if self.session:
            await self.session.close()
            self.session = None
    
    def validate_playlist_exists(self, title: str) -> Dict[str, Any]:
        """
        Validate if a playlist exists and return detailed information about it.
        Base implementation - should be overridden by specific clients.
        Returns dict with 'exists', 'count', 'playlists', 'total_tracks', 'track_inventory'
        """
        raise NotImplementedError("validate_playlist_exists must be implemented by specific client")
    
    def compare_playlist_content(self, title: str, new_track_ids: List[str]) -> Dict[str, Any]:
        """
        Compare new track IDs with existing playlist content.
        Base implementation - should be overridden by specific clients.
        Returns dict with 'identical', 'similar', 'different', 'recommendation'
        """
        raise NotImplementedError("compare_playlist_content must be implemented by specific client")