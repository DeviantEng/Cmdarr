#!/usr/bin/env python3
"""
xmplaylist.com public API client (SiriusXM track history).
https://xmplaylist.com/docs — set a User-Agent (uses CMDARR_USER_AGENT / same default as MusicBrainz).

Requests use curl_cffi with Chrome TLS impersonation when available (see XMPLAYLIST_USE_CURL_CFFI).
Note: TLS fingerprint may not match a literal Cmdarr User-Agent; operators may whitelist by UA header.
"""

from __future__ import annotations

from typing import Any

import aiohttp

from utils.cmdarr_user_agent import resolve_cmdarr_user_agent

from .client_base import BaseAPIClient

# Default Chrome impersonation profile for curl_cffi (must match BrowserType in curl_cffi)
_DEFAULT_XMPLAYLIST_IMPERSONATE = "chrome131"


def _xmplaylist_headers(config: Any) -> dict[str, str]:
    """Headers for xmplaylist JSON API (honest Cmdarr User-Agent; no fake browser Sec-Ch-Ua)."""
    return {
        "User-Agent": resolve_cmdarr_user_agent(config),
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "en-US,en;q=0.9",
        "Referer": "https://xmplaylist.com/",
        "Origin": "https://xmplaylist.com",
    }


MOST_HEARD_DAYS = frozenset({1, 7, 14, 30, 60})


def _join_artists(artists: Any) -> str:
    """Normalize artists array or string to a single search string."""
    if artists is None:
        return ""
    if isinstance(artists, str):
        return artists.strip()
    if isinstance(artists, list):
        names = []
        for a in artists:
            if isinstance(a, str):
                s = a.strip()
            elif isinstance(a, dict):
                s = (a.get("name") or a.get("title") or "").strip()
            else:
                s = str(a).strip()
            if s:
                names.append(s)
        return ", ".join(names) if names else ""
    return str(artists).strip()


def _normalize_track_row(raw: dict[str, Any]) -> dict[str, str] | None:
    """
    Map one API result row to {track, artist, album}. Ignores storefront / spotify / deezer blocks.
    Accepts several plausible payload shapes.
    """
    if not isinstance(raw, dict):
        return None

    node = raw.get("track") if isinstance(raw.get("track"), dict) else raw

    title = (
        node.get("title")
        or node.get("name")
        or node.get("track")
        or raw.get("title")
        or raw.get("name")
        or ""
    )
    title = str(title).strip()
    if not title:
        return None

    artist = _join_artists(
        node.get("artists") or node.get("artist") or raw.get("artists") or raw.get("artist")
    )

    album = ""
    alb = node.get("album") or raw.get("album")
    if isinstance(alb, dict):
        album = (alb.get("title") or alb.get("name") or "").strip()
    elif isinstance(alb, str):
        album = alb.strip()

    if not artist:
        return None

    return {"track": title, "artist": artist, "album": album or ""}


class XmplaylistClient(BaseAPIClient):
    """Client for xmplaylist.com JSON API."""

    def __init__(self, config):
        super().__init__(
            config=config,
            client_name="xmplaylist",
            base_url="https://xmplaylist.com",
            rate_limit=float(getattr(config, "XMPLAYLIST_RATE_LIMIT", None) or 1.0),
            headers=_xmplaylist_headers(config),
        )
        self._curl_session = None

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self._curl_session is not None:
            await self._curl_session.close()
            self._curl_session = None
        await super().__aexit__(exc_type, exc_val, exc_tb)

    async def _make_request_curl_cffi(
        self, full_url: str, method: str, json_body: Any | None
    ) -> dict[str, Any] | list[Any] | None:
        """HTTP via curl_cffi (Chrome JA3 / HTTP2) — required for many Cloudflare-protected hosts."""
        from curl_cffi.requests import AsyncSession

        if self._curl_session is None:
            self._curl_session = AsyncSession()

        impersonate = getattr(
            self.config, "XMPLAYLIST_CURL_IMPERSONATE", _DEFAULT_XMPLAYLIST_IMPERSONATE
        )
        if not isinstance(impersonate, str) or not impersonate.strip():
            impersonate = _DEFAULT_XMPLAYLIST_IMPERSONATE

        hdrs = dict(self.headers)

        meth = (method or "GET").upper()
        try:
            if meth == "GET":
                r = await self._curl_session.get(
                    full_url, headers=hdrs, impersonate=impersonate, timeout=30
                )
            elif meth == "POST":
                r = await self._curl_session.post(
                    full_url,
                    headers=hdrs,
                    json=json_body,
                    impersonate=impersonate,
                    timeout=30,
                )
            else:
                self.logger.error("xmplaylist: unsupported HTTP method %s", meth)
                return None
        except Exception as e:
            self.logger.error("xmplaylist curl_cffi request failed: %s", e)
            return None

        if r.status_code not in (200, 201, 204):
            body = r.text or ""
            preview = (body[:500] + "…") if len(body) > 500 else body
            self.logger.error("HTTP error %s: %s", r.status_code, preview or "(empty body)")
            return None

        if r.status_code == 204:
            return {}

        try:
            data = r.json()
        except Exception as e:
            self.logger.error("Invalid JSON from xmplaylist (%s): %s", r.status_code, e)
            return None

        if isinstance(data, (dict, list)):
            return data
        self.logger.error("Unexpected JSON type from xmplaylist: %s", type(data).__name__)
        return None

    async def _make_request(
        self, endpoint: str, params: dict[str, str] | None = None, method: str = "GET", **kwargs
    ) -> dict[str, Any] | list[Any] | None:
        """
        Prefer curl_cffi (Chrome TLS impersonation) when enabled; fall back to aiohttp only if
        curl_cffi is missing or XMPLAYLIST_USE_CURL_CFFI is false.
        """
        from urllib.parse import urlencode

        from utils.http_client import HTTPClientUtils

        if params is None:
            params = {}

        if endpoint.startswith("http"):
            url = endpoint
        else:
            url = HTTPClientUtils.build_api_url(self.base_url, endpoint)

        if params:
            sep = "&" if "?" in url else "?"
            url = f"{url}{sep}{urlencode(params)}"

        await self._rate_limiter.acquire()

        use_curl = getattr(self.config, "XMPLAYLIST_USE_CURL_CFFI", True)
        if use_curl:
            try:
                return await self._make_request_curl_cffi(url, method, kwargs.get("json"))
            except ImportError:
                self.logger.warning(
                    "curl_cffi is not installed; xmplaylist may be blocked by Cloudflare. "
                    "Install dependencies (pip install -r requirements.txt) including curl-cffi."
                )

        if not self.session:
            self.session = aiohttp.ClientSession(headers=self.headers)

        aio_url = (
            endpoint
            if endpoint.startswith("http")
            else HTTPClientUtils.build_api_url(self.base_url, endpoint)
        )
        return await HTTPClientUtils.make_async_request(
            session=self.session,
            url=aio_url,
            method=method,
            params=params,
            headers=self.headers,
            timeout=30,
            logger=self.logger,
            json=kwargs.get("json"),
        )

    def _build_url(self, path_or_url: str) -> str:
        from utils.http_client import HTTPClientUtils

        if path_or_url.startswith("http"):
            return path_or_url
        return HTTPClientUtils.build_api_url(self.base_url, path_or_url)

    def _extract_list_and_next(self, data: dict[str, Any] | list | None) -> tuple[list, str | None]:
        """Support {results:[]}, {data:[]}, or bare list; return (items, next_url_or_none)."""
        if data is None:
            return [], None
        if isinstance(data, list):
            return data, None
        if not isinstance(data, dict):
            return [], None

        items = (
            data.get("results") or data.get("data") or data.get("items") or data.get("tracks") or []
        )
        if not isinstance(items, list):
            items = []

        nxt = data.get("next")
        if isinstance(nxt, str) and nxt.strip():
            return items, nxt.strip()
        return items, None

    def _normalize_page(
        self, data: dict[str, Any] | list | None
    ) -> tuple[list[dict[str, str]], str | None]:
        items, nxt = self._extract_list_and_next(data)
        out: list[dict[str, str]] = []
        for row in items:
            norm = _normalize_track_row(row if isinstance(row, dict) else {})
            if norm:
                out.append(norm)
        resolved_next = None
        if nxt:
            resolved_next = nxt if nxt.startswith("http") else self._build_url(nxt)
        return out, resolved_next

    async def list_stations(self) -> list[dict[str, Any]]:
        """Fetch all stations (paginate via `next` when present)."""
        all_rows: list[dict[str, Any]] = []
        next_ref: str | None = "/api/station"
        visited: set[str] = set()

        for _ in range(100):
            if not next_ref or next_ref in visited:
                break
            visited.add(next_ref)
            data = await self._make_request(next_ref)
            if not data:
                break
            items, nxt = self._extract_list_and_next(data)
            for row in items:
                if isinstance(row, dict):
                    all_rows.append(row)
            if nxt:
                next_ref = nxt if nxt.startswith("http") else self._build_url(nxt)
            else:
                next_ref = None

        return all_rows

    async def fetch_tracks_newest(
        self, channel: str, max_tracks: int, max_pages: int = 20
    ) -> list[dict[str, str]]:
        """Newest-first; follow `next` until max_tracks or no next."""
        ch = (channel or "").strip().lower().replace(" ", "")
        if not ch:
            return []

        collected: list[dict[str, str]] = []
        next_ref: str | None = f"/api/station/{ch}/newest"
        visited: set[str] = set()

        for _ in range(max_pages):
            if not next_ref or next_ref in visited or len(collected) >= max_tracks:
                break
            visited.add(next_ref)
            data = await self._make_request(next_ref)
            if not data:
                break
            page_tracks, nxt_abs = self._normalize_page(data)
            for t in page_tracks:
                if len(collected) >= max_tracks:
                    break
                collected.append(t)
            if len(collected) >= max_tracks:
                break
            if nxt_abs:
                next_ref = nxt_abs
            else:
                break

        return collected[:max_tracks]

    async def fetch_tracks_most_heard(
        self, channel: str, days: int, max_tracks: int, max_pages: int = 20
    ) -> list[dict[str, str]]:
        if days not in MOST_HEARD_DAYS:
            raise ValueError(f"most_heard days must be one of {sorted(MOST_HEARD_DAYS)}")
        ch = (channel or "").strip().lower().replace(" ", "")
        if not ch:
            return []

        collected: list[dict[str, str]] = []
        next_ref: str | None = f"/api/station/{ch}/most-heard"
        visited: set[str] = set()
        params: dict[str, str] | None = {"days": str(days)}

        for _ in range(max_pages):
            if not next_ref or next_ref in visited or len(collected) >= max_tracks:
                break
            visited.add(next_ref)
            data = await self._make_request(next_ref, params=params)
            params = None
            if not data:
                break
            page_tracks, nxt_abs = self._normalize_page(data)
            for t in page_tracks:
                if len(collected) >= max_tracks:
                    break
                collected.append(t)
            if len(collected) >= max_tracks:
                break
            if nxt_abs:
                next_ref = nxt_abs
            else:
                break

        return collected[:max_tracks]
