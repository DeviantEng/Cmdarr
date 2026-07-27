#!/usr/bin/env python3
"""
Last.fm API Client with SQLite caching
Refactored to use BaseAPIClient for reduced code duplication
"""

from typing import Any

from utils.similarr_images import pick_lastfm_image_url

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
                            "image_url": pick_lastfm_image_url(artist.get("image")),
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
                    "image_url": pick_lastfm_image_url(artist.get("image")),
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

    def _parse_top_tracks_response(
        self, response: dict[str, Any] | None, default_artist: str
    ) -> list[dict[str, Any]]:
        if not response:
            return []
        if response.get("error"):
            self.logger.debug(
                "Last.fm top tracks error %s: %s",
                response.get("error"),
                response.get("message", ""),
            )
            return []
        toptracks = response.get("toptracks", {})
        track_list = toptracks.get("track", [])
        if isinstance(track_list, dict):
            track_list = [track_list]

        tracks: list[dict[str, Any]] = []
        for t in track_list:
            name = t.get("name", "").strip()
            art = t.get("artist", {})
            artist = art.get("name", default_artist) if isinstance(art, dict) else default_artist
            if name:
                tracks.append(
                    {
                        "name": name,
                        "artist": artist,
                        "playcount": int(t.get("playcount", 0)),
                    }
                )
        return tracks

    async def get_top_tracks(
        self,
        artist_name: str,
        limit: int = 10,
        *,
        mbid: str | None = None,
    ) -> list[dict[str, Any]]:
        """
        Get top tracks for an artist via artist.getTopTracks.
        Returns list of {name, artist, playcount} for matching against library.
        Tries MBID first when provided, then falls back to artist name (like get_similar_artists).
        """
        mbid = (mbid or "").strip() or None
        name_clean = (artist_name or "").strip()
        if not mbid and not name_clean:
            return []

        limit_str = str(min(limit, 50))
        default_artist = name_clean or artist_name or ""

        async def _request_top_tracks(params: dict[str, str], context: str) -> list[dict[str, Any]]:
            response = await self._make_request(params, context_info=context)
            return self._parse_top_tracks_response(response, default_artist)

        tracks: list[dict[str, Any]] = []
        mbid_cache_key = f"toptracks:mbid:{mbid}:{limit}" if mbid else None
        name_cache_key = f"toptracks:name:{name_clean.lower()}:{limit}" if name_clean else None

        try:
            if mbid:
                if self.cache_enabled and self.cache:
                    if self.cache.is_failed_lookup(mbid_cache_key, "lastfm"):
                        pass
                    else:
                        cached = self.cache.get(mbid_cache_key, "lastfm")
                        if cached is not None:
                            self.logger.debug(f"Cache hit for top tracks MBID: {mbid}")
                            tracks = cached.get("tracks", [])
                            if tracks:
                                return tracks

                if not tracks:
                    params = {
                        "method": "artist.getTopTracks",
                        "mbid": mbid,
                        "limit": limit_str,
                    }
                    context = f"top tracks for '{name_clean}' (MBID: {mbid})"
                    tracks = await _request_top_tracks(params, context)
                    if tracks and self.cache_enabled and self.cache:
                        self.cache.set(
                            mbid_cache_key,
                            "lastfm",
                            {"tracks": tracks},
                            self.config.CACHE_LASTFM_TTL_DAYS,
                        )
                    if tracks:
                        return tracks

            if name_clean:
                if self.cache_enabled and self.cache:
                    if self.cache.is_failed_lookup(name_cache_key, "lastfm"):
                        return []
                    cached = self.cache.get(name_cache_key, "lastfm")
                    if cached is not None:
                        self.logger.debug(f"Cache hit for top tracks name: {name_clean}")
                        return cached.get("tracks", [])

                if mbid:
                    self.logger.debug(
                        f"MBID top tracks empty for '{name_clean}' (MBID: {mbid}), "
                        "trying name-based query"
                    )
                params = {
                    "method": "artist.getTopTracks",
                    "artist": name_clean,
                    "limit": limit_str,
                }
                context = f"top tracks for '{name_clean}' (name)"
                tracks = await _request_top_tracks(params, context)
                if self.cache_enabled and self.cache and tracks:
                    self.cache.set(
                        name_cache_key,
                        "lastfm",
                        {"tracks": tracks},
                        self.config.CACHE_LASTFM_TTL_DAYS,
                    )
                return tracks

            return []
        except Exception as e:
            self.logger.error(f"Error getting top tracks for {mbid or name_clean}: {e}")
            if self.cache_enabled and self.cache:
                fail_key = name_cache_key or mbid_cache_key
                if fail_key:
                    self.cache.mark_failed_lookup(
                        fail_key,
                        "lastfm",
                        str(e),
                        self.config.CACHE_FAILED_LOOKUP_TTL_DAYS,
                    )
            return []

    def _parse_artist_info_response(self, response: dict[str, Any] | None) -> dict[str, Any] | None:
        if not response:
            return None
        artist_data = response.get("artist", {})
        if not artist_data:
            return None
        wiki = artist_data.get("wiki") or {}
        return {
            "name": artist_data.get("name", ""),
            "mbid": artist_data.get("mbid", ""),
            "url": artist_data.get("url", ""),
            "playcount": artist_data.get("stats", {}).get("playcount", 0),
            "listeners": artist_data.get("stats", {}).get("listeners", 0),
            "bio_summary": wiki.get("summary") or "",
            "bio_content": wiki.get("content") or "",
        }

    async def get_artist_info(
        self,
        mbid: str = None,
        artist_name: str = None,
        *,
        prefer_bio: bool = False,
    ) -> dict[str, Any] | None:
        """Get artist information by MBID or name.

        Last.fm often omits wiki/bio when queried by MBID alone. When prefer_bio is True,
        name lookup (with autocorrect) is tried first, then MBID if wiki is still empty.
        """
        mbid_clean = (mbid or "").strip() or None
        name_clean = (artist_name or "").strip() or None
        if not mbid_clean and not name_clean:
            self.logger.error("Either MBID or artist name must be provided")
            return None

        try:
            if prefer_bio:
                info = None
                if name_clean:
                    info = self._parse_artist_info_response(
                        await self._make_request(
                            {
                                "method": "artist.getinfo",
                                "artist": name_clean,
                                "autocorrect": "1",
                            }
                        )
                    )
                has_bio = bool(info and (info.get("bio_summary") or info.get("bio_content")))
                if not has_bio and mbid_clean:
                    mbid_info = self._parse_artist_info_response(
                        await self._make_request({"method": "artist.getinfo", "mbid": mbid_clean})
                    )
                    if mbid_info:
                        if info:
                            # Prefer name payload; fill gaps from MBID lookup.
                            for key in (
                                "mbid",
                                "url",
                                "playcount",
                                "listeners",
                                "bio_summary",
                                "bio_content",
                            ):
                                if not info.get(key) and mbid_info.get(key):
                                    info[key] = mbid_info[key]
                        else:
                            info = mbid_info
                return info

            params: dict[str, str] = {"method": "artist.getinfo"}
            if mbid_clean:
                params["mbid"] = mbid_clean
            else:
                params["artist"] = name_clean
                params["autocorrect"] = "1"
            return self._parse_artist_info_response(await self._make_request(params))

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
