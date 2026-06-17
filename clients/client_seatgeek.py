#!/usr/bin/env python3
"""SeatGeek open API — performer-centric upcoming events."""

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


def _pick_performer(performers: list[dict[str, Any]], artist_name: str) -> dict[str, Any] | None:
    if not performers:
        return None
    target = (artist_name or "").strip().lower()
    for p in performers:
        if (p.get("name") or "").strip().lower() == target:
            return p
    return performers[0]


def _event_features_artist(ev: dict[str, Any], artist_name: str) -> bool:
    artist_tokens = _tokens(artist_name)
    if not artist_tokens:
        return False
    for p in ev.get("performers") or []:
        if _contains_phrase(_tokens(p.get("name") or ""), artist_tokens):
            return True
    return _contains_phrase(_tokens(ev.get("title") or ""), artist_tokens)


class SeatGeekClient(BaseAPIClient):
    def __init__(self, config, client_id: str):
        super().__init__(
            config=config,
            client_name="seatgeek",
            base_url="https://api.seatgeek.com/2",
            rate_limit=0.2,
        )
        self._client_id = (client_id or "").strip()

    async def fetch_upcoming_events(
        self, artist_name: str, artist_mbid: str
    ) -> list[dict[str, Any]] | None:
        if not artist_name or not self._client_id:
            return []
        performer_id = await self._resolve_performer_id(artist_name)
        if performer_id is None:
            return None
        if not performer_id:
            return []
        data = await self._get(
            "/events",
            params={
                "client_id": self._client_id,
                "performers.id": str(performer_id),
                "per_page": "50",
                "sort": "datetime_utc.asc",
            },
        )
        if data is None:
            return None
        events = data.get("events") or []
        if isinstance(events, dict):
            events = [events]
        now = datetime.now(UTC)
        out: list[dict[str, Any]] = []
        for ev in events:
            if not _event_features_artist(ev, artist_name):
                continue
            norm = self._normalize_event(ev, artist_mbid, artist_name, now)
            if norm:
                out.append(norm)
        return out

    async def _resolve_performer_id(self, artist_name: str) -> int | None:
        data = await self._get(
            "/performers",
            params={
                "client_id": self._client_id,
                "q": artist_name,
                "per_page": "10",
            },
        )
        if data is None:
            return None
        performers = data.get("performers") or []
        if isinstance(performers, dict):
            performers = [performers]
        picked = _pick_performer(performers, artist_name)
        if not picked:
            return 0
        pid = picked.get("id")
        try:
            return int(pid)
        except TypeError, ValueError:
            return 0

    def _normalize_event(
        self, ev: dict[str, Any], artist_mbid: str, artist_name: str, now: datetime
    ) -> dict[str, Any] | None:
        dt_raw = ev.get("datetime_utc") or ev.get("datetime_local")
        if not dt_raw:
            return None
        try:
            s = str(dt_raw).replace("Z", "+00:00")
            starts = datetime.fromisoformat(s)
            if starts.tzinfo is None:
                starts = starts.replace(tzinfo=UTC)
            else:
                starts = starts.astimezone(UTC)
        except ValueError, TypeError:
            return None
        if starts < now:
            return None

        venue = ev.get("venue") or {}
        loc = venue.get("location") or {}
        lat_s = loc.get("lat")
        lon_s = loc.get("lon")
        try:
            lat_f = float(lat_s) if lat_s is not None else None
            lon_f = float(lon_s) if lon_s is not None else None
        except TypeError, ValueError:
            lat_f, lon_f = None, None

        local_date = str(ev.get("datetime_local") or "")[:10] or starts.date().isoformat()
        ext_id = str(ev.get("id") or "")
        url = (ev.get("url") or "").strip()
        if url and not url.startswith("http"):
            url = f"https://seatgeek.com{url}"

        event_kind = "show"
        festival_key = None
        title = (ev.get("title") or "").strip()
        if title and re.search(r"\bfestival\b", title, re.I):
            event_kind = "festival"
            slug = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")[:80]
            year = local_date[:4] if local_date else ""
            if slug and year:
                festival_key = f"sgfest:{slug}:{year}"

        return {
            "provider": "seatgeek",
            "external_id": ext_id[:256] if ext_id else f"sg-{artist_mbid}-{local_date}",
            "source_url": url[:1024] or None,
            "event_kind": event_kind,
            "festival_key": festival_key,
            "provider_event_name": title[:500] or None,
            "artist_mbid": artist_mbid,
            "artist_name": artist_name,
            "venue_name": coerce_location_str(venue.get("name")),
            "venue_city": coerce_location_str(venue.get("city")),
            "venue_region": coerce_location_str(venue.get("state")),
            "venue_country": coerce_location_str(venue.get("country") or "US"),
            "venue_lat": lat_f,
            "venue_lon": lon_f,
            "starts_at_utc": starts,
            "local_date": local_date,
        }

    async def test_connection(self) -> bool:
        return bool(self._client_id)
