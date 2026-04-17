#!/usr/bin/env python3
"""Ticketmaster Discovery API — keyword search for music events (US)."""

from __future__ import annotations

import re
from datetime import UTC, datetime
from typing import Any

from utils.event_geo import coerce_location_str

from .client_base import BaseAPIClient

_TOKEN_RE = re.compile(r"[a-z0-9']+")


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


class TicketmasterClient(BaseAPIClient):
    def __init__(self, config, api_key: str):
        super().__init__(
            config=config,
            client_name="ticketmaster",
            base_url="https://app.ticketmaster.com/discovery/v2",
            rate_limit=0.33,
        )
        self._api_key = api_key

    async def fetch_upcoming_events(
        self, artist_name: str, artist_mbid: str
    ) -> list[dict[str, Any]] | None:
        """Return normalized events, [] if TM returned no matches, or None on provider error.

        Callers must treat None as "unknown" (do not advance scan TTL) and [] as "scanned OK,
        TM had no events for this keyword right now".
        """
        if not artist_name or not self._api_key:
            return []
        data = await self._get(
            "/events.json",
            params={
                "apikey": self._api_key,
                "keyword": artist_name,
                "countryCode": "US",
                "classificationName": "Music",
                "size": "50",
                "sort": "date,asc",
            },
        )
        if data is None:
            return None
        if not isinstance(data, dict):
            return []
        emb = data.get("_embedded") or {}
        evs = emb.get("events") or []
        if isinstance(evs, dict):
            evs = [evs]
        out: list[dict[str, Any]] = []
        now = datetime.now(UTC)
        for ev in evs:
            if not self._event_matches_artist(ev, artist_name, artist_mbid):
                continue
            norm = self._normalize_event(ev, artist_mbid, artist_name, now)
            if norm:
                out.append(norm)
        return out

    @staticmethod
    def _event_matches_artist(ev: dict[str, Any], artist_name: str, artist_mbid: str = "") -> bool:
        """
        Decide whether a TM keyword-search event genuinely features this artist.

        Prefer MBID match via `_embedded.attractions[*].externalLinks.musicbrainz[*].id`.
        If TM provides MBIDs for any attraction on the event and none match our MBID, the
        event is rejected outright — this kills the "substring of artist name matches some
        unrelated short attraction title" false positives we were seeing.

        Fall back to whole-phrase, token-aligned match of the artist name inside an
        attraction name (or the event title if the event has no attractions at all).
        """
        artist_tokens = _tokens(artist_name)
        if not artist_tokens:
            return False
        emb = ev.get("_embedded") or {}
        attractions = emb.get("attractions") or []

        if artist_mbid:
            mb_target = artist_mbid.lower().strip()
            any_mbid_seen = False
            for att in attractions:
                mbs = (att.get("externalLinks") or {}).get("musicbrainz") or []
                for mb in mbs:
                    mid = (mb.get("id") or "").lower().strip()
                    if not mid:
                        continue
                    any_mbid_seen = True
                    if mid == mb_target:
                        return True
            if any_mbid_seen:
                return False

        for att in attractions:
            if _contains_phrase(_tokens(att.get("name") or ""), artist_tokens):
                return True

        if not attractions:
            return _contains_phrase(_tokens(ev.get("name") or ""), artist_tokens)
        return False

    def _normalize_event(
        self, ev: dict[str, Any], artist_mbid: str, artist_name: str, now: datetime
    ) -> dict[str, Any] | None:
        dates = ev.get("dates") or {}
        start = dates.get("start") or {}
        dt_raw = start.get("dateTime") or start.get("localDate")
        if not dt_raw:
            return None
        try:
            if "T" in str(dt_raw):
                s = str(dt_raw).replace("Z", "+00:00")
                starts = datetime.fromisoformat(s)
            else:
                starts = datetime.strptime(str(dt_raw)[:10], "%Y-%m-%d").replace(tzinfo=UTC)
            if starts.tzinfo is None:
                starts = starts.replace(tzinfo=UTC)
            else:
                starts = starts.astimezone(UTC)
        except ValueError, TypeError:
            return None
        if starts < now:
            return None

        emb = ev.get("_embedded") or {}
        venues = emb.get("venues") or []
        venue = venues[0] if venues else {}
        loc = venue.get("location") or {}
        lat_s = loc.get("latitude")
        lon_s = loc.get("longitude")
        try:
            lat_f = float(lat_s) if lat_s is not None else None
            lon_f = float(lon_s) if lon_s is not None else None
        except TypeError, ValueError:
            lat_f, lon_f = None, None

        addr = venue.get("address") or {}
        state = venue.get("state") or addr.get("line2")
        city = venue.get("city") or {}
        city_name = city.get("name") if isinstance(city, dict) else None
        country_raw = venue.get("country")
        if country_raw is None:
            country_raw = "US"

        provider_local = str(start.get("localDate") or "")[:10]
        local_date = provider_local if provider_local else starts.date().isoformat()
        ext_id = str(ev.get("id") or "")

        return {
            "provider": "ticketmaster",
            "external_id": ext_id[:256] if ext_id else f"tm-{artist_mbid}-{local_date}",
            "source_url": (ev.get("url") or "")[:1024] or None,
            "artist_mbid": artist_mbid,
            "artist_name": artist_name,
            "venue_name": coerce_location_str(venue.get("name")),
            "venue_city": coerce_location_str(city_name),
            "venue_region": coerce_location_str(state),
            "venue_country": coerce_location_str(country_raw),
            "venue_lat": lat_f,
            "venue_lon": lon_f,
            "starts_at_utc": starts,
            "local_date": local_date,
        }

    async def test_connection(self) -> bool:
        return bool(self._api_key)
