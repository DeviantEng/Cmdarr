#!/usr/bin/env python3
"""
Last.fm API Client with SQLite caching
Refactored to use BaseAPIClient for reduced code duplication
"""

from typing import Any

from .client_base import BaseAPIClient


class LastFMClient(BaseAPIClient):
    def __init__(self, config):
        super().__init__(
            config=config,
            client_name="lastfm",
            base_url="http://ws.audioscrobbler.com/2.0/",
            rate_limit=config.LASTFM_RATE_LIMIT,
        )

    def _get_similar_cache_key(
        self,
        mbid: str | None = None,
        artist_name: str | None = None,
        playlist: bool = False,
    ) -> str:
        """Cache key for artist.getsimilar; playlist variant merges name-only similar artists."""
        if mbid:
            base = f"similar_mbid:{mbid}"
        else:
            base = f"similar_name:{artist_name or ''}"
        return f"{base}:pl" if playlist else base

    async def _make_request(
        self, params: dict[str, str], context_info: str = None
    ) -> dict[str, Any] | None:
        """Make rate-limited HTTP request to Last.fm API"""
        # Add common parameters
        params.update({"api_key": self.config.LASTFM_API_KEY, "format": "json"})

        # Use parent class method
        return await super()._make_request("", params=params)

    def _process_similar_artist_rows(
        self,
        artists: list,
        include_similar_without_mbid: bool,
    ) -> tuple[list, list]:
        processed_artists = []
        skipped_artists = []

        for artist in artists:
            name = (artist.get("name") or "").strip()
            match_score = artist.get("match", "0")
            try:
                float(match_score)
            except ValueError, TypeError:
                skipped_artists.append(
                    {
                        "name": artist.get("name", ""),
                        "match": match_score,
                        "url": artist.get("url", ""),
                        "reason": "invalid_match_score",
                    }
                )
                self.logger.warning(
                    f"Invalid match score for {artist.get('name', 'unknown')}: {match_score}"
                )
                continue

            if not artist.get("mbid"):
                if include_similar_without_mbid and name:
                    processed_artists.append(
                        {
                            "name": name,
                            "mbid": "",
                            "match": match_score,
                            "url": artist.get("url", ""),
                        }
                    )
                else:
                    skipped_artists.append(
                        {
                            "name": artist.get("name", ""),
                            "match": match_score,
                            "url": artist.get("url", ""),
                            "reason": "no_mbid",
                        }
                    )
                    self.logger.debug(
                        f"Skipping similar artist '{artist.get('name', 'unknown')}' - no MBID"
                    )
                continue

            processed_artists.append(
                {
                    "name": artist.get("name", ""),
                    "mbid": artist.get("mbid", ""),
                    "match": match_score,
                    "url": artist.get("url", ""),
                }
            )

        return processed_artists, skipped_artists

    async def get_similar_artists(
        self,
        mbid: str | None = None,
        artist_name: str | None = None,
        limit: int | None = None,
        include_similar_without_mbid: bool = False,
    ) -> tuple:
        """Get similar artists via Last.fm artist.getsimilar (MBID and/or name) with caching.

        Args:
            mbid: Optional MusicBrainz artist ID; if omitted/empty, uses name-only request.
            artist_name: Artist name (required for name-only lookup; used as MBID fallback).
            limit: Max similar artists to request (overrides config if provided).
            include_similar_without_mbid: If True, similar rows without MBID are returned in
                processed_artists (for playlist generation). Discovery should leave this False.
        """
        similar_limit = limit if limit is not None else self.config.LASTFM_SIMILAR_COUNT
        mbid = (mbid or "").strip() or None
        name_clean = (artist_name or "").strip() or None
        if not mbid and not name_clean:
            return [], []

        playlist = bool(include_similar_without_mbid)
        cache_key = self._get_similar_cache_key(
            mbid=mbid, artist_name=name_clean, playlist=playlist
        )

        if self.cache_enabled and self.cache:
            if self.cache.is_failed_lookup(cache_key, "lastfm"):
                self.logger.debug(f"Skipping known failed similar lookup: {cache_key}")
                return [], []

            cached_result = self.cache.get(cache_key, "lastfm")
            if cached_result is not None:
                self.logger.debug(f"Cache hit for Last.fm similar artists: {cache_key}")
                proc = cached_result.get("processed", [])[:similar_limit]
                skip = cached_result.get("skipped", [])
                return proc, skip

        params: dict[str, str] = {}
        response = None

        try:
            if mbid:
                params = {"method": "artist.getsimilar", "mbid": mbid, "limit": str(similar_limit)}
                response = await self._make_request(
                    params, context_info=f"artist '{name_clean}' (MBID: {mbid})"
                )

            if not response and name_clean:
                if mbid:
                    self.logger.debug(
                        f"MBID lookup failed for '{name_clean}' (MBID: {mbid}), trying name-based query"
                    )
                params = {
                    "method": "artist.getsimilar",
                    "artist": name_clean,
                    "limit": str(similar_limit),
                }
                response = await self._make_request(
                    params, context_info=f"artist '{name_clean}' (name)"
                )

            if not response:
                if self.cache_enabled and self.cache:
                    self.cache.mark_failed_lookup(
                        cache_key,
                        "lastfm",
                        "API request failed",
                        self.config.CACHE_FAILED_LOOKUP_TTL_DAYS,
                    )
                return [], []

            similar_data = response.get("similarartists", {})
            artists = similar_data.get("artist", [])
            if isinstance(artists, dict):
                artists = [artists]

            processed_artists, skipped_artists = self._process_similar_artist_rows(
                artists, include_similar_without_mbid
            )

            ctx = f"MBID {mbid}" if mbid and "mbid" in params else f"artist {name_clean}"
            self.logger.debug(
                f"Found {len(processed_artists)} similar artists (processed), "
                f"{len(skipped_artists)} skipped for {ctx}"
            )

            if self.cache_enabled and self.cache:
                cache_data = {"processed": processed_artists, "skipped": skipped_artists}
                self.cache.set(cache_key, "lastfm", cache_data, self.config.CACHE_LASTFM_TTL_DAYS)

            return processed_artists[:similar_limit], skipped_artists

        except Exception as e:
            self.logger.error(f"Error getting similar artists for {cache_key}: {e}")

            if self.cache_enabled and self.cache:
                self.cache.mark_failed_lookup(
                    cache_key,
                    "lastfm",
                    f"Exception: {str(e)}",
                    self.config.CACHE_FAILED_LOOKUP_TTL_DAYS,
                )

            return [], []

    async def get_top_tracks(self, artist_name: str, limit: int = 10) -> list[dict[str, Any]]:
        """
        Get top tracks for an artist via artist.getTopTracks.
        Returns list of {name, artist, playcount} for matching against library.
        """
        if not artist_name or not str(artist_name).strip():
            return []

        cache_key = f"toptracks:{artist_name}:{limit}"
        if self.cache_enabled and self.cache:
            if self.cache.is_failed_lookup(cache_key, "lastfm"):
                return []
            cached = self.cache.get(cache_key, "lastfm")
            if cached is not None:
                self.logger.debug(f"Cache hit for top tracks: {artist_name}")
                return cached.get("tracks", [])

        params = {
            "method": "artist.getTopTracks",
            "artist": artist_name.strip(),
            "limit": str(min(limit, 50)),
        }
        try:
            response = await self._make_request(
                params, context_info=f"top tracks for '{artist_name}'"
            )
            if not response:
                if self.cache_enabled and self.cache:
                    self.cache.mark_failed_lookup(
                        cache_key,
                        "lastfm",
                        "API request failed",
                        self.config.CACHE_FAILED_LOOKUP_TTL_DAYS,
                    )
                return []

            toptracks = response.get("toptracks", {})
            track_list = toptracks.get("track", [])
            if isinstance(track_list, dict):
                track_list = [track_list]

            tracks = []
            for t in track_list:
                name = t.get("name", "").strip()
                art = t.get("artist", {})
                artist = art.get("name", artist_name) if isinstance(art, dict) else artist_name
                if name:
                    tracks.append(
                        {
                            "name": name,
                            "artist": artist,
                            "playcount": int(t.get("playcount", 0)),
                        }
                    )

            if self.cache_enabled and self.cache:
                self.cache.set(
                    cache_key,
                    "lastfm",
                    {"tracks": tracks},
                    self.config.CACHE_LASTFM_TTL_DAYS,
                )
            return tracks
        except Exception as e:
            self.logger.error(f"Error getting top tracks for {artist_name}: {e}")
            if self.cache_enabled and self.cache:
                self.cache.mark_failed_lookup(
                    cache_key,
                    "lastfm",
                    str(e),
                    self.config.CACHE_FAILED_LOOKUP_TTL_DAYS,
                )
            return []

    async def get_artist_info(
        self, mbid: str = None, artist_name: str = None
    ) -> dict[str, Any] | None:
        """Get artist information by MBID or name (for validation)"""
        if not mbid and not artist_name:
            self.logger.error("Either MBID or artist name must be provided")
            return None

        params = {"method": "artist.getinfo"}

        if mbid:
            params["mbid"] = mbid
        else:
            params["artist"] = artist_name

        try:
            response = await self._make_request(params)

            if not response:
                return None

            artist_data = response.get("artist", {})
            return {
                "name": artist_data.get("name", ""),
                "mbid": artist_data.get("mbid", ""),
                "url": artist_data.get("url", ""),
                "playcount": artist_data.get("stats", {}).get("playcount", 0),
                "listeners": artist_data.get("stats", {}).get("listeners", 0),
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

            if result and result.get("name"):
                self.logger.info(
                    f"Connected to Last.fm API successfully (test artist: {result['name']})"
                )
                return True
            else:
                self.logger.error("Last.fm API test failed - no valid response")
                return False

        except Exception as e:
            self.logger.error(f"Failed to connect to Last.fm API: {e}")
            return False

    async def get_api_stats(self) -> dict[str, Any]:
        """Get basic API usage statistics"""
        stats = await super().get_api_stats()
        stats.update(
            {
                "rate_limit": self.config.LASTFM_RATE_LIMIT,
                "similar_count_per_request": self.config.LASTFM_SIMILAR_COUNT,
                "min_match_score": self.config.LASTFM_MIN_MATCH_SCORE,
            }
        )
        return stats
