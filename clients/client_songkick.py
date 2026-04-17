#!/usr/bin/env python3
"""Songkick API 3.0 — search artist then calendar."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from utils.event_geo import coerce_location_str

from .client_base import BaseAPIClient


class SongkickClient(BaseAPIClient):
    def __init__(self, config, api_key: str):
        super().__init__(
            config=config,
            client_name="songkick",
            base_url="https://api.songkick.com/api/3.0",
            rate_limit=1.0,
        )
        self._api_key = api_key

    async def fetch_upcoming_events(
        self, artist_name: str, artist_mbid: str
    ) -> list[dict[str, Any]] | None:
        """Return normalized events, [] on no-results, or None on provider error.

        Callers must treat None as "unknown" (do not advance scan TTL) and [] as "scanned OK,
        Songkick had no upcoming events for this artist".
        """
        if not artist_name or not self._api_key:
            return []
        search = await self._get(
            "/search/artists.json",
            params={"query": artist_name, "apikey": self._api_key},
        )
        if search is None:
            return None
        if not isinstance(search, dict):
            return []
        results = (search.get("resultsPage") or {}).get("results")
        if not isinstance(results, dict):
            return []
        artist_list = results.get("artist") or []
        if isinstance(artist_list, dict):
            artist_list = [artist_list]
        if not artist_list:
            return []
        sk_id = artist_list[0].get("id")
        if not sk_id:
            return []
        cal = await self._get(
            f"/artists/{sk_id}/calendar.json",
            params={"apikey": self._api_key},
        )
        if cal is None:
            return None
        if not isinstance(cal, dict):
            return []
        res = (cal.get("resultsPage") or {}).get("results")
        if not isinstance(res, dict):
            return []
        evs = res.get("event") or []
        if isinstance(evs, dict):
            evs = [evs]
        out: list[dict[str, Any]] = []
        for ev in evs:
            norm = self._normalize_event(ev, artist_mbid, artist_name)
            if norm:
                out.append(norm)
        return out

    def _normalize_event(
        self, ev: dict[str, Any], artist_mbid: str, artist_name: str
    ) -> dict[str, Any] | None:
        if ev.get("status") == "cancelled":
            return None
        start = ev.get("start") or {}
        dt_raw = start.get("datetime") or start.get("date")
        if not dt_raw:
            return None
        try:
            if "T" in str(dt_raw):
                s = str(dt_raw).replace("Z", "+00:00")
                if "+" not in s and "Z" not in str(dt_raw):
                    s = s + "+00:00"
                starts = datetime.fromisoformat(s.replace("Z", "+00:00"))
            else:
                starts = datetime.strptime(str(dt_raw)[:10], "%Y-%m-%d").replace(tzinfo=UTC)
            if starts.tzinfo is None:
                starts = starts.replace(tzinfo=UTC)
            else:
                starts = starts.astimezone(UTC)
        except ValueError, TypeError:
            return None

        venue = ev.get("venue") or {}
        city = venue.get("city") or {}
        lat = venue.get("lat")
        lon = venue.get("lng")
        try:
            lat_f = float(lat) if lat is not None else None
            lon_f = float(lon) if lon is not None else None
        except TypeError, ValueError:
            lat_f, lon_f = None, None

        local_date = starts.date().isoformat()
        ext_id = str(ev.get("id") or "")

        ma = venue.get("metroArea") if isinstance(venue.get("metroArea"), dict) else {}
        return {
            "provider": "songkick",
            "external_id": ext_id[:256] if ext_id else f"sk-{artist_mbid}-{local_date}",
            "source_url": (ev.get("uri") or ev.get("url") or "")[:1024] or None,
            "artist_mbid": artist_mbid,
            "artist_name": artist_name,
            "venue_name": coerce_location_str(venue.get("displayName")),
            "venue_city": coerce_location_str(
                city.get("displayName") if isinstance(city, dict) else city
            ),
            "venue_region": coerce_location_str(ma.get("state")),
            "venue_country": coerce_location_str(ma.get("country")),
            "venue_lat": lat_f,
            "venue_lon": lon_f,
            "starts_at_utc": starts,
            "local_date": local_date,
        }

    async def test_connection(self) -> bool:
        return bool(self._api_key)
