#!/usr/bin/env python3
"""setlist.fm REST API (API key required — register at https://api.setlist.fm/)."""

from __future__ import annotations

from typing import Any

from .client_base import BaseAPIClient


class SetlistFmClient(BaseAPIClient):
    def __init__(self, config):
        api_key = getattr(config, "SETLIST_FM_API_KEY", "") or ""
        headers = {
            "Accept": "application/json",
            "x-api-key": api_key,
        }
        rate = float(getattr(config, "SETLIST_FM_RATE_LIMIT", 1.0) or 1.0)
        super().__init__(
            config=config,
            client_name="setlistfm",
            base_url="https://api.setlist.fm/rest/1.0",
            rate_limit=rate,
            headers=headers,
        )

    async def test_connection(self) -> bool:
        """Lightweight check — search for a well-known artist."""
        data = await self.search_artists("Muse", page=1)
        return bool(data)

    async def search_artists(self, artist_name: str, page: int = 1) -> dict[str, Any] | None:
        return await self._get(
            "search/artists",
            {"artistName": artist_name.strip(), "p": str(page)},
        )

    async def get_artist_setlists(self, mbid: str, page: int = 1) -> dict[str, Any] | None:
        mbid = (mbid or "").strip()
        if not mbid:
            return None
        # Pagination past last page returns 404 "page does not exist"; avoid ERROR spam in shared HTTP util.
        return await self._get(
            f"artist/{mbid}/setlists",
            {"p": str(page)},
            suppress_error_log_statuses=frozenset({404}),
        )
