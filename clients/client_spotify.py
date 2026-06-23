#!/usr/bin/env python3
"""
Spotify API Client
Handles authentication and playlist operations for Spotify.
Uses API when credentials configured; falls back to SpotifyScraper when not configured or API fails.
Caches API usability (403 Premium required) to avoid repeated token fetch + 403 on every playlist sync.
"""

import asyncio
import base64
import hashlib
import inspect
import json
import time
from typing import Any

import aiohttp

from services.config_service import config_service
from utils.playlist_parser import parse_playlist_url
from utils.text_normalizer import normalize_text

from .client_base import BaseAPIClient


def _scraper_uses_legacy_init() -> bool:
    """spotifyscraper 2.x accepts browser_type; 3.x removed it."""
    from spotify_scraper import SpotifyClient as ScraperClient

    return "browser_type" in inspect.signature(ScraperClient.__init__).parameters


def _normalize_scraper_owner(owner: Any) -> str:
    if hasattr(owner, "to_dict"):
        owner = owner.to_dict()
    if not isinstance(owner, dict):
        return "Unknown"
    return owner.get("display_name") or owner.get("name") or owner.get("id") or "Unknown"


def _normalize_scraper_tracks(raw_tracks: list[Any]) -> list[dict[str, str]]:
    tracks: list[dict[str, str]] = []
    for entry in raw_tracks:
        track = entry.get("track", entry) if isinstance(entry, dict) else entry
        if hasattr(track, "to_dict"):
            track = track.to_dict()
        if not isinstance(track, dict) or not track.get("name"):
            continue

        artists = track.get("artists", [])
        artist_name = (
            artists[0].get("name", "Unknown Artist")
            if artists and isinstance(artists[0], dict)
            else "Unknown Artist"
        )
        album = track.get("album", {}) or {}
        album_name = (
            album.get("name", "Unknown Album") if isinstance(album, dict) else "Unknown Album"
        )
        tracks.append(
            {
                "artist": normalize_text(artist_name),
                "track": normalize_text(track.get("name", "Unknown Track")),
                "album": normalize_text(album_name),
            }
        )
    return tracks


def _scraper_playlist_result(data: dict[str, Any]) -> dict[str, Any]:
    tracks = _normalize_scraper_tracks(data.get("tracks", []))
    total = data.get("total_tracks") or data.get("track_count") or len(tracks)
    return {
        "success": True,
        "name": data.get("name", "Unknown Playlist"),
        "description": data.get("description", ""),
        "owner": _normalize_scraper_owner(data.get("owner", {})),
        "track_count": len(tracks),
        "tracks": tracks,
        "total_tracks": int(total) if isinstance(total, int | float) else len(tracks),
    }


def _scraper_get_playlist_v2(url: str) -> dict[str, Any]:
    from spotify_scraper import SpotifyClient as ScraperClient

    client = ScraperClient(browser_type="requests")
    try:
        return _scraper_playlist_result(client.get_playlist_info(url))
    finally:
        client.close()


def _scraper_get_playlist_v3(url: str) -> dict[str, Any]:
    from spotify_scraper import SpotifyClient as ScraperClient

    with ScraperClient() as client:
        playlist = client.get_playlist(url)
        data = playlist.to_dict() if hasattr(playlist, "to_dict") else playlist
    if not isinstance(data, dict):
        raise TypeError(f"Unexpected scraper playlist payload: {type(data)!r}")
    return _scraper_playlist_result(data)


def _scraper_get_playlist(url: str) -> dict[str, Any]:
    """Sync helper: fetch playlist via SpotifyScraper (no auth). Returns normalized dict."""
    try:
        if _scraper_uses_legacy_init():
            return _scraper_get_playlist_v2(url)
        return _scraper_get_playlist_v3(url)
    except Exception as e:
        return {"success": False, "error": f"Scraper failed: {str(e)}"}


_SCRAPER_DISCO_PAGE_SIZE = 50

_SPOTIFY_DISCO_TYPE_MAP = {
    "ALBUM": "album",
    "EP": "ep",
    "SINGLE": "single",
    "COMPILATION": "compilation",
}


def _spotify_discography_album_type(raw_type: str | None) -> str:
    key = (raw_type or "ALBUM").upper()
    return _SPOTIFY_DISCO_TYPE_MAP.get(key, key.lower())


def _parse_scraper_discography_date(date_obj: dict[str, Any] | None) -> tuple[str, str]:
    if not date_obj:
        return "", "year"
    precision_raw = (date_obj.get("precision") or "YEAR").upper()
    precision_map = {"DAY": "day", "MONTH": "month", "YEAR": "year"}
    precision = precision_map.get(precision_raw, "year")
    iso = date_obj.get("isoString") or ""
    if iso and "T" in iso:
        return iso[:10], precision
    year = date_obj.get("year")
    if year is not None:
        return str(year), "year"
    return "", "year"


def _normalize_scraper_discography_release(
    release: dict[str, Any], artist_id: str
) -> dict[str, Any] | None:
    """Normalize artist discography GraphQL release to NRD album dict shape."""
    album_id = release.get("id")
    if not album_id:
        return None
    sharing = release.get("sharingInfo") or {}
    share_url = sharing.get("shareUrl") or f"https://open.spotify.com/album/{album_id}"
    release_date, precision = _parse_scraper_discography_date(release.get("date"))
    tracks = release.get("tracks") or {}
    return {
        "id": album_id,
        "name": release.get("name") or "",
        "release_date": release_date,
        "release_date_precision": precision,
        "album_type": _spotify_discography_album_type(release.get("type")),
        "total_tracks": int(tracks.get("totalCount") or 0),
        "primary_artist_id": artist_id,
        "external_url": share_url,
        "spotify_url": share_url,
    }


def _scraper_iter_discography_releases(client: Any, artist_id: str):
    """Yield raw release dicts from paginated artist discography (one artist endpoint)."""
    from spotify_scraper.api import parse_entities as pe

    _, entity_id = client._resolve(artist_id, "artist")
    offset = 0
    total: int | None = None
    while True:
        union = client._anon_union(
            "artist_discography",
            entity_id,
            "artistUnion",
            {"offset": offset, "limit": _SCRAPER_DISCO_PAGE_SIZE},
        )
        if total is None:
            total = pe.discography_total(union)
        count = pe.discography_item_count(union)
        if count == 0:
            break
        for group in union.get("discography", {}).get("all", {}).get("items", []):
            for release in group.get("releases", {}).get("items", []):
                if isinstance(release, dict) and release.get("id"):
                    yield release
        offset += count
        if total is not None and offset >= total:
            break


def _scraper_supports_discography() -> bool:
    """spotifyscraper 3.x exposes get_discography; 2.x does not."""
    if _scraper_uses_legacy_init():
        return False
    try:
        from spotify_scraper import SpotifyClient as ScraperClient

        return callable(getattr(ScraperClient, "get_discography", None))
    except ImportError:
        return False


def _scraper_model_to_dict(obj: Any) -> dict[str, Any]:
    if obj is None:
        return {}
    if isinstance(obj, dict):
        return obj
    if hasattr(obj, "to_dict"):
        data = obj.to_dict()
        return data if isinstance(data, dict) else {}
    return {}


def _normalize_scraper_album(
    data: dict[str, Any], fallback_artist_id: str | None = None
) -> dict[str, Any]:
    """Normalize scraper album payload to NRD album dict shape."""
    artists = data.get("artists") or []
    primary_artist_id = fallback_artist_id
    if artists:
        a0 = artists[0]
        if isinstance(a0, dict):
            primary_artist_id = a0.get("id") or primary_artist_id
    album_id = data.get("id") or ""
    share_url = data.get("share_url") or (
        f"https://open.spotify.com/album/{album_id}" if album_id else ""
    )
    release_date = data.get("release_date") or ""
    precision = "year"
    if release_date and len(release_date) >= 10:
        precision = "day"
    elif release_date and len(release_date) >= 7:
        precision = "month"
    return {
        "id": album_id,
        "name": data.get("name") or "",
        "release_date": release_date,
        "release_date_precision": precision,
        "album_type": (data.get("album_type") or "album").lower(),
        "total_tracks": int(data.get("total_tracks") or 0),
        "primary_artist_id": primary_artist_id,
        "external_url": share_url,
        "spotify_url": share_url,
    }


def _scraper_album_type_in_groups(album_type: str, include_groups: str) -> bool:
    groups = {g.strip().lower() for g in (include_groups or "").split(",") if g.strip()}
    if not groups:
        return True
    at = (album_type or "album").lower()
    if at in groups:
        return True
    if at == "ep" and "album" in groups:
        return True
    return False


def _scraper_enrich_nrd_album(
    album_id: str, fallback_artist_id: str | None = None
) -> dict[str, Any]:
    """Fetch one album via get_album for NRD pending metadata."""
    try:
        if _scraper_uses_legacy_init():
            return {
                "success": False,
                "error": "Album lookup requires spotifyscraper 3.x",
                "album": None,
            }
        from spotify_scraper import SpotifyClient as ScraperClient

        with ScraperClient() as client:
            album = client.get_album(album_id)
            data = _scraper_model_to_dict(album)
        normalized = _normalize_scraper_album(data, fallback_artist_id=fallback_artist_id)
        return {"success": True, "album": normalized}
    except Exception as e:
        return {"success": False, "error": f"Scraper failed: {e}", "album": None}


def _scraper_get_artist(artist_id: str) -> dict[str, Any]:
    try:
        if _scraper_uses_legacy_init():
            from spotify_scraper import SpotifyClient as ScraperClient

            client = ScraperClient(browser_type="requests")
            try:
                data = client.get_artist_info(artist_id)
                if not isinstance(data, dict):
                    data = _scraper_model_to_dict(data)
            finally:
                client.close()
        else:
            from spotify_scraper import SpotifyClient as ScraperClient

            with ScraperClient() as client:
                data = _scraper_model_to_dict(client.get_artist(artist_id))
        if not data.get("id") and not data.get("name"):
            return {"success": False, "error": "Artist not found", "name": None}
        return {
            "success": True,
            "id": data.get("id"),
            "name": data.get("name"),
        }
    except Exception as e:
        return {"success": False, "error": f"Scraper failed: {e}", "name": None}


def _scraper_search_artists(name: str, limit: int = 5) -> dict[str, Any]:
    try:
        if _scraper_uses_legacy_init():
            return {
                "success": False,
                "error": "Artist search requires spotifyscraper 3.x",
                "artists": [],
            }
        from spotify_scraper import SpotifyClient as ScraperClient

        with ScraperClient() as client:
            results = client.search(name)
            data = _scraper_model_to_dict(results)
        artists_raw = data.get("artists") or []
        artists = []
        for artist in artists_raw[:limit]:
            if not isinstance(artist, dict):
                artist = _scraper_model_to_dict(artist)
            aid = artist.get("id")
            if not aid:
                continue
            share_url = artist.get("share_url") or f"https://open.spotify.com/artist/{aid}"
            artists.append(
                {
                    "id": aid,
                    "name": artist.get("name"),
                    "uri": artist.get("uri"),
                    "external_url": share_url,
                }
            )
        return {"success": True, "artists": artists}
    except Exception as e:
        return {"success": False, "error": f"Scraper failed: {e}", "artists": []}


def _scraper_get_album(album_id: str) -> dict[str, Any]:
    try:
        if _scraper_uses_legacy_init():
            return {
                "success": False,
                "error": "Album lookup requires spotifyscraper 3.x",
            }
        from spotify_scraper import SpotifyClient as ScraperClient

        with ScraperClient() as client:
            album = client.get_album(album_id)
            data = _scraper_model_to_dict(album)
        artists = data.get("artists") or []
        artist_id = artists[0].get("id") if artists and isinstance(artists[0], dict) else ""
        artist_name = artists[0].get("name") if artists and isinstance(artists[0], dict) else ""
        album_url = data.get("share_url") or f"https://open.spotify.com/album/{album_id}"
        return {
            "success": True,
            "id": data.get("id", album_id),
            "title": data.get("name", ""),
            "artist_id": artist_id,
            "artist_name": artist_name,
            "release_date": data.get("release_date", ""),
            "record_type": (data.get("album_type") or "album").lower(),
            "nb_tracks": int(data.get("total_tracks") or 0),
            "album_url": album_url,
        }
    except Exception as e:
        return {"success": False, "error": f"Scraper failed: {e}"}


def _scraper_get_artist_albums(
    artist_id: str,
    include_groups: str = "album,ep,single,compilation,appears_on",
    fetch_all: bool = True,
    limit: int = 50,
) -> dict[str, Any]:
    if not _scraper_supports_discography():
        return {
            "success": False,
            "error": "spotifyscraper 3.x required for discography (get_discography)",
            "albums": [],
        }
    try:
        from spotify_scraper import SpotifyClient as ScraperClient

        with ScraperClient() as client:
            all_albums: list[dict[str, Any]] = []
            for release in _scraper_iter_discography_releases(client, artist_id):
                normalized = _normalize_scraper_discography_release(release, artist_id)
                if not normalized:
                    continue
                if not _scraper_album_type_in_groups(normalized["album_type"], include_groups):
                    continue
                all_albums.append(normalized)
                if not fetch_all and len(all_albums) >= limit:
                    break

        return {"success": True, "albums": all_albums}
    except Exception as e:
        return {"success": False, "error": f"Scraper failed: {e}", "albums": []}


def probe_scraper_discography(artist_id: str = "4Z8W4fKeB5YxbusRsdQVPb") -> bool:
    """Lightweight probe for NRD source availability."""
    if not _scraper_supports_discography():
        return False
    try:
        from spotify_scraper import SpotifyClient as ScraperClient

        with ScraperClient() as client:
            client.get_artist(artist_id)
        return True
    except Exception:
        return False


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

    def _get_cred_hash(self) -> str:
        """Hash of credentials for cache invalidation when they change."""
        raw = f"{self.client_id or ''}:{self.client_secret or ''}"
        return hashlib.sha256(raw.encode()).hexdigest()[:16]

    def _get_api_usable_cached(self) -> bool | None:
        """
        Get cached API usability. Returns True/False if valid cache, None if needs evaluation.
        Cache is invalid when credentials have changed.
        """
        cache = config_service.get("SPOTIFY_API_CACHE") or {}
        if not isinstance(cache, dict):
            return None
        cred_hash = cache.get("cred_hash")
        if cred_hash != self._get_cred_hash():
            return None
        if "usable" not in cache:
            return None
        return bool(cache["usable"])

    def _update_api_cache(self, usable: bool):
        """Persist API usability to hidden config."""
        cache = {"usable": usable, "cred_hash": self._get_cred_hash()}
        config_service.set("SPOTIFY_API_CACHE", json.dumps(cache), "json")

    async def _probe_api_usable(self) -> bool:
        """
        Make one lightweight API call to determine if API works (not 403 Premium required).
        Does not log at ERROR level - used for cache evaluation.
        """
        if not await self._ensure_valid_token():
            return False
        url = "https://api.spotify.com/v1/tracks/4iV5W9uYEdYUVa79Axb7Rh"
        try:
            if not self.session:
                self.session = aiohttp.ClientSession(headers=self.headers)
            self.headers["Authorization"] = f"Bearer {self.access_token}"
            async with self.session.get(url) as resp:
                if resp.status == 200:
                    return True
                if resp.status == 403:
                    self.logger.debug(
                        "Spotify API returned 403 (Premium required) - caching as unusable"
                    )
                    return False
                return False
        except Exception as e:
            self.logger.debug(f"Spotify API probe failed: {e}")
            return False

    def _should_skip_api(self) -> bool:
        """
        True if we should skip the API and go straight to scraper (avoids token fetch + 403).
        Evaluates and caches on first use when credentials present.
        """
        if not self._has_credentials():
            return True
        cached = self._get_api_usable_cached()
        if cached is False:
            return True
        if cached is True:
            return False
        # Need to evaluate - will be done in get_playlist_info/get_playlist_tracks
        return False

    async def _ensure_api_evaluated(self) -> bool:
        """
        Ensure API usability is evaluated and cached. Returns True if API is usable.
        Call when cache is None (first use or credentials changed).
        """
        usable = await self._probe_api_usable()
        self._update_api_cache(usable)
        if not usable:
            self.logger.info(
                "Spotify API cached as unusable (403 Premium required) - using scraper"
            )
        return usable

    async def _can_try_api(self) -> bool:
        """True when credentials are present and API is not cached as unusable."""
        if not self._has_credentials():
            return False
        if self._should_skip_api():
            return False
        if self._get_api_usable_cached() is None:
            return await self._ensure_api_evaluated()
        return True

    async def _api_or_scraper(
        self,
        operation: str,
        api_fn,
        scraper_fn,
        *,
        tag_via: bool = False,
    ) -> dict[str, Any]:
        """Try official API when usable; fall back to spotifyscraper on failure."""
        if await self._can_try_api():
            api_result = await api_fn()
            if api_result.get("success"):
                if tag_via:
                    api_result["via"] = "api"
                return api_result
            self.logger.info(f"Spotify API unavailable for {operation} — using scraper")
        scraper_result = await scraper_fn()
        if tag_via and scraper_result.get("success"):
            scraper_result["via"] = "scraper"
        return scraper_result

    async def _get_playlist_via_scraper(self, url: str) -> dict[str, Any]:
        """Run sync scraper in executor."""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, _scraper_get_playlist, url)

    async def _run_scraper(self, func, *args, **kwargs) -> dict[str, Any]:
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, lambda: func(*args, **kwargs))

    async def _enrich_nrd_album_api(
        self, album_id: str, fallback_artist_id: str | None
    ) -> dict[str, Any]:
        result = await self._get(f"/albums/{album_id}")
        if not result:
            return {"success": False, "album": None}
        artists = result.get("artists", [])
        primary_artist_id = fallback_artist_id
        if artists and isinstance(artists[0], dict):
            primary_artist_id = artists[0].get("id") or primary_artist_id
        external_url = result.get("external_urls", {}).get("spotify", "")
        return {
            "success": True,
            "album": {
                "id": result.get("id", album_id),
                "name": result.get("name", ""),
                "release_date": result.get("release_date", ""),
                "release_date_precision": result.get("release_date_precision", "year"),
                "album_type": (result.get("album_type") or "album").lower(),
                "total_tracks": int(result.get("total_tracks") or 0),
                "primary_artist_id": primary_artist_id,
                "external_url": external_url,
                "spotify_url": external_url,
            },
        }

    async def enrich_nrd_album(self, album: dict[str, Any]) -> dict[str, Any]:
        """Fetch full album metadata for a discography candidate."""
        album_id = album.get("id")
        if not album_id:
            return album
        fallback_artist_id = album.get("primary_artist_id")

        async def api_fn():
            return await self._enrich_nrd_album_api(album_id, fallback_artist_id)

        async def scraper_fn():
            return await self._run_scraper(_scraper_enrich_nrd_album, album_id, fallback_artist_id)

        result = await self._api_or_scraper("enrich_nrd_album", api_fn, scraper_fn)
        if result.get("success") and result.get("album"):
            return result["album"]
        return album

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
        Skips API entirely when cached as unusable (403 Premium) to avoid repeated token fetch.
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

            # Skip API when cached as unusable (403 Premium) - avoids token fetch + 403 every sync
            if self._should_skip_api():
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

            # Evaluate API usability on first use or when credentials changed
            if self._get_api_usable_cached() is None and not await self._ensure_api_evaluated():
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
        Skips API entirely when cached as unusable (403 Premium) to avoid repeated token fetch.
        """
        try:
            parsed = parse_playlist_url(url)
            if not parsed["valid"]:
                return {"success": False, "error": parsed["error"]}

            if not self._has_credentials():
                return await self._get_playlist_via_scraper(url)

            # Skip API when cached as unusable (403 Premium) - avoids token fetch + 403 every sync
            if self._should_skip_api():
                return await self._get_playlist_via_scraper(url)

            # Evaluate API usability on first use or when credentials changed
            if self._get_api_usable_cached() is None and not await self._ensure_api_evaluated():
                return await self._get_playlist_via_scraper(url)

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

    async def _get_album_api(self, album_id: str) -> dict[str, Any]:
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

    async def get_album(self, album_id: str) -> dict[str, Any]:
        """Get album by ID. Returns artist_id, artist_name, title, album_url, etc."""
        return await self._api_or_scraper(
            "get_album",
            lambda: self._get_album_api(album_id),
            lambda: self._run_scraper(_scraper_get_album, album_id),
        )

    async def _get_artist_api(self, artist_id: str) -> dict[str, Any]:
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

    async def get_artist(self, artist_id: str) -> dict[str, Any]:
        """
        Get artist by Spotify ID (for name validation when using Lidarr's Spotify link).
        Returns dict with id, name, or error.
        """
        return await self._api_or_scraper(
            "get_artist",
            lambda: self._get_artist_api(artist_id),
            lambda: self._run_scraper(_scraper_get_artist, artist_id),
        )

    async def _search_artists_api(self, name: str, limit: int) -> dict[str, Any]:
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

    async def search_artists(self, name: str, limit: int = 5) -> dict[str, Any]:
        """
        Search for artists by name on Spotify.
        Feb 2026: search limit max 10 per request; paginate if more needed.
        """
        return await self._api_or_scraper(
            "search_artists",
            lambda: self._search_artists_api(name, limit),
            lambda: self._run_scraper(_scraper_search_artists, name, limit),
        )

    def _get_artist_albums_cache_key(self, artist_id: str, via: str) -> str:
        """Generate cache key for artist albums (separate keys per data source)."""
        if via == "scraper":
            return f"spotify_scraper_artist_albums_v1:{artist_id}"
        return f"spotify_artist_albums_v2:{artist_id}"

    async def _get_artist_albums_api(
        self,
        artist_id: str,
        limit: int,
        include_groups: str,
        fetch_all: bool,
    ) -> dict[str, Any]:
        try:
            all_albums = []
            offset = 0
            page_limit = min(limit, 50)

            while True:
                params = {"limit": page_limit, "offset": offset, "include_groups": include_groups}
                result = await self._get(f"/artists/{artist_id}/albums", params=params)

                if not result:
                    if offset == 0:
                        return {"success": False, "error": "No response", "albums": []}
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

            return {"success": True, "albums": all_albums}

        except Exception as e:
            self.logger.error(f"Error getting albums for artist {artist_id}: {e}")
            return {"success": False, "error": str(e), "albums": []}

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
            Dict with success, albums list, optional via (api|scraper), or error info
        """
        via = "api" if await self._can_try_api() else "scraper"
        cache_key = self._get_artist_albums_cache_key(artist_id, via)
        if self.cache_enabled and self.cache and fetch_all:
            cached = self.cache.get(cache_key, "spotify")
            if cached is not None:
                self.logger.debug(f"Cache hit for Spotify {via} albums: {artist_id}")
                return {"success": True, "albums": cached, "via": via}

        result = await self._api_or_scraper(
            "get_artist_albums",
            lambda: self._get_artist_albums_api(artist_id, limit, include_groups, fetch_all),
            lambda: self._run_scraper(
                _scraper_get_artist_albums,
                artist_id,
                include_groups,
                fetch_all,
                limit,
            ),
            tag_via=True,
        )

        if (
            result.get("success")
            and self.cache_enabled
            and self.cache
            and fetch_all
            and result.get("albums") is not None
        ):
            result_via = result.get("via", via)
            ck = self._get_artist_albums_cache_key(artist_id, result_via)
            ttl = getattr(self.config, "NEW_RELEASES_CACHE_DAYS", 14)
            self.cache.set(ck, "spotify", result["albums"], ttl)

        return result

    async def _test_scraper_connection(self) -> bool:
        scraper_result = await self._get_playlist_via_scraper(
            "https://open.spotify.com/playlist/37i9dQZF1DXcBWIGoYBM5M"
        )
        return bool(scraper_result.get("success"))

    async def test_connection(self) -> bool:
        """Test connection: API when credentials configured; scraper as fallback."""
        detail = await self.test_connection_detail()
        return detail.get("success", False)

    async def test_connection_detail(self) -> dict[str, Any]:
        """Test Spotify connectivity; returns success flag and human-readable message."""
        api_ok = False
        scraper_ok = False
        try:
            if self._has_credentials():
                self.logger.info("Testing connection to Spotify API...")
                if await self._can_try_api():
                    result = await self._get("/tracks/4iV5W9uYEdYUVa79Axb7Rh")
                    api_ok = bool(result)
                    if api_ok:
                        self.logger.info("Successfully connected to Spotify API")
                if not api_ok:
                    self.logger.info("Spotify API test failed — trying scraper fallback")
            else:
                self.logger.info("Testing Spotify scraper (no API credentials)...")

            scraper_ok = await self._test_scraper_connection()
            if scraper_ok:
                self.logger.info("Spotify scraper test passed")

            if api_ok:
                return {"success": True, "message": "Official API connected", "mode": "api"}
            if scraper_ok:
                if self._has_credentials():
                    return {
                        "success": True,
                        "message": "API failed; scraper connected",
                        "mode": "scraper",
                    }
                return {
                    "success": True,
                    "message": "Scraper connected (no API creds)",
                    "mode": "scraper",
                }
            return {
                "success": False,
                "message": "Both API and scraper failed",
                "mode": None,
            }

        except Exception as e:
            self.logger.error(f"Failed to connect to Spotify: {e}")
            return {"success": False, "message": "Connection test failed", "mode": None}
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
