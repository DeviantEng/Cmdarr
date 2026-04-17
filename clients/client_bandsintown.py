#!/usr/bin/env python3
"""Bandsintown public REST API (artist upcoming events)."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from urllib.parse import quote

from utils.cmdarr_user_agent import resolve_cmdarr_user_agent
from utils.event_geo import coerce_location_str

from .client_base import BaseAPIClient


class BandsintownClient(BaseAPIClient):
    def __init__(self, config, app_id: str):
        super().__init__(
            config=config,
            client_name="bandsintown",
            base_url="https://rest.bandsintown.com",
            rate_limit=2.0,
            headers={"User-Agent": resolve_cmdarr_user_agent(config)},
        )
        self._app_id = app_id

    async def fetch_upcoming_events(
        self, artist_name: str, artist_mbid: str
    ) -> list[dict[str, Any]] | None:
        """Return normalized events, [] on no-results, or None on provider error.

        Callers must treat None as "unknown" (do not advance scan TTL) and [] as "scanned OK,
        Bandsintown had no upcoming events for this artist".
        """
        if not artist_name or not self._app_id:
            return []
        path = f"/artists/{quote(artist_name, safe='')}/events"
        data = await self._get(
            path,
            params={"app_id": self._app_id, "date": "upcoming"},
        )
        if data is None:
            return None
        if not isinstance(data, list):
            return []
        out: list[dict[str, Any]] = []
        for ev in data:
            norm = self._normalize_event(ev, artist_mbid, artist_name)
            if norm:
                out.append(norm)
        return out

    def _normalize_event(
        self, ev: dict[str, Any], artist_mbid: str, artist_name: str
    ) -> dict[str, Any] | None:
        venue = ev.get("venue") or {}
        dt_raw = ev.get("datetime") or ev.get("starts_at")
        if not dt_raw:
            return None
        try:
            s = str(dt_raw).replace("Z", "+00:00")
            if "+" not in s and s.count("-") >= 3:
                s = s + "+00:00"
            starts = datetime.fromisoformat(s)
            if starts.tzinfo is None:
                starts = starts.replace(tzinfo=UTC)
            else:
                starts = starts.astimezone(UTC)
        except ValueError, TypeError:
            return None

        lat = venue.get("latitude")
        lon = venue.get("longitude")
        try:
            lat_f = float(lat) if lat is not None else None
            lon_f = float(lon) if lon is not None else None
        except TypeError, ValueError:
            lat_f, lon_f = None, None

        local_date = starts.date().isoformat()
        vname = coerce_location_str(venue.get("name")) or ""
        ext_id = str(ev.get("id") or ev.get("url") or f"{artist_mbid}-{local_date}-{vname}")

        return {
            "provider": "bandsintown",
            "external_id": ext_id[:256],
            "source_url": (ev.get("url") or "")[:1024] or None,
            "artist_mbid": artist_mbid,
            "artist_name": artist_name,
            "venue_name": coerce_location_str(venue.get("name")),
            "venue_city": coerce_location_str(venue.get("city")),
            "venue_region": coerce_location_str(venue.get("region")),
            "venue_country": coerce_location_str(venue.get("country")),
            "venue_lat": lat_f,
            "venue_lon": lon_f,
            "starts_at_utc": starts,
            "local_date": local_date,
        }

    async def test_connection(self) -> bool:
        return bool(self._app_id)
