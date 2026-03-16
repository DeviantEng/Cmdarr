#!/usr/bin/env python3
"""
Library selector utility - single source of truth for resolving which music library
to use for Plex and Jellyfin operations.

Used for: library cache, play history, track/artist search, sonic analysis.
Resolution: PLEX_LIBRARY_NAME/JELLYFIN_LIBRARY_NAME if set; else prefer "Music"; else first by lowest key.
"""

from typing import Any


def _first_by_lowest_key(libraries: list[dict[str, Any]]) -> dict[str, Any] | None:
    """Return library with lowest key (numeric when possible)."""
    if not libraries:
        return None

    def sort_key(lib):
        k = lib.get("key") or ""
        try:
            return (0, int(k))
        except (ValueError, TypeError):
            return (1, str(k))

    return min(libraries, key=sort_key)


def _resolve_from_libraries(
    music_libraries: list[dict[str, Any]],
    name_override: str | None,
    logger=None,
) -> dict[str, Any] | None:
    """
    Resolve which music library to use. Input is pre-filtered artist-type libraries.

    Order: 1) name_override if set; 2) single library; 3) prefer "Music"; 4) first by lowest key.
    """
    if not music_libraries:
        return None
    name_override = (name_override or "").strip()
    chosen = None
    if name_override:
        for lib in music_libraries:
            if (lib.get("title") or "").strip().lower() == name_override.lower():
                chosen = lib
                break
        if not chosen and logger:
            logger.warning(
                f"Library '{name_override}' not found in {[item.get('title') for item in music_libraries]}, using first"
            )
        if not chosen:
            chosen = _first_by_lowest_key(music_libraries)
    elif len(music_libraries) == 1:
        chosen = music_libraries[0]
    else:
        for lib in music_libraries:
            if (lib.get("title") or "").strip().lower() == "music":
                chosen = lib
                break
        if not chosen:
            chosen = _first_by_lowest_key(music_libraries)
    if chosen and logger:
        logger.debug(f"Resolved library: {chosen.get('title', '?')} (key={chosen.get('key', '?')})")
    return chosen


def resolve_plex_library(client) -> dict[str, Any] | None:
    """
    Resolve which Plex music library to use. Uses PLEX_LIBRARY_NAME if set.
    Returns dict with key, title, type or None.
    """
    music_libraries = client.get_music_libraries()
    name_override = (client.config.get("PLEX_LIBRARY_NAME") or "").strip() or None
    return _resolve_from_libraries(music_libraries, name_override, client.logger)


def resolve_jellyfin_library(client) -> dict[str, Any] | None:
    """
    Resolve which Jellyfin music library to use. Uses JELLYFIN_LIBRARY_NAME if set.
    Returns dict with key, title, type or None.
    """
    music_libraries = client.get_music_libraries()
    name_override = (client.config.get("JELLYFIN_LIBRARY_NAME") or "").strip() or None
    return _resolve_from_libraries(music_libraries, name_override, client.logger)
