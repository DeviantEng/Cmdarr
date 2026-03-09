#!/usr/bin/env python3
"""
Spotify API Client
Handles authentication and playlist operations for Spotify.
Uses API when credentials configured; falls back to SpotifyScraper when not configured or API fails.
"""

import asyncio
import base64
import time
from typing import Any

import aiohttp

from utils.playlist_parser import parse_playlist_url

from .client_base import BaseAPIClient


def _scraper_get_playlist(url: str) -> dict[str, Any]:
    """Sync helper: fetch playlist via SpotifyScraper (no auth). Returns normalized dict."""
    from utils.text_normalizer import normalize_text

    try:
        from spotify_scraper import SpotifyClient as ScraperClient

        client = ScraperClient(browser_type="requests")
        try:
            data = client.get_playlist_info(url)
            tracks = []
            for t in data.get("tracks", []):
                artists = t.get("artists", [])
                artist_name = (
                    artists[0].get("name", "Unknown Artist") if artists else "Unknown Artist"
                )
                album = t.get("album", {}) or {}
                album_name = (
                    album.get("name", "Unknown Album")
                    if isinstance(album, dict)
                    else "Unknown Album"
                )
                tracks.append(
                    {
                        "artist": normalize_text(artist_name),
                        "track": normalize_text(t.get("name", "Unknown Track")),
                        "album": normalize_text(album_name),
                    }
                )
            owner = data.get("owner", {}) or {}
            owner_name = (
                owner.get("display_name", owner.get("id", "Unknown"))
                if isinstance(owner, dict)
                else "Unknown"
            )
            return {
                "success": True,
                "name": data.get("name", "Unknown Playlist"),
                "description": data.get("description", ""),
                "owner": owner_name,
                "track_count": len(tracks),
                "tracks": tracks,
                "total_tracks": len(tracks),
            }
        finally:
            client.close()
    except Exception as e:
        return {"success": False, "error": f"Scraper failed: {str(e)}"}


class SpotifyClient(BaseAPIClient):
    """Client for Spotify API operations"""

    def __init__(self, config):
        super().__init__(
            config=config,
            client_name="spotify",
            base_url="https://api.spotify.com/v1",
            rate_limit=10.0,  # Spotify allows 10 requests per second
            headers={},
        )

        self.client_id = config.SPOTIFY_CLIENT_ID
        self.client_secret = config.SPOTIFY_CLIENT_SECRET
        self.access_token = None
        self.token_expires_at = 0

        if not self.client_id or not self.client_secret:
            self.logger.warning("Spotify credentials not configured")

    def _has_credentials(self) -> bool:
        """True if Client ID and Secret are configured."""
        return bool(self.client_id and self.client_secret)

    async def _get_playlist_via_scraper(self, url: str) -> dict[str, Any]:
        """Run sync scraper in executor."""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, _scraper_get_playlist, url)

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
                "Content-Type": "application/x-www-form-urlencoded",
            }
            data = {"grant_type": "client_credentials"}

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
                    self.logger.error(
                        f"Failed to get Spotify access token: {response.status} - {error_text}"
                    )
                    return False

        except Exception as e:
            self.logger.error(f"Error getting Spotify access token: {e}")
            return False

    async def _ensure_valid_token(self) -> bool:
        """Ensure we have a valid access token"""
        if not self.access_token or time.time() >= self.token_expires_at:
            return await self._get_access_token()
        return True

    async def _make_request(
        self, endpoint: str, params: dict[str, str] = None, method: str = "GET", **kwargs
    ) -> dict[str, Any] | None:
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

    async def get_playlist_info(self, url: str) -> dict[str, Any]:
        """
        Get playlist metadata from Spotify URL.
        Uses API when credentials configured; falls back to scraper when not or on API failure.
        """
        try:
            parsed = parse_playlist_url(url)
            if not parsed["valid"]:
                return {"success": False, "error": parsed["error"]}

            if not self._has_credentials():
                scraper_result = await self._get_playlist_via_scraper(url)
                if scraper_result.get("success"):
                    return {
                        "success": True,
                        "name": scraper_result.get("name", "Unknown Playlist"),
                        "description": scraper_result.get("description", ""),
                        "owner": scraper_result.get("owner", "Unknown"),
                        "track_count": scraper_result.get("track_count", 0),
                        "playlist_id": parsed["playlist_id"],
                        "public": True,
                        "collaborative": False,
                    }
                return scraper_result

            api_result = await self._get_playlist_info_async(parsed["playlist_id"])
            if api_result.get("success"):
                return api_result
            self.logger.info("API failed, falling back to scraper")
            scraper_result = await self._get_playlist_via_scraper(url)
            if scraper_result.get("success"):
                return {
                    "success": True,
                    "name": scraper_result.get("name", "Unknown Playlist"),
                    "description": scraper_result.get("description", ""),
                    "owner": scraper_result.get("owner", "Unknown"),
                    "track_count": scraper_result.get("track_count", 0),
                    "playlist_id": parsed["playlist_id"],
                    "public": True,
                    "collaborative": False,
                }
            return scraper_result

        except Exception as e:
            self.logger.error(f"Error getting playlist info: {e}")
            return {"success": False, "error": "Failed to fetch playlist info"}

    async def _get_playlist_info_async(self, playlist_id: str) -> dict[str, Any]:
        """Async helper to get playlist info via API."""
        try:
            result = await self._get(f"/playlists/{playlist_id}")

            if result:
                items_or_tracks = result.get("items", result.get("tracks", {}))
                track_count = (
                    items_or_tracks.get("total", 0) if isinstance(items_or_tracks, dict) else 0
                )
                return {
                    "success": True,
                    "name": result.get("name", "Unknown Playlist"),
                    "description": result.get("description", ""),
                    "owner": result.get("owner", {}).get("display_name", "Unknown"),
                    "track_count": track_count,
                    "playlist_id": playlist_id,
                    "public": result.get("public", False),
                    "collaborative": result.get("collaborative", False),
                }
            return {
                "success": False,
                "error": "Spotify API request failed (check credentials or Premium status for Development Mode)",
            }

        except Exception as e:
            self.logger.error(f"Error fetching playlist info: {e}")
            return {"success": False, "error": "Failed to fetch playlist from Spotify"}

    async def get_playlist_tracks(self, url: str) -> dict[str, Any]:
        """
        Get all tracks from a Spotify playlist.
        Uses API when credentials configured; falls back to scraper when not or on API failure.
        """
        try:
            parsed = parse_playlist_url(url)
            if not parsed["valid"]:
                return {"success": False, "error": parsed["error"]}

            if not self._has_credentials():
                scraper_result = await self._get_playlist_via_scraper(url)
                return scraper_result

            api_result = await self._get_playlist_tracks_async(parsed["playlist_id"])
            if api_result.get("success"):
                return api_result
            self.logger.info("API failed, falling back to scraper")
            return await self._get_playlist_via_scraper(url)

        except Exception as e:
            self.logger.error(f"Error getting playlist tracks: {e}")
            return {"success": False, "error": f"Failed to fetch playlist tracks: {str(e)}"}

    async def _get_playlist_tracks_async(self, playlist_id: str) -> dict[str, Any]:
        """Async helper to get all playlist tracks with pagination. Feb 2026: uses /items."""
        try:
            all_tracks = []
            offset = 0
            limit = 100

            while True:
                params = {
                    "limit": limit,
                    "offset": offset,
                    "fields": "items(item(name,artists(name),album(name)),track(name,artists(name),album(name)))",
                }

                result = await self._get(f"/playlists/{playlist_id}/items", params=params)

                if not result:
                    if offset == 0:
                        return {
                            "success": False,
                            "error": "Spotify API request failed (check credentials or Premium status for Development Mode)",
                            "tracks": [],
                            "total_tracks": 0,
                        }
                    break

                tracks = result.get("items", [])
                if not tracks:
                    break

                from utils.text_normalizer import normalize_text

                for item in tracks:
                    track = item.get("item", item.get("track", {}))
                    if track and track.get("name"):
                        artists = track.get("artists", [])
                        artist_name = (
                            artists[0].get("name", "Unknown Artist")
                            if artists
                            else "Unknown Artist"
                        )
                        raw_album_name = track.get("album", {}).get("name", "Unknown Album")
                        all_tracks.append(
                            {
                                "artist": normalize_text(artist_name),
                                "track": normalize_text(track.get("name", "Unknown Track")),
                                "album": normalize_text(raw_album_name),
                            }
                        )

                if len(tracks) < limit:
                    break

                offset += limit
                if offset > 10000:
                    self.logger.warning("Reached safety limit for playlist tracks")
                    break

            return {"success": True, "tracks": all_tracks, "total_tracks": len(all_tracks)}

        except Exception as e:
            self.logger.error(f"Error fetching playlist tracks: {e}")
            return {"success": False, "error": f"Failed to fetch tracks: {str(e)}"}

    async def get_album(self, album_id: str) -> dict[str, Any]:
        """Get album by ID. Returns artist_id, artist_name, title, album_url, etc."""
        try:
            result = await self._get(f"/albums/{album_id}")
            if not result:
                return {"success": False, "error": "No response"}
            artists = result.get("artists", [])
            artist_id = artists[0].get("id") if artists else ""
            artist_name = artists[0].get("name", "") if artists else ""
            album_url = result.get("external_urls", {}).get("spotify", "")
            return {
                "success": True,
                "id": result.get("id", ""),
                "title": result.get("name", ""),
                "artist_id": artist_id,
                "artist_name": artist_name,
                "release_date": result.get("release_date", ""),
                "record_type": (result.get("album_type") or "album").lower(),
                "nb_tracks": result.get("total_tracks", 0),
                "album_url": album_url,
            }
        except Exception as e:
            self.logger.error(f"Error fetching album {album_id}: {e}")
            return {"success": False, "error": str(e)}

    async def get_artist(self, artist_id: str) -> dict[str, Any]:
        """
        Get artist by Spotify ID (for name validation when using Lidarr's Spotify link).
        Returns dict with id, name, or error.
        """
        try:
            result = await self._get(f"/artists/{artist_id}")
            if not result:
                return {"success": False, "error": "No response", "name": None}
            return {
                "success": True,
                "id": result.get("id"),
                "name": result.get("name"),
            }
        except Exception as e:
            self.logger.error(f"Error fetching artist {artist_id}: {e}")
            return {"success": False, "error": str(e), "name": None}

    async def search_artists(self, name: str, limit: int = 5) -> dict[str, Any]:
        """
        Search for artists by name on Spotify.
        Feb 2026: search limit max 10 per request; paginate if more needed.
        """
        try:
            page_limit = min(limit, 10)
            all_artists = []
            offset = 0

            while len(all_artists) < limit:
                params = {
                    "q": f'artist:"{name}"',
                    "type": "artist",
                    "limit": page_limit,
                    "offset": offset,
                }
                result = await self._get("/search", params=params)

                if not result:
                    if offset == 0:
                        return {
                            "success": False,
                            "error": "No response from Spotify",
                            "artists": [],
                        }
                    break

                artists_data = result.get("artists", {}).get("items", [])
                for artist in artists_data:
                    all_artists.append(
                        {
                            "id": artist.get("id"),
                            "name": artist.get("name"),
                            "uri": artist.get("uri"),
                            "external_url": artist.get("external_urls", {}).get("spotify"),
                        }
                    )

                if len(artists_data) < page_limit:
                    break
                offset += page_limit
                if offset >= 50:
                    break

            return {"success": True, "artists": all_artists[:limit]}

        except Exception as e:
            self.logger.error(f"Error searching for artist '{name}': {e}")
            return {"success": False, "error": str(e), "artists": []}

    def _get_artist_albums_cache_key(self, artist_id: str) -> str:
        """Generate cache key for artist albums (v2 includes primary_artist_id)"""
        return f"spotify_artist_albums_v2:{artist_id}"

    async def get_artist_albums(
        self,
        artist_id: str,
        limit: int = 50,
        include_groups: str = "album,single,compilation,appears_on",
        fetch_all: bool = False,
    ) -> dict[str, Any]:
        """
        Get albums for an artist from Spotify.

        Args:
            artist_id: Spotify artist ID
            limit: Maximum albums per request (max 50)
            include_groups: Album types - album, single, appears_on, compilation
            fetch_all: If True, paginate to get all albums (no limit)

        Returns:
            Dict with success, albums list (id, name, release_date, total_tracks, etc.) or error info
        """
        try:
            cache_key = self._get_artist_albums_cache_key(artist_id)
            if self.cache_enabled and self.cache and fetch_all:
                cached = self.cache.get(cache_key, "spotify")
                if cached is not None:
                    self.logger.debug(f"Cache hit for Spotify albums: {artist_id}")
                    return {"success": True, "albums": cached}

            all_albums = []
            offset = 0
            page_limit = min(limit, 50)

            while True:
                params = {"limit": page_limit, "offset": offset, "include_groups": include_groups}
                result = await self._get(f"/artists/{artist_id}/albums", params=params)

                if not result:
                    break

                items = result.get("items", [])
                for item in items:
                    external_url = item.get("external_urls", {}).get("spotify")
                    artists = item.get("artists", [])
                    primary_artist_id = artists[0].get("id") if artists else None
                    all_albums.append(
                        {
                            "id": item.get("id"),
                            "name": item.get("name"),
                            "release_date": item.get("release_date", ""),
                            "release_date_precision": item.get("release_date_precision", "year"),
                            "album_type": item.get("album_type", ""),
                            "total_tracks": item.get("total_tracks", 0),
                            "primary_artist_id": primary_artist_id,
                            "external_url": external_url,
                            "spotify_url": external_url,
                        }
                    )

                if not fetch_all or len(items) < page_limit:
                    break
                offset += page_limit
                if offset >= 200:  # Spotify caps at 200 albums per artist
                    break

            if self.cache_enabled and self.cache and fetch_all:
                ttl = getattr(self.config, "NEW_RELEASES_CACHE_DAYS", 14)
                self.cache.set(cache_key, "spotify", all_albums, ttl)

            return {"success": True, "albums": all_albums}

        except Exception as e:
            self.logger.error(f"Error getting albums for artist {artist_id}: {e}")
            return {"success": False, "error": str(e), "albums": []}

    async def test_connection(self) -> bool:
        """Test connection: API when credentials configured, scraper when not."""
        try:
            if self._has_credentials():
                self.logger.info("Testing connection to Spotify API...")
                if not await self._ensure_valid_token():
                    self.logger.error("Failed to obtain Spotify access token")
                    return False
                result = await self._get("/tracks/4iV5W9uYEdYUVa79Axb7Rh")
                if result:
                    self.logger.info("Successfully connected to Spotify API")
                    return True
                self.logger.error("Spotify API test failed - no valid response")
                return False

            self.logger.info("Testing Spotify scraper (no credentials)...")
            scraper_result = await self._get_playlist_via_scraper(
                "https://open.spotify.com/playlist/37i9dQZF1DXcBWIGoYBM5M"
            )
            if scraper_result.get("success"):
                self.logger.info("Spotify scraper test passed")
                return True
            self.logger.error(f"Spotify scraper test failed: {scraper_result.get('error')}")
            return False

        except Exception as e:
            self.logger.error(f"Failed to connect to Spotify: {e}")
            return False
        finally:
            if self.session:
                await self.session.close()
                self.session = None

    async def get_api_stats(self) -> dict[str, Any]:
        """Get Spotify API usage statistics"""
        stats = await super().get_api_stats()
        stats.update(
            {
                "client_id_configured": bool(self.client_id),
                "client_secret_configured": bool(self.client_secret),
                "access_token_valid": bool(
                    self.access_token and time.time() < self.token_expires_at
                ),
            }
        )
        return stats

    async def close(self):
        """Close HTTP session"""
        if self.session:
            await self.session.close()
            self.session = None
