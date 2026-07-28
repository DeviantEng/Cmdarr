#!/usr/bin/env python3
"""Helpers for Lidarr maintenance commands (Update All, Wanted Search)."""

from __future__ import annotations

from typing import Any

# Canonical Cmdarr release-type set (matches NRD / UI checkboxes).
ALBUM_TYPES = frozenset({"album", "ep", "single", "other"})

SORT_OPTIONS = {
    "oldest_release_date": ("releaseDate", "ascending"),
    "newest_release_date": ("releaseDate", "descending"),
    "artist_name_asc": ("artist.sortName", "ascending"),
    "album_title_asc": ("title", "ascending"),
}

DEFAULT_SORT = "oldest_release_date"
DEFAULT_TOP_X = 10
DEFAULT_IGNORE_DAYS = 14
DEFAULT_SETTLE_SECONDS = 15


def normalize_album_types(raw: str | list[str] | None) -> set[str]:
    """Parse album_types config into a non-empty set of canonical types."""
    if raw is None:
        return {"album"}
    if isinstance(raw, list):
        parts = [str(x).strip().lower() for x in raw if str(x).strip()]
    else:
        parts = [p.strip().lower() for p in str(raw).split(",") if p.strip()]
    selected = {p for p in parts if p in ALBUM_TYPES}
    return selected or {"album"}


def map_lidarr_album_type(album_type: str | None) -> str:
    """
    Map Lidarr albumType string to Cmdarr album|ep|single|other.

    Lidarr uses title-case values like Album, EP, Single, Broadcast, Remix, etc.
    """
    t = (album_type or "").strip().lower()
    if t == "album":
        return "album"
    if t == "ep":
        return "ep"
    if t == "single":
        return "single"
    return "other"


def album_matches_types(album_type: str | None, selected: set[str]) -> bool:
    """True when Lidarr albumType maps into the selected Cmdarr type set."""
    return map_lidarr_album_type(album_type) in selected


def resolve_sort(sort_key: str | None) -> tuple[str, str]:
    """Return (lidarr_sortKey, lidarr_sortDirection) for a Cmdarr sort option."""
    key = (sort_key or DEFAULT_SORT).strip().lower()
    return SORT_OPTIONS.get(key, SORT_OPTIONS[DEFAULT_SORT])


def extract_album_ids_from_queue(queue_records: list[dict[str, Any]]) -> set[int]:
    """Collect Lidarr album IDs referenced by queue items."""
    ids: set[int] = set()
    for item in queue_records or []:
        aid = item.get("albumId")
        if aid is None and isinstance(item.get("album"), dict):
            aid = item["album"].get("id")
        if aid is not None:
            try:
                ids.add(int(aid))
            except TypeError, ValueError:
                pass
    return ids


def extract_album_ids_from_history(history_records: list[dict[str, Any]]) -> set[int]:
    """Collect Lidarr album IDs from history entries (e.g. grabbed)."""
    ids: set[int] = set()
    for item in history_records or []:
        aid = item.get("albumId")
        if aid is None and isinstance(item.get("album"), dict):
            aid = item["album"].get("id")
        if aid is not None:
            try:
                ids.add(int(aid))
            except TypeError, ValueError:
                pass
    return ids


def normalize_wanted_record(record: dict[str, Any]) -> dict[str, Any]:
    """Flatten a Wanted/Missing album record for ignore tracking and logging."""
    artist = record.get("artist") if isinstance(record.get("artist"), dict) else {}
    album_id = record.get("id")
    return {
        "lidarr_album_id": int(album_id) if album_id is not None else None,
        "foreign_album_id": record.get("foreignAlbumId"),
        "album_title": record.get("title") or "",
        "album_type": map_lidarr_album_type(record.get("albumType")),
        "lidarr_album_type": record.get("albumType"),
        "release_date": record.get("releaseDate"),
        "artist_name": artist.get("artistName") if artist else None,
        "artist_mbid": artist.get("foreignArtistId") if artist else None,
        "lidarr_artist_id": record.get("artistId"),
    }
