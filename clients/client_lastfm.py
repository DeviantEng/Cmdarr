#!/usr/bin/env python3
"""
Last.fm API Client with SQLite caching
Refactored to use BaseAPIClient for reduced code duplication
"""

from typing import List, Dict, Any, Optional
from .client_base import BaseAPIClient


class LastFMClient(BaseAPIClient):
    def __init__(self, config):
        super().__init__(
            config=config,
            client_name='lastfm',
            base_url="http://ws.audioscrobbler.com/2.0/",
            rate_limit=config.LASTFM_RATE_LIMIT
        )
    
    def _get_cache_key(self, mbid: str = None, artist_name: str = None) -> str:
        """Generate cache key for Last.fm requests"""
        if mbid:
            return f"similar_mbid:{mbid}"
        else:
            return f"similar_name:{artist_name}"
    
    async def _make_request(self, params: Dict[str, str], context_info: str = None) -> Optional[Dict[str, Any]]:
        """Make rate-limited HTTP request to Last.fm API"""
        # Add common parameters
        params.update({
            'api_key': self.config.LASTFM_API_KEY,
            'format': 'json'
        })
        
        # Use parent class method
        return await super()._make_request('', params=params)
    
    async def get_similar_artists(self, mbid: str, artist_name: str = None) -> List[Dict[str, Any]]:
        """Get similar artists for a given MBID, with artist name fallback and caching"""
        
        # Try cache first if enabled
        cache_key = self._get_cache_key(mbid=mbid)
        if self.cache_enabled and self.cache:
            # Check if this is a known failed lookup
            if self.cache.is_failed_lookup(cache_key, 'lastfm'):
                self.logger.debug(f"Skipping known failed lookup: {mbid}")
                return [], []
            
            # Try to get from cache
            cached_result = self.cache.get(cache_key, 'lastfm')
            if cached_result is not None:
                self.logger.debug(f"Cache hit for Last.fm similar artists: {mbid}")
                return cached_result.get('processed', []), cached_result.get('skipped', [])
        
        # Try MBID-based query first
        params = {
            'method': 'artist.getsimilar',
            'mbid': mbid,
            'limit': str(self.config.LASTFM_SIMILAR_COUNT)
        }
        
        try:
            response = await self._make_request(params, context_info=f"artist '{artist_name}' (MBID: {mbid})")
            
            # If MBID query failed and we have artist name, try name-based query
            if not response and artist_name:
                self.logger.debug(f"MBID lookup failed for '{artist_name}' (MBID: {mbid}), trying name-based query")
                
                # Try cache for name-based lookup
                name_cache_key = self._get_cache_key(artist_name=artist_name)
                if self.cache_enabled and self.cache:
                    if self.cache.is_failed_lookup(name_cache_key, 'lastfm'):
                        self.logger.debug(f"Skipping known failed name lookup: {artist_name}")
                        return [], []
                    
                    cached_result = self.cache.get(name_cache_key, 'lastfm')
                    if cached_result is not None:
                        self.logger.debug(f"Cache hit for Last.fm similar artists (name): {artist_name}")
                        return cached_result.get('processed', []), cached_result.get('skipped', [])
                
                params = {
                    'method': 'artist.getsimilar',
                    'artist': artist_name,
                    'limit': str(self.config.LASTFM_SIMILAR_COUNT)
                }
                response = await self._make_request(params, context_info=f"artist '{artist_name}' (name fallback)")
                
                # Log success/failure of fallback
                if response:
                    self.logger.debug(f"Name-based lookup succeeded for '{artist_name}' after MBID failure")
                else:
                    self.logger.debug(f"Both MBID and name-based lookups failed for '{artist_name}'")
                
                cache_key = name_cache_key  # Use name-based cache key for caching
            
            if not response:
                # Cache the failure
                if self.cache_enabled and self.cache:
                    self.cache.mark_failed_lookup(
                        cache_key, 'lastfm', 'API request failed', 
                        self.config.CACHE_FAILED_LOOKUP_TTL_DAYS
                    )
                return [], []  # Return empty lists for both processed and skipped
            
            # Extract similar artists from response
            similar_data = response.get('similarartists', {})
            artists = similar_data.get('artist', [])
            
            # Handle single artist response (not in array)
            if isinstance(artists, dict):
                artists = [artists]
            
            # Process and filter artists
            processed_artists = []
            skipped_artists = []  # Track artists without MBIDs
            
            for artist in artists:
                # Track artists without MBID separately
                if not artist.get('mbid'):
                    skipped_artists.append({
                        'name': artist.get('name', ''),
                        'match': artist.get('match', '0'),
                        'url': artist.get('url', ''),
                        'reason': 'no_mbid'
                    })
                    self.logger.debug(f"Skipping similar artist '{artist.get('name', 'unknown')}' - no MBID")
                    continue
                
                # Validate match score
                match_score = artist.get('match', '0')
                try:
                    float(match_score)
                except (ValueError, TypeError):
                    skipped_artists.append({
                        'name': artist.get('name', ''),
                        'match': match_score,
                        'url': artist.get('url', ''),
                        'reason': 'invalid_match_score'
                    })
                    self.logger.warning(f"Invalid match score for {artist.get('name', 'unknown')}: {match_score}")
                    continue
                
                processed_artists.append({
                    'name': artist.get('name', ''),
                    'mbid': artist.get('mbid', ''),
                    'match': match_score,
                    'url': artist.get('url', '')
                })
            
            self.logger.debug(f"Found {len(processed_artists)} similar artists with MBIDs, {len(skipped_artists)} skipped for {'MBID ' + mbid if 'mbid' in params else 'artist ' + artist_name}")
            
            # Cache the successful result
            if self.cache_enabled and self.cache:
                cache_data = {
                    'processed': processed_artists,
                    'skipped': skipped_artists
                }
                self.cache.set(cache_key, 'lastfm', cache_data, self.config.CACHE_LASTFM_TTL_DAYS)
            
            # Return both processed and skipped for tracking
            return processed_artists, skipped_artists
            
        except Exception as e:
            self.logger.error(f"Error getting similar artists for {'MBID ' + mbid if 'mbid' in params else 'artist ' + (artist_name or 'unknown')}: {e}")
            
            # Cache the failure
            if self.cache_enabled and self.cache:
                self.cache.mark_failed_lookup(
                    cache_key, 'lastfm', f'Exception: {str(e)}', 
                    self.config.CACHE_FAILED_LOOKUP_TTL_DAYS
                )
            
            return [], []  # Return empty lists for both processed and skipped
    
    async def get_artist_info(self, mbid: str = None, artist_name: str = None) -> Optional[Dict[str, Any]]:
        """Get artist information by MBID or name (for validation)"""
        if not mbid and not artist_name:
            self.logger.error("Either MBID or artist name must be provided")
            return None
        
        params = {'method': 'artist.getinfo'}
        
        if mbid:
            params['mbid'] = mbid
        else:
            params['artist'] = artist_name
        
        try:
            response = await self._make_request(params)
            
            if not response:
                return None
            
            artist_data = response.get('artist', {})
            return {
                'name': artist_data.get('name', ''),
                'mbid': artist_data.get('mbid', ''),
                'url': artist_data.get('url', ''),
                'playcount': artist_data.get('stats', {}).get('playcount', 0),
                'listeners': artist_data.get('stats', {}).get('listeners', 0)
            }
            
        except Exception as e:
            self.logger.error(f"Error getting artist info: {e}")
            return None
    
    async def test_connection(self) -> bool:
        """Test connection to Last.fm API"""
        try:
            self.logger.info("Testing connection to Last.fm API...")
            
            # Test with a known artist MBID (Radiohead)
            test_mbid = "a74b1b7f-71a5-4011-9441-d0b5e4122711"
            result = await self.get_artist_info(mbid=test_mbid)
            
            if result and result.get('name'):
                self.logger.info(f"Connected to Last.fm API successfully (test artist: {result['name']})")
                return True
            else:
                self.logger.error("Last.fm API test failed - no valid response")
                return False
                
        except Exception as e:
            self.logger.error(f"Failed to connect to Last.fm API: {e}")
            return False
    
    async def get_api_stats(self) -> Dict[str, Any]:
        """Get basic API usage statistics"""
        stats = await super().get_api_stats()
        stats.update({
            'rate_limit': self.config.LASTFM_RATE_LIMIT,
            'similar_count_per_request': self.config.LASTFM_SIMILAR_COUNT,
            'min_match_score': self.config.LASTFM_MIN_MATCH_SCORE,
        })
        return stats
