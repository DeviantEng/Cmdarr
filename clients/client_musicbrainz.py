#!/usr/bin/env python3
"""
MusicBrainz API Client with SQLite caching
Refactored to use BaseAPIClient for reduced code duplication
"""

from difflib import SequenceMatcher
from typing import Any

import aiohttp

from __version__ import __version__

from .client_base import BaseAPIClient

# Hardcoded per MusicBrainz API guidelines: AppName/Version (contact)
# Parentheses required; project URL for maintainer contact
MUSICBRAINZ_USER_AGENT = f"Cmdarr/{__version__} (https://github.com/DeviantEng/Cmdarr)"


class MusicBrainzClient(BaseAPIClient):
    def __init__(self, config):
        headers = {"User-Agent": MUSICBRAINZ_USER_AGENT}

        super().__init__(
            config=config,
            client_name="musicbrainz",
            base_url="https://musicbrainz.org/ws/2/",
            rate_limit=config.MUSICBRAINZ_RATE_LIMIT,
            headers=headers,
        )

    def _get_cache_key(self, artist_name: str) -> str:
        """Generate cache key for MusicBrainz fuzzy search"""
        # Normalize artist name for consistent caching
        normalized_name = artist_name.lower().strip()
        return f"fuzzy_search:{normalized_name}"

    async def _make_request(self, endpoint: str, params: dict[str, str]) -> dict[str, Any] | None:
        """Make rate-limited HTTP request to MusicBrainz API using HTTP utilities with retry logic"""
        params["fmt"] = "json"  # Always request JSON format

        # Apply rate limiting (MusicBrainz: 1 req/sec per IP)
        await self._rate_limiter.acquire()

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
            max_retries=getattr(self.config, "MUSICBRAINZ_MAX_RETRIES", 3),
            retry_delay=getattr(self.config, "MUSICBRAINZ_RETRY_DELAY", 2.0),
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
        if "(" in cleaned:
            cleaned = cleaned.split("(")[0].strip()

        return cleaned

    async def fuzzy_search_artist(self, artist_name: str) -> dict[str, Any] | None:
        """Search for artist using fuzzy matching with caching"""

        # Check cache first if enabled
        cache_key = self._get_cache_key(artist_name)
        if self.cache_enabled and self.cache:
            # Check if this is a known failed lookup
            if self.cache.is_failed_lookup(cache_key, "musicbrainz"):
                self.logger.debug(f"Skipping known failed MusicBrainz lookup: {artist_name}")
                return None

            # Try to get from cache
            cached_result = self.cache.get(cache_key, "musicbrainz")
            if cached_result is not None:
                self.logger.debug(f"Cache hit for MusicBrainz fuzzy search: {artist_name}")
                return cached_result

        # Clean the artist name for searching
        search_name = self._clean_artist_name(artist_name)

        # Search parameters
        params = {
            "query": f'artist:"{search_name}"',
            "limit": "10",  # Get top 10 matches for comparison
        }

        try:
            response = await self._make_request("artist", params)

            if not response or "artists" not in response:
                self.logger.debug(f"No artists found for '{artist_name}'")

                # Cache the failure
                if self.cache_enabled and self.cache:
                    self.cache.mark_failed_lookup(
                        cache_key,
                        "musicbrainz",
                        "No artists found",
                        self.config.CACHE_MUSICBRAINZ_TTL_DAYS,
                    )
                return None

            artists = response["artists"]
            if not artists:
                # Cache the failure
                if self.cache_enabled and self.cache:
                    self.cache.mark_failed_lookup(
                        cache_key,
                        "musicbrainz",
                        "Empty artists list",
                        self.config.CACHE_MUSICBRAINZ_TTL_DAYS,
                    )
                return None

            # Find best match using similarity scoring
            best_match = None
            best_score = 0

            for artist in artists:
                mb_name = artist.get("name", "")

                # Calculate similarity score
                similarity = self._calculate_similarity(artist_name, mb_name)

                # Also check aliases for better matching
                max_alias_similarity = 0
                if "aliases" in artist:
                    for alias in artist["aliases"]:
                        alias_name = alias.get("name", "")
                        alias_similarity = self._calculate_similarity(artist_name, alias_name)
                        max_alias_similarity = max(max_alias_similarity, alias_similarity)

                # Use the better of name or alias similarity
                final_similarity = max(similarity, max_alias_similarity)

                self.logger.debug(
                    f"Artist '{mb_name}' similarity: {final_similarity:.3f} (name: {similarity:.3f}, alias: {max_alias_similarity:.3f})"
                )

                if final_similarity > best_score:
                    best_score = final_similarity
                    best_match = {
                        "mbid": artist.get("id"),
                        "name": mb_name,
                        "similarity_score": final_similarity,
                        "disambiguation": artist.get("disambiguation", ""),
                        "type": artist.get("type", ""),
                        "country": artist.get("country", ""),
                        "matched_via": "alias" if max_alias_similarity > similarity else "name",
                    }

            # Only return if similarity meets minimum threshold
            if best_match and best_score >= self.config.MUSICBRAINZ_MIN_SIMILARITY:
                self.logger.debug(
                    f"Best match for '{artist_name}': '{best_match['name']}' (score: {best_score:.3f})"
                )

                # Cache the successful result
                if self.cache_enabled and self.cache:
                    self.cache.set(
                        cache_key, "musicbrainz", best_match, self.config.CACHE_MUSICBRAINZ_TTL_DAYS
                    )

                return best_match
            else:
                self.logger.debug(
                    f"No match above threshold {self.config.MUSICBRAINZ_MIN_SIMILARITY} for '{artist_name}' (best: {best_score:.3f})"
                )

                # Cache the failure
                if self.cache_enabled and self.cache:
                    self.cache.mark_failed_lookup(
                        cache_key,
                        "musicbrainz",
                        f"No match above threshold (best: {best_score:.3f})",
                        self.config.CACHE_MUSICBRAINZ_TTL_DAYS,
                    )
                return None

        except Exception as e:
            self.logger.error(f"Error searching for artist '{artist_name}': {e}")

            # Cache the failure
            if self.cache_enabled and self.cache:
                self.cache.mark_failed_lookup(
                    cache_key,
                    "musicbrainz",
                    f"Exception: {str(e)}",
                    self.config.CACHE_MUSICBRAINZ_TTL_DAYS,
                )
            return None

    async def search_artist_candidates(
        self, artist_name: str, limit: int = 5
    ) -> list[dict[str, Any]]:
        """
        Search for artists by name and return all candidates above similarity threshold.
        """
        search_name = self._clean_artist_name(artist_name)
        params = {"query": f'artist:"{search_name}"', "limit": "10"}
        try:
            response = await self._make_request("artist", params)
            if not response or "artists" not in response:
                return []
            artists = response["artists"]
            candidates = []
            for artist in artists:
                mb_name = artist.get("name", "")
                similarity = self._calculate_similarity(artist_name, mb_name)
                max_alias_similarity = 0
                if "aliases" in artist:
                    for alias in artist["aliases"]:
                        alias_name = alias.get("name", "")
                        alias_similarity = self._calculate_similarity(artist_name, alias_name)
                        max_alias_similarity = max(max_alias_similarity, alias_similarity)
                final_similarity = max(similarity, max_alias_similarity)
                if final_similarity >= self.config.MUSICBRAINZ_MIN_SIMILARITY:
                    candidates.append(
                        {
                            "mbid": artist.get("id"),
                            "name": mb_name,
                            "similarity_score": final_similarity,
                        }
                    )
                    if len(candidates) >= limit:
                        break
            return candidates
        except Exception as e:
            self.logger.error(f"Error searching artist candidates '{artist_name}': {e}")
            return []

    def _extract_streaming_id_from_url(self, url_resource: str, provider: str) -> str | None:
        """Extract artist/album ID from MB URL relation. Returns None if no match."""
        import re
        from urllib.parse import urlparse

        if not url_resource:
            return None
        try:
            parsed = urlparse(url_resource)
            host = (parsed.netloc or "").replace("www.", "").lower()
            path = (parsed.path or "").strip("/")
            if provider == "spotify" and host in ("open.spotify.com", "spotify.com"):
                m = re.search(r"artist/([a-zA-Z0-9]+)", path)
                if m:
                    return m.group(1)
            if provider == "deezer" and host == "deezer.com":
                m = re.search(r"artist/(\d+)", path)
                if m:
                    return m.group(1)
        except Exception:
            pass
        return None

    async def get_artist_streaming_id(self, mbid: str, provider: str) -> str | None:
        """
        Get Deezer or Spotify artist ID from MusicBrainz URL relations.
        Returns None if artist has no link for the provider.
        Use when Lidarr lacks the streaming link—MB often has it (e.g. "Stream at Deezer").
        """
        try:
            response = await self._make_request(f"artist/{mbid}", {"inc": "url-rels"})
            if not response or "relations" not in response:
                return None
            for rel in response.get("relations", []):
                url_obj = rel.get("url", {})
                resource = url_obj.get("resource", "")
                extracted = self._extract_streaming_id_from_url(resource, provider)
                if extracted:
                    return str(extracted)
            return None
        except Exception as e:
            self.logger.debug(f"get_artist_streaming_id {mbid}: {e}")
            return None

    async def artist_has_streaming_link(self, mbid: str, provider: str, artist_id: str) -> bool:
        """Check if MB artist has a URL relation matching the given provider+artist_id."""
        extracted = await self.get_artist_streaming_id(mbid, provider)
        return extracted is not None and str(extracted) == str(artist_id)

    async def get_artist_most_recent_release_title(
        self, mbid: str, prefer_album: bool = True
    ) -> str | None:
        """
        Get the title of the most recent album (or EP if no albums) for an artist.
        Returns None if no albums or EPs.
        """
        try:
            params = {"artist": mbid, "limit": "100"}
            response = await self._make_request("release-group", params)
            if not response or "release-groups" not in response:
                return None
            groups = response.get("release-groups", [])
            # Filter by type: album first, then ep
            albums = [g for g in groups if g.get("primary-type") == "album"]
            eps = [g for g in groups if g.get("primary-type") == "ep"]
            candidates = albums if (prefer_album and albums) else (eps if eps else albums)
            if not candidates:
                return None

            # Sort by first-release-date desc
            def parse_date(d):
                if not d:
                    return ""
                return (d or "")[:10]

            candidates.sort(key=lambda g: parse_date(g.get("first-release-date", "")), reverse=True)
            return candidates[0].get("title")
        except Exception as e:
            self.logger.debug(f"get_artist_most_recent_release_title {mbid}: {e}")
            return None

    def _get_release_groups_cache_key(self, artist_mbid: str) -> str:
        """Generate cache key for artist release groups"""
        return f"mb_release_groups:{artist_mbid}"

    async def get_artist_release_groups(
        self, artist_mbid: str, cache_ttl_days: int = None
    ) -> list[str] | None:
        """
        Get all release group titles for an artist from MusicBrainz (1 API call per 100).
        Used for local comparison - no per-album MB lookups needed.
        Returns None on error (e.g. rate limit 503) so callers can skip adding to pending.
        """
        cache_key = self._get_release_groups_cache_key(artist_mbid)
        ttl = cache_ttl_days or getattr(self.config, "NEW_RELEASES_CACHE_DAYS", 14)
        if self.cache_enabled and self.cache:
            cached = self.cache.get(cache_key, "musicbrainz")
            if cached is not None:
                self.logger.debug(f"Cache hit for MB release groups: {artist_mbid}")
                return cached

        titles = []
        offset = 0
        limit = 100

        try:
            while True:
                params = {
                    "artist": artist_mbid,
                    "limit": str(limit),
                    "offset": str(offset),
                }
                response = await self._make_request("release-group", params)
                if not response:
                    # API error (e.g. 503 rate limit after retries) - don't cache, return None
                    self.logger.warning(
                        f"MusicBrainz API error for {artist_mbid} (possible rate limit)"
                    )
                    return None

                groups = response.get("release-groups", [])
                for rg in groups:
                    title = rg.get("title", "")
                    if title:
                        titles.append(title)

                if len(groups) < limit:
                    break
                offset += limit
                if offset >= 500:  # Safety cap
                    break

            if self.cache_enabled and self.cache:
                self.cache.set(cache_key, "musicbrainz", titles, ttl)

            return titles
        except Exception as e:
            self.logger.debug(f"MusicBrainz release groups for {artist_mbid}: {e}")
            return None

    def _get_spotify_url_cache_key(self, spotify_url: str) -> str:
        """Generate cache key for Spotify URL MusicBrainz lookup"""
        return f"mb_release_by_spotify:{spotify_url}"

    def _get_release_search_cache_key(self, artist_mbid: str, title: str) -> str:
        """Generate cache key for release search by artist+title"""
        norm = title.lower().strip()[:50]
        return f"mb_release_exists:{artist_mbid}:{norm}"

    async def release_exists_by_artist_and_title(
        self, artist_mbid: str, release_title: str, cache_ttl_days: int = None
    ) -> bool:
        """
        Check if a release exists in MusicBrainz by artist MBID and title.
        Uses fuzzy matching - catches cases like "Deconstructed" vs "Deconstructed (Live)".
        Pass cache_ttl_days=0 to bypass cache (e.g. for recheck after user adds via Harmony).
        """
        if not artist_mbid or not release_title:
            return False

        cache_key = self._get_release_search_cache_key(artist_mbid, release_title)
        skip_cache = cache_ttl_days is not None and cache_ttl_days == 0
        ttl = (
            cache_ttl_days
            if (cache_ttl_days is not None and cache_ttl_days > 0)
            else getattr(self.config, "NEW_RELEASES_CACHE_DAYS", 14)
        )

        if not skip_cache and self.cache_enabled and self.cache:
            cached = self.cache.get(cache_key, "musicbrainz")
            if cached is not None:
                return cached

        try:
            # Use word-based search to match "Deconstructed" vs "Deconstructed (Live)" etc.
            # Take first significant word (skip common articles) for broad match
            skip = {"the", "a", "an"}
            words = [
                w
                for w in release_title.replace("(", " ").replace(")", " ").split()
                if len(w) > 1 and w.lower() not in skip
            ]
            search_term = words[0] if words else release_title[:20]
            safe_term = search_term.replace('"', '\\"').replace("\\", "\\\\")
            params = {
                "query": f"arid:{artist_mbid} AND release:{safe_term}",
                "limit": "25",
            }
            response = await self._make_request("release", params)

            if not response or "releases" not in response:
                if not skip_cache and self.cache_enabled and self.cache:
                    self.cache.set(cache_key, "musicbrainz", False, ttl)
                return False

            releases = response.get("releases", [])

            for r in releases:
                mb_title = r.get("title", "")
                if self._calculate_similarity(release_title, mb_title) >= 0.7:
                    if not skip_cache and self.cache_enabled and self.cache:
                        self.cache.set(cache_key, "musicbrainz", True, ttl)
                    return True

            if not skip_cache and self.cache_enabled and self.cache:
                self.cache.set(cache_key, "musicbrainz", False, ttl)
            return False
        except Exception as e:
            self.logger.debug(f"MusicBrainz release search for {artist_mbid}/{release_title}: {e}")
            return False

    async def release_exists_by_spotify_url(
        self, spotify_url: str, cache_ttl_days: int = None
    ) -> bool:
        """
        Check if a release already exists in MusicBrainz by its Spotify URL.
        Returns True if the release is linked in MusicBrainz, False otherwise.
        """
        try:
            from urllib.parse import urlparse

            parsed = urlparse(spotify_url or "")
            host = (parsed.netloc or "").replace("www.", "").lower()
            path = parsed.path or ""
            if host != "open.spotify.com" or "/album/" not in path:
                return False
        except Exception:
            return False

        cache_key = self._get_spotify_url_cache_key(spotify_url)
        ttl = cache_ttl_days or getattr(self.config, "NEW_RELEASES_CACHE_DAYS", 14)
        if self.cache_enabled and self.cache:
            cached = self.cache.get(cache_key, "musicbrainz")
            if cached is not None:
                return cached

        try:
            params = {"query": f'url:"{spotify_url}"'}
            response = await self._make_request("url", params)

            exists = bool(response and response.get("urls") and len(response.get("urls", [])) > 0)

            if self.cache_enabled and self.cache:
                self.cache.set(cache_key, "musicbrainz", exists, ttl)

            return exists
        except Exception as e:
            self.logger.debug(f"MusicBrainz URL lookup for {spotify_url}: {e}")
            return False

    async def get_artist_by_mbid(self, mbid: str) -> dict[str, Any] | None:
        """Get artist details by MBID"""
        try:
            response = await self._make_request(f"artist/{mbid}", {})

            if response:
                return {
                    "mbid": response.get("id"),
                    "name": response.get("name"),
                    "disambiguation": response.get("disambiguation", ""),
                    "type": response.get("type", ""),
                    "country": response.get("country", ""),
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

            if result and result.get("name"):
                self.logger.info(
                    f"Connected to MusicBrainz API successfully (test artist: {result['name']})"
                )
                return True
            else:
                self.logger.error("MusicBrainz API test failed - no valid response")
                return False

        except Exception as e:
            self.logger.error(f"Failed to connect to MusicBrainz API: {e}")
            return False

    async def get_api_stats(self) -> dict[str, Any]:
        """Get basic API usage statistics"""
        stats = await super().get_api_stats()
        stats.update(
            {
                "rate_limit": self.config.MUSICBRAINZ_RATE_LIMIT,
                "min_similarity": self.config.MUSICBRAINZ_MIN_SIMILARITY,
                "user_agent": self.headers["User-Agent"],
            }
        )
        return stats
