#!/usr/bin/env python3
"""
Lidarr API Client
Refactored to use BaseAPIClient for reduced code duplication
"""

import re
import aiohttp
import asyncio
from typing import List, Dict, Any, Optional, Set
from urllib.parse import urljoin
from .client_base import BaseAPIClient


# Regex to extract Spotify artist ID from URLs like https://open.spotify.com/artist/0fLSXz9013NN5b1NoRXLJ9
_SPOTIFY_ARTIST_URL_RE = re.compile(
    r'https?://(?:open\.)?spotify\.com/artist/([a-zA-Z0-9]+)',
    re.IGNORECASE
)


def _extract_spotify_id_from_links(links: List[Dict[str, Any]]) -> Optional[str]:
    """
    Extract Spotify artist ID from Lidarr artist links.
    Lidarr links are [{url, name}, ...] - we find the Spotify one by URL pattern.
    """
    for link in links or []:
        url = link.get('url') or link.get('Url') or ''
        name = (link.get('name') or link.get('Name') or '').lower()
        if 'spotify' in url.lower() or name == 'spotify':
            m = _SPOTIFY_ARTIST_URL_RE.search(url)
            if m:
                return m.group(1)
    return None


class LidarrClient(BaseAPIClient):
    def __init__(self, config):
        headers = {
            'X-Api-Key': config.LIDARR_API_KEY,
            'Content-Type': 'application/json'
        }
        
        super().__init__(
            config=config,
            client_name='lidarr',
            base_url=f"{config.LIDARR_URL.rstrip('/')}/api/v1/",
            rate_limit=1.0,  # Conservative rate limiting
            headers=headers
        )
    
    async def _make_request(self, endpoint: str, method: str = 'GET', **kwargs) -> Optional[Dict[str, Any]]:
        """Make HTTP request to Lidarr API with custom timeout and SSL handling"""
        url = f"{self.base_url.rstrip('/')}/{endpoint.lstrip('/')}"
        
        timeout = aiohttp.ClientTimeout(total=self.config.LIDARR_TIMEOUT)
        connector = aiohttp.TCPConnector(ssl=not self.config.LIDARR_IGNORE_TLS)
        
        try:
            async with aiohttp.ClientSession(
                headers=self.headers,
                timeout=timeout,
                connector=connector
            ) as session:
                self.logger.debug(f"Making {method} request to: {url}")
                
                async with session.request(method, url, **kwargs) as response:
                    if response.status == 200:
                        data = await response.json()
                        self.logger.debug(f"Successful response from {endpoint}")
                        return data
                    else:
                        self.logger.error(f"Lidarr API error {response.status}: {await response.text()}")
                        response.raise_for_status()
                        
        except asyncio.TimeoutError:
            self.logger.error(f"Timeout connecting to Lidarr at {url}")
            raise
        except aiohttp.ClientError as e:
            self.logger.error(f"HTTP error connecting to Lidarr: {e}")
            raise
        except Exception as e:
            self.logger.error(f"Unexpected error connecting to Lidarr: {e}")
            raise
            
        return None
    
    def _get_exclusions_cache_key(self) -> str:
        """Generate cache key for import list exclusions"""
        return "lidarr_import_list_exclusions"
    
    async def get_import_list_exclusions(self) -> Set[str]:
        """
        Get Import List Exclusions from Lidarr with caching
        
        Returns:
            Set of excluded artist MBIDs
        """
        try:
            # Check cache first if enabled
            cache_key = self._get_exclusions_cache_key()
            if self.cache_enabled and self.cache:
                cached_exclusions = self.cache.get(cache_key, 'lidarr')
                if cached_exclusions is not None:
                    self.logger.debug(f"Cache hit for import list exclusions: {len(cached_exclusions)} exclusions")
                    return set(cached_exclusions)
            
            self.logger.info("Fetching Import List Exclusions from Lidarr...")
            exclusions_data = await self._make_request('importlistexclusion')
            
            if not exclusions_data:
                self.logger.warning("No exclusions data returned from Lidarr")
                return set()
            
            # Extract MBIDs from exclusions
            excluded_mbids = set()
            for exclusion in exclusions_data:
                if isinstance(exclusion, dict):
                    foreign_id = exclusion.get('foreignId')
                    artist_name = exclusion.get('artistName', 'Unknown')
                    
                    if foreign_id:
                        excluded_mbids.add(foreign_id)
                        self.logger.debug(f"Exclusion: {artist_name} (MBID: {foreign_id})")
                    else:
                        self.logger.warning(f"Exclusion entry missing foreignId: {exclusion}")
            
            self.logger.info(f"Retrieved {len(excluded_mbids)} Import List Exclusions from Lidarr")
            
            # Cache the result (convert set to list for JSON serialization)
            if self.cache_enabled and self.cache:
                exclusions_list = list(excluded_mbids)
                # Cache for 7 days - exclusions don't change frequently
                self.cache.set(cache_key, 'lidarr', exclusions_list, 7)
                self.logger.debug(f"Cached {len(exclusions_list)} exclusions for 7 days")
            
            return excluded_mbids
            
        except Exception as e:
            self.logger.error(f"Failed to get Import List Exclusions from Lidarr: {e}")
            # Return empty set on error to not block discovery
            return set()
    
    async def test_connection(self) -> bool:
        """Test connection to Lidarr API"""
        try:
            self.logger.info("Testing connection to Lidarr...")
            result = await self._make_request('system/status')
            if result:
                self.logger.info(f"Connected to Lidarr v{result.get('version', 'unknown')}")
                return True
        except Exception as e:
            self.logger.error(f"Failed to connect to Lidarr: {e}")
            
        return False
    
    def _get_artists_cache_key(self) -> str:
        """Generate cache key for Lidarr artists (v2 includes spotifyArtistId from links)"""
        return "lidarr_artists_v2"

    async def get_all_artists(self) -> List[Dict[str, Any]]:
        """Get all artists from Lidarr with their MBIDs (cached 7 days)"""
        try:
            cache_key = self._get_artists_cache_key()
            if self.cache_enabled and self.cache:
                cached = self.cache.get(cache_key, 'lidarr')
                if cached is not None:
                    self.logger.debug(f"Cache hit for Lidarr artists: {len(cached)} artists")
                    return cached

            self.logger.info("Fetching all artists from Lidarr...")
            artists_data = await self._make_request('artist')
            
            if not artists_data:
                self.logger.warning("No artists returned from Lidarr")
                return []
            
            # Extract relevant artist information
            artists = []
            for artist in artists_data:
                # Validate required fields
                mbid = artist.get('foreignArtistId')  # This is the MBID field in Lidarr
                name = artist.get('artistName')
                
                if not mbid:
                    self.logger.warning(f"Artist '{name}' has no MBID - this should not happen in Lidarr")
                    continue
                    
                if not name:
                    self.logger.warning(f"Artist with MBID '{mbid}' has no name")
                    continue
                
                # Extract Spotify artist ID from links if available (avoids name-search collisions)
                spotify_artist_id = _extract_spotify_id_from_links(artist.get('links') or [])

                artists.append({
                    'musicBrainzId': mbid,  # Rename to standard field name for consistency
                    'artistName': name,
                    'id': artist.get('id'),
                    'status': artist.get('status'),
                    'monitored': artist.get('monitored', False),
                    'monitorNewItems': artist.get('monitorNewItems', 'all'),
                    'spotifyArtistId': spotify_artist_id,  # From Lidarr links when available
                })
            
            self.logger.info(f"Retrieved {len(artists)} artists from Lidarr")

            if self.cache_enabled and self.cache:
                ttl = getattr(self.config, 'NEW_RELEASES_CACHE_DAYS', 14)
                self.cache.set(cache_key, 'lidarr', artists, ttl)
            
            # Log any artists without MBIDs (should not happen)
            total_artists = len(artists_data)
            missing_mbid_count = total_artists - len(artists)
            if missing_mbid_count > 0:
                self.logger.warning(f"{missing_mbid_count} artists in Lidarr missing MBID (unexpected)")
            
            return artists
            
        except Exception as e:
            self.logger.error(f"Failed to get artists from Lidarr: {e}")
            raise
    
    async def get_artist_by_mbid(self, mbid: str) -> Optional[Dict[str, Any]]:
        """Get specific artist by MBID"""
        try:
            artists = await self.get_all_artists()
            for artist in artists:
                if artist['musicBrainzId'] == mbid:
                    return artist
            return None
        except Exception as e:
            self.logger.error(f"Failed to get artist by MBID {mbid}: {e}")
            return None
    
    async def get_quality_profiles(self) -> List[Dict[str, Any]]:
        """Get all quality profiles from Lidarr"""
        try:
            response = await self._make_request('qualityprofile')
            if response:
                return response
            return []
        except Exception as e:
            self.logger.error(f"Error getting quality profiles: {e}")
            return []
    
    async def get_root_folders(self) -> List[Dict[str, Any]]:
        """Get all root folders from Lidarr"""
        try:
            response = await self._make_request('rootfolder')
            if response:
                return response
            return []
        except Exception as e:
            self.logger.error(f"Error getting root folders: {e}")
            return []

    async def add_artist(self, mbid: str, artist_name: str, quality_profile_id: int = None, 
                       metadata_profile_id: int = None, monitored: bool = True) -> Dict[str, Any]:
        """Add a new artist to Lidarr by MusicBrainz ID"""
        try:
            # Check if artist already exists
            existing_artist = await self.get_artist_by_mbid(mbid)
            if existing_artist:
                return {
                    'success': False,
                    'error': 'Artist already exists',
                    'artist': existing_artist
                }
            
            # Get actual configuration from Lidarr
            quality_profiles = await self.get_quality_profiles()
            root_folders = await self.get_root_folders()
            
            if not quality_profiles:
                return {
                    'success': False,
                    'error': 'No quality profiles found in Lidarr'
                }
            
            if not root_folders:
                return {
                    'success': False,
                    'error': 'No root folders found in Lidarr'
                }
            
            # Use provided IDs or default to first available
            if quality_profile_id is None:
                quality_profile_id = quality_profiles[0]['id']
            
            if metadata_profile_id is None:
                metadata_profile_id = 1  # Default metadata profile ID
            
            # Use first root folder
            root_folder_path = root_folders[0]['path']
            
            # Prepare artist data for Lidarr API
            artist_data = {
                'foreignArtistId': mbid,
                'artistName': artist_name,
                'qualityProfileId': quality_profile_id,
                'metadataProfileId': metadata_profile_id,
                'monitored': monitored,
                'monitorNewItems': 'all',  # Monitor all new albums
                'rootFolderPath': root_folder_path,
                'addOptions': {
                    'monitor': 'all',
                    'searchForMissingAlbums': False  # Don't auto-search on add
                }
            }
            
            self.logger.info(f"Adding artist '{artist_name}' (MBID: {mbid}) to Lidarr")
            self.logger.debug(f"Using quality profile ID: {quality_profile_id}, root folder: {root_folder_path}")
            
            # Make POST request to add artist
            response = await self._make_request('artist', method='POST', json=artist_data)
            
            if response:
                self.logger.info(f"Successfully added artist '{artist_name}' to Lidarr")
                return {
                    'success': True,
                    'artist': response,
                    'message': f"Artist '{artist_name}' added successfully"
                }
            else:
                self.logger.error(f"Failed to add artist '{artist_name}' - no response from Lidarr")
                return {
                    'success': False,
                    'error': 'No response from Lidarr API'
                }
                
        except Exception as e:
            self.logger.error(f"Error adding artist '{artist_name}' (MBID: {mbid}): {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    async def get_artist_stats(self) -> Dict[str, Any]:
        """Get basic statistics about artists in Lidarr"""
        try:
            artists = await self.get_all_artists()
            
            stats = {
                'total_artists': len(artists),
                'monitored_artists': len([a for a in artists if a.get('monitored', False)]),
                'artists_with_mbid': len([a for a in artists if a.get('musicBrainzId')]),
            }
            
            # Count by status
            status_counts = {}
            for artist in artists:
                status = artist.get('status', 'unknown')
                status_counts[status] = status_counts.get(status, 0) + 1
            
            stats['status_breakdown'] = status_counts
            
            self.logger.info(f"Lidarr stats: {stats}")
            return stats
            
        except Exception as e:
            self.logger.error(f"Failed to get artist stats: {e}")
            return {}
    
    async def get_exclusion_stats(self) -> Dict[str, Any]:
        """Get statistics about Import List Exclusions"""
        try:
            exclusions = await self.get_import_list_exclusions()
            
            stats = {
                'total_exclusions': len(exclusions),
                'sample_exclusions': list(exclusions)[:5] if exclusions else []
            }
            
            return stats
            
        except Exception as e:
            self.logger.error(f"Failed to get exclusion stats: {e}")
            return {'total_exclusions': 0, 'sample_exclusions': []}
    
    def _get_albums_cache_key(self) -> str:
        """Generate cache key for Lidarr albums"""
        return "lidarr_albums"

    async def get_all_albums(self) -> List[Dict[str, Any]]:
        """
        Get all albums from Lidarr with caching.
        Used to filter out releases already in Lidarr from new releases discovery.
        """
        try:
            cache_key = self._get_albums_cache_key()
            if self.cache_enabled and self.cache:
                cached = self.cache.get(cache_key, 'lidarr')
                if cached is not None:
                    self.logger.debug(f"Cache hit for Lidarr albums: {len(cached)} albums")
                    return cached

            self.logger.info("Fetching all albums from Lidarr...")
            albums_data = await self._make_request('album')

            if not albums_data:
                self.logger.warning("No albums returned from Lidarr")
                return []

            # Handle both list and paginated response formats
            if isinstance(albums_data, dict):
                albums_data = albums_data.get('records', albums_data.get('items', []))

            albums = []
            for album in (albums_data or []):
                artist_id = album.get('artistId')
                foreign_album_id = album.get('foreignAlbumId')
                title = album.get('title', '')
                if artist_id and title:
                    albums.append({
                        'artistId': artist_id,
                        'foreignAlbumId': foreign_album_id,
                        'title': title,
                        'monitored': album.get('monitored', False),
                    })

            if self.cache_enabled and self.cache:
                ttl = getattr(self.config, 'NEW_RELEASES_CACHE_DAYS', 14)
                self.cache.set(cache_key, 'lidarr', albums, ttl)

            self.logger.info(f"Retrieved {len(albums)} albums from Lidarr")
            return albums

        except Exception as e:
            self.logger.error(f"Failed to get albums from Lidarr: {e}")
            return []

    async def get_api_stats(self) -> Dict[str, Any]:
        """Get basic API usage statistics"""
        stats = await super().get_api_stats()
        stats.update({
            'base_url': self.base_url,
            'timeout': self.config.LIDARR_TIMEOUT,
            'ignore_tls': self.config.LIDARR_IGNORE_TLS,
        })
        return stats