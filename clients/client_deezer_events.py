#!/usr/bin/env python3
"""Deezer Pipe GraphQL — artist live events (Songkick-sourced, unofficial API)."""

from __future__ import annotations

import json
import logging
import re
from datetime import UTC, datetime
from typing import Any

import aiohttp

from utils.deezer_gql_auth import DeezerGqlAuth
from utils.event_geo import coerce_location_str, parse_place_city_region

logger = logging.getLogger("cmdarr.deezer_events")

_TOKEN_RE = re.compile(r"[a-z0-9']+")

_ARTIST_LIVE_EVENTS_QUERY = """
query ArtistLiveEvents($artistId: String!, $first: Int!) {
  artist(artistId: $artistId) {
    id
    name
    liveEvents(first: $first, types: [CONCERT, FESTIVAL], statuses: [PENDING, STARTED]) {
      edges {
        node {
          id
          name
          startDate
          venue
          cityName
          countryCode
          status
          types { isConcert isFestival }
          sources { defaultUrl }
        }
      }
    }
  }
}
"""


def _tokens(text: str) -> list[str]:
    return _TOKEN_RE.findall((text or "").lower())


def _contains_phrase(haystack_tokens: list[str], needle_tokens: list[str]) -> bool:
    if not needle_tokens or len(needle_tokens) > len(haystack_tokens):
        return False
    n = len(needle_tokens)
    for i in range(len(haystack_tokens) - n + 1):
        if haystack_tokens[i : i + n] == needle_tokens:
            return True
    return False


def _pick_artist_from_search(
    artists: list[dict[str, Any]], artist_name: str
) -> dict[str, Any] | None:
    if not artists:
        return None
    target = (artist_name or "").strip().lower()
    for a in artists:
        if (a.get("name") or "").strip().lower() == target:
            return a
    return artists[0]


class DeezerEventsClient:
    """Fetch upcoming concerts via Deezer's undocumented Pipe GraphQL API."""

    PIPE_URL = "https://pipe.deezer.com/api"
    REST_SEARCH_URL = "https://api.deezer.com/search/artist"

    def __init__(self, config, arl: str):
        self.config = config
        self._arl = (arl or "").strip()
        self.session: aiohttp.ClientSession | None = None
        self._auth: DeezerGqlAuth | None = None
        self.logger = logger

    async def __aenter__(self):
        if not self.session:
            self.session = aiohttp.ClientSession()
            self._auth = DeezerGqlAuth(self._arl, session=self.session)
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self._auth:
            await self._auth.close()
            self._auth = None
        if self.session:
            await self.session.close()
            self.session = None

    async def fetch_upcoming_events(
        self,
        artist_name: str,
        artist_mbid: str,
        deezer_artist_id: str | None = None,
    ) -> tuple[list[dict[str, Any]] | None, str | None]:
        """Return (normalized events, resolved deezer artist id). None events = provider error."""
        if not artist_name or not self._arl:
            return [], deezer_artist_id

        resolved_id = (deezer_artist_id or "").strip() or None
        if not resolved_id:
            resolved_id = await self._resolve_artist_id_rest(artist_name)
            if resolved_id is None:
                return None, None
            if not resolved_id:
                return [], None

        payload = await self._gql(
            _ARTIST_LIVE_EVENTS_QUERY,
            {"artistId": resolved_id, "first": 50},
            "ArtistLiveEvents",
        )
        if payload is None:
            return None, resolved_id
        if payload.get("errors") and not (payload.get("data") or {}).get("artist"):
            return None, resolved_id
        artist = (payload.get("data") or {}).get("artist") or {}
        edges = ((artist.get("liveEvents") or {}).get("edges")) or []
        now = datetime.now(UTC)
        out: list[dict[str, Any]] = []
        for edge in edges:
            node = edge.get("node") if isinstance(edge, dict) else None
            if not isinstance(node, dict):
                continue
            if not _event_features_artist(node, artist_name):
                continue
            norm = self._normalize_event(node, artist_mbid, artist_name, now, resolved_id)
            if norm:
                out.append(norm)
        return out, resolved_id

    async def _resolve_artist_id_rest(self, artist_name: str) -> str | None:
        if not self.session:
            self.session = aiohttp.ClientSession()
        try:
            async with self.session.get(
                self.REST_SEARCH_URL,
                params={"q": artist_name, "limit": "10"},
                timeout=aiohttp.ClientTimeout(total=15),
            ) as resp:
                if resp.status != 200:
                    self.logger.warning("Deezer REST artist search HTTP %s", resp.status)
                    return None
                data = await resp.json()
        except Exception as exc:
            self.logger.warning("Deezer REST artist search failed: %s", exc)
            return None
        items = ((data.get("data") or []) if isinstance(data, dict) else []) or []
        picked = _pick_artist_from_search(items, artist_name)
        if not picked:
            return ""
        return str(picked.get("id") or "")

    async def _gql(
        self, query: str, variables: dict[str, Any], operation_name: str
    ) -> dict[str, Any] | None:
        if not self._auth:
            return None
        token = await self._auth.get_bearer_token()
        if not token:
            self.logger.warning("Deezer GraphQL skipped: no JWT from ARL")
            return None
        if not self.session:
            self.session = aiohttp.ClientSession()
        try:
            async with self.session.post(
                self.PIPE_URL,
                json={"query": query, "variables": variables, "operationName": operation_name},
                headers={
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "application/json",
                },
                timeout=aiohttp.ClientTimeout(total=30),
            ) as resp:
                body = await resp.read()
                if resp.status != 200:
                    self.logger.warning("Deezer GraphQL HTTP %s", resp.status)
                    return None
                return json.loads(body)
        except Exception as exc:
            self.logger.warning("Deezer GraphQL request failed: %s", exc)
            return None

    async def test_connection(self) -> bool:
        if not self._arl:
            return False
        async with self:
            token = await self._auth.get_bearer_token() if self._auth else None
            return bool(token)

    def _normalize_event(
        self,
        node: dict[str, Any],
        artist_mbid: str,
        artist_name: str,
        now: datetime,
        deezer_artist_id: str,
    ) -> dict[str, Any] | None:
        dt_raw = node.get("startDate")
        if not dt_raw:
            return None
        local_date = str(dt_raw)[:10]
        try:
            if "T" in str(dt_raw):
                s = str(dt_raw).replace("Z", "+00:00")
                starts = datetime.fromisoformat(s)
            else:
                starts = datetime.strptime(local_date, "%Y-%m-%d").replace(tzinfo=UTC)
            if starts.tzinfo is None:
                starts = starts.replace(tzinfo=UTC)
            else:
                starts = starts.astimezone(UTC)
        except ValueError, TypeError:
            return None
        if starts < now:
            return None

        types = node.get("types") or {}
        is_festival = bool(types.get("isFestival"))
        event_kind = "festival" if is_festival else "show"
        festival_key = None
        if is_festival:
            title = (node.get("name") or "").strip().lower()
            slug = re.sub(r"[^a-z0-9]+", "-", title).strip("-")[:80]
            year = local_date[:4] if local_date else ""
            if slug and year:
                festival_key = f"dzfest:{slug}:{year}"

        sources = node.get("sources") or {}
        source_url = (sources.get("defaultUrl") or "").strip()
        if not source_url:
            source_url = f"https://www.deezer.com/en/artist/{deezer_artist_id}"

        ext_id = str(node.get("id") or "")
        raw_city = coerce_location_str(node.get("cityName"))
        country = coerce_location_str(node.get("countryCode"))
        venue_city, venue_region = parse_place_city_region(raw_city, None)
        return {
            "provider": "deezer",
            "external_id": ext_id[:256] if ext_id else f"dz-{artist_mbid}-{local_date}",
            "source_url": source_url[:1024] or None,
            "event_kind": event_kind,
            "festival_key": festival_key,
            "provider_event_name": (node.get("name") or "")[:500] or None,
            "artist_mbid": artist_mbid,
            "artist_name": artist_name,
            "venue_name": coerce_location_str(node.get("venue")),
            "venue_city": venue_city,
            "venue_region": venue_region,
            "venue_country": country,
            "venue_lat": None,
            "venue_lon": None,
            "starts_at_utc": starts,
            "local_date": local_date,
        }


def _event_features_artist(node: dict[str, Any], artist_name: str) -> bool:
    title = node.get("name") or ""
    return _contains_phrase(_tokens(title), _tokens(artist_name)) or bool(title)
