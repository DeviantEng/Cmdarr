"""Parse setlist.fm API JSON into ordered song lists (unit-testable)."""

from __future__ import annotations

from typing import Any


def extract_ordered_songs_from_setlist(setlist_obj: dict[str, Any]) -> list[str]:
    """Return song titles in performance order; skip tape-only entries."""
    out: list[str] = []
    sets_block = setlist_obj.get("sets") or {}
    set_list = sets_block.get("set")
    if not set_list:
        return out
    if isinstance(set_list, dict):
        set_list = [set_list]
    for st in set_list:
        if not isinstance(st, dict):
            continue
        songs = st.get("song")
        if songs is None:
            continue
        if isinstance(songs, dict):
            songs = [songs]
        for s in songs:
            if not isinstance(s, dict):
                continue
            if s.get("tape") is True:
                continue
            name = (s.get("name") or "").strip()
            if name:
                out.append(name)
    return out


def _setlist_entries(page: dict[str, Any]) -> list[dict[str, Any]]:
    raw = page.get("setlist")
    if raw is None:
        return []
    if isinstance(raw, dict):
        return [raw]
    if isinstance(raw, list):
        return [x for x in raw if isinstance(x, dict)]
    return []


def first_non_empty_setlist(setlists_page: dict[str, Any]) -> dict[str, Any] | None:
    """Return the first setlist document that yields at least one song title."""
    for sl in _setlist_entries(setlists_page):
        if extract_ordered_songs_from_setlist(sl):
            return sl
    return None


def pick_setlist_for_block(
    setlists_page: dict[str, Any], *, prefer_non_empty: bool = True
) -> dict[str, Any] | None:
    """Choose a setlist row to derive a playlist block from."""
    entries = _setlist_entries(setlists_page)
    if not entries:
        return None
    if prefer_non_empty:
        hit = first_non_empty_setlist(setlists_page)
        if hit:
            return hit
    return entries[0]
