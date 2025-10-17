#!/usr/bin/env python3
"""
MusicBrainz API Client with SQLite caching
Refactored to use BaseAPIClient for reduced code duplication
"""

import aiohttp
from typing import List, Dict, Any, Optional
from urllib.parse import urlencode
from difflib import SequenceMatcher
from .client_base import BaseAPIClient


class MusicBrainzClient(BaseAPIClient):
    def __init__(self, config):
        # User agent is required by MusicBrainz
        headers = {
            'User-Agent': f'{config.MUSICBRAINZ_USER_AGENT}/1.0 ({config.MUSICBRAINZ_CONTACT})'
        }
        
        super().__init__(
            config=config,
            client_name='musicbrainz',
            base_url="https://musicbrainz.org/ws/2/",
            rate_limit=config.MUSICBRAINZ_RATE_LIMIT,
            headers=headers
        )
    
    def _get_cache_key(self, artist_name: str) -> str:
        """Generate cache key for MusicBrainz fuzzy search"""
        # Normalize artist name for consistent caching
        normalized_name = artist_name.lower().strip()
        return f"fuzzy_search:{normalized_name}"
    
    async def _make_request(self, endpoint: str, params: Dict[str, str]) -> Optional[Dict[str, Any]]:
        """Make rate-limited HTTP request to MusicBrainz API using HTTP utilities with retry logic"""
        params['fmt'] = 'json'  # Always request JSON format
        
        # Ensure session exists
        if not self.session:
            self.session = aiohttp.ClientSession(headers=self.headers)
        
        # Use HTTP utilities with retry configuration
        from utils.http_client import HTTPClientUtils
        
        url = HTTPClientUtils.build_api_url(self.base_url, endpoint)
        
        return await HTTPClientUtils.make_async_request(
            session=self.session,
            url=url,
            params=params,
            logger=self.logger,
            max_retries=getattr(self.config, 'MUSICBRAINZ_MAX_RETRIES', 3),
            retry_delay=getattr(self.config, 'MUSICBRAINZ_RETRY_DELAY', 2.0)
        )
    
    def _calculate_similarity(self, name1: str, name2: str) -> float:
        """Calculate similarity score between two artist names"""
        # Normalize names for comparison
        norm1 = name1.lower().strip()
        norm2 = name2.lower().strip()
        
        # Use sequence matcher for similarity
        return SequenceMatcher(None, norm1, norm2).ratio()
    
    def _clean_artist_name(self, name: str) -> str:
        """Clean artist name for better searching"""
        # Remove common suffixes that might cause issues
        cleaned = name.strip()
        
        # Remove parenthetical info for initial search
        if '(' in cleaned:
            cleaned = cleaned.split('(')[0].strip()
            
        return cleaned
    
    async def fuzzy_search_artist(self, artist_name: str) -> Optional[Dict[str, Any]]:
        """Search for artist using fuzzy matching with caching"""
        
        # Check cache first if enabled
        cache_key = self._get_cache_key(artist_name)
        if self.cache_enabled and self.cache:
            # Check if this is a known failed lookup
            if self.cache.is_failed_lookup(cache_key, 'musicbrainz'):
                self.logger.debug(f"Skipping known failed MusicBrainz lookup: {artist_name}")
                return None
            
            # Try to get from cache
            cached_result = self.cache.get(cache_key, 'musicbrainz')
            if cached_result is not None:
                self.logger.debug(f"Cache hit for MusicBrainz fuzzy search: {artist_name}")
                return cached_result
        
        # Clean the artist name for searching
        search_name = self._clean_artist_name(artist_name)
        
        # Search parameters
        params = {
            'query': f'artist:"{search_name}"',
            'limit': '10',  # Get top 10 matches for comparison
        }
        
        try:
            response = await self._make_request('artist', params)
            
            if not response or 'artists' not in response:
                self.logger.debug(f"No artists found for '{artist_name}'")
                
                # Cache the failure
                if self.cache_enabled and self.cache:
                    self.cache.mark_failed_lookup(
                        cache_key, 'musicbrainz', 'No artists found', 
                        self.config.CACHE_MUSICBRAINZ_TTL_DAYS
                    )
                return None
            
            artists = response['artists']
            if not artists:
                # Cache the failure
                if self.cache_enabled and self.cache:
                    self.cache.mark_failed_lookup(
                        cache_key, 'musicbrainz', 'Empty artists list', 
                        self.config.CACHE_MUSICBRAINZ_TTL_DAYS
                    )
                return None
            
            # Find best match using similarity scoring
            best_match = None
            best_score = 0
            
            for artist in artists:
                mb_name = artist.get('name', '')
                
                # Calculate similarity score
                similarity = self._calculate_similarity(artist_name, mb_name)
                
                # Also check aliases for better matching
                max_alias_similarity = 0
                if 'aliases' in artist:
                    for alias in artist['aliases']:
                        alias_name = alias.get('name', '')
                        alias_similarity = self._calculate_similarity(artist_name, alias_name)
                        max_alias_similarity = max(max_alias_similarity, alias_similarity)
                
                # Use the better of name or alias similarity
                final_similarity = max(similarity, max_alias_similarity)
                
                self.logger.debug(f"Artist '{mb_name}' similarity: {final_similarity:.3f} (name: {similarity:.3f}, alias: {max_alias_similarity:.3f})")
                
                if final_similarity > best_score:
                    best_score = final_similarity
                    best_match = {
                        'mbid': artist.get('id'),
                        'name': mb_name,
                        'similarity_score': final_similarity,
                        'disambiguation': artist.get('disambiguation', ''),
                        'type': artist.get('type', ''),
                        'country': artist.get('country', ''),
                        'matched_via': 'alias' if max_alias_similarity > similarity else 'name'
                    }
            
            # Only return if similarity meets minimum threshold
            if best_match and best_score >= self.config.MUSICBRAINZ_MIN_SIMILARITY:
                self.logger.debug(f"Best match for '{artist_name}': '{best_match['name']}' (score: {best_score:.3f})")
                
                # Cache the successful result
                if self.cache_enabled and self.cache:
                    self.cache.set(cache_key, 'musicbrainz', best_match, self.config.CACHE_MUSICBRAINZ_TTL_DAYS)
                
                return best_match
            else:
                self.logger.debug(f"No match above threshold {self.config.MUSICBRAINZ_MIN_SIMILARITY} for '{artist_name}' (best: {best_score:.3f})")
                
                # Cache the failure
                if self.cache_enabled and self.cache:
                    self.cache.mark_failed_lookup(
                        cache_key, 'musicbrainz', f'No match above threshold (best: {best_score:.3f})', 
                        self.config.CACHE_MUSICBRAINZ_TTL_DAYS
                    )
                return None
                
        except Exception as e:
            self.logger.error(f"Error searching for artist '{artist_name}': {e}")
            
            # Cache the failure
            if self.cache_enabled and self.cache:
                self.cache.mark_failed_lookup(
                    cache_key, 'musicbrainz', f'Exception: {str(e)}', 
                    self.config.CACHE_MUSICBRAINZ_TTL_DAYS
                )
            return None
    
    async def get_artist_by_mbid(self, mbid: str) -> Optional[Dict[str, Any]]:
        """Get artist details by MBID"""
        try:
            response = await self._make_request(f'artist/{mbid}', {})
            
            if response:
                return {
                    'mbid': response.get('id'),
                    'name': response.get('name'),
                    'disambiguation': response.get('disambiguation', ''),
                    'type': response.get('type', ''),
                    'country': response.get('country', '')
                }
            return None
            
        except Exception as e:
            self.logger.error(f"Error getting artist by MBID {mbid}: {e}")
            return None
    
    async def test_connection(self) -> bool:
        """Test connection to MusicBrainz API"""
        try:
            self.logger.info("Testing connection to MusicBrainz API...")
            
            # Test with a known artist (The Beatles)
            test_mbid = "b10bbbfc-cf9e-42e0-be17-e2c3e1d2600d"
            result = await self.get_artist_by_mbid(test_mbid)
            
            if result and result.get('name'):
                self.logger.info(f"Connected to MusicBrainz API successfully (test artist: {result['name']})")
                return True
            else:
                self.logger.error("MusicBrainz API test failed - no valid response")
                return False
                
        except Exception as e:
            self.logger.error(f"Failed to connect to MusicBrainz API: {e}")
            return False
    
    async def get_api_stats(self) -> Dict[str, Any]:
        """Get basic API usage statistics"""
        stats = await super().get_api_stats()
        stats.update({
            'rate_limit': self.config.MUSICBRAINZ_RATE_LIMIT,
            'min_similarity': self.config.MUSICBRAINZ_MIN_SIMILARITY,
            'user_agent': self.headers['User-Agent'],
        })
        return stats