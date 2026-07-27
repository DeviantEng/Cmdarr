"""Helpers for Similarr artist artwork (Last.fm + Deezer)."""

from __future__ import annotations

from typing import Any

# Last.fm retired real artist images; this hash is the shared placeholder.
_LASTFM_PLACEHOLDER_MARKER = "2a96cbd8b46e442fc41c2b86b821562f"
_SIZE_ORDER = ("mega", "extralarge", "large", "medium", "small", "")


def pick_lastfm_image_url(image_list: Any) -> str | None:
    """Best non-placeholder Last.fm image URL from an image array, or None."""
    if not isinstance(image_list, list):
        return None
    by_size: dict[str, str] = {}
    for entry in image_list:
        if not isinstance(entry, dict):
            continue
        url = (entry.get("#text") or entry.get("text") or "").strip()
        if not url:
            continue
        size = (entry.get("size") or "").strip().lower()
        by_size[size] = url
    for size in _SIZE_ORDER:
        url = by_size.get(size)
        if url and _LASTFM_PLACEHOLDER_MARKER not in url:
            return url
    return None


def pick_deezer_image_url(artist: dict[str, Any] | None) -> str | None:
    """Best Deezer artist picture URL."""
    if not artist:
        return None
    for key in ("picture_xl", "picture_big", "picture_medium", "picture_small", "picture"):
        url = (artist.get(key) or "").strip()
        if url:
            return url
    return None
