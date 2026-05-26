#!/usr/bin/env python3
"""Shared helpers for playlist generator commands (Artist Essentials, Last.fm Similar, etc.)."""

from collections import defaultdict
from collections.abc import Iterable
from difflib import SequenceMatcher
from typing import Any

from utils.text_normalizer import normalize_text

SEP = " · "
MAX_ARTIST_LEN = 40
PLAYLIST_TITLE_TOP_TRACKS_PREFIX = "[Cmdarr] Artist Essentials"
PLAYLIST_TITLE_LFM_SIMILAR_PREFIX = "[Cmdarr] Last.fm Similar"
PLAYLIST_TITLE_SETLIST_PREFIX = "[Cmdarr] Setlist"


def build_auto_playlist_suffix(artist_names: list[str]) -> str:
    """Build suffix from artist names: 1-3 artists show all, 4+ show first 2 + N More."""
    names = [n.strip()[:MAX_ARTIST_LEN] for n in artist_names if (n or "").strip()]
    if not names:
        return "Mix"
    if len(names) <= 3:
        return SEP.join(names)
    return f"{names[0]}{SEP}{names[1]} + {len(names) - 2} More"


def validate_artists_against_cache(
    artists: list[str], cached_data: dict[str, Any] | None
) -> tuple[list[str], list[str]]:
    """Validate artists against library cache. Returns (valid normalized keys, invalid display names).
    Uses exact match first, then fuzzy match (ratio >= 0.88).
    """
    if not cached_data or "artist_index" not in cached_data:
        return [], [a.strip() for a in artists if a.strip()]

    artist_index = cached_data.get("artist_index", {})
    index_keys = list(artist_index.keys())
    valid = []
    invalid = []
    fuzzy_threshold = 0.88

    for a in artists:
        name = (a or "").strip()
        if not name:
            continue
        norm = normalize_text(name.lower())
        if norm in artist_index:
            valid.append(norm)
            continue
        first_char = norm[0] if norm else ""
        candidates = [k for k in index_keys if k and k[0] == first_char]
        if not candidates and index_keys:
            candidates = index_keys
        best_ratio = 0.0
        best_key = None
        for key in candidates:
            r = SequenceMatcher(None, norm, key).ratio()
            if r > best_ratio:
                best_ratio = r
                best_key = key
        if best_key and best_ratio >= fuzzy_threshold:
            valid.append(best_key)
        else:
            invalid.append(name)
    return valid, invalid


def index_lidarr_artist_mbids_by_norm(
    name_mbid_pairs: Iterable[tuple[str, str]],
) -> dict[str, list[str]]:
    """Map normalized artist name → sorted distinct MBIDs (Lidarr / MusicBrainz)."""
    by_norm: dict[str, set[str]] = defaultdict(set)
    for name, mbid in name_mbid_pairs:
        n = normalize_text(name or "")
        mb = (mbid or "").strip()
        if n and mb:
            by_norm[n].add(mb)
    return {k: sorted(v) for k, v in by_norm.items()}


def load_lidarr_artist_norm_mbid_index_sync() -> dict[str, list[str]]:
    """Load ``lidarr_artist`` rows into norm → MBIDs. Returns {} if DB/query fails."""

    try:
        from database.config_models import LidarrArtist
        from database.database import get_database_manager

        db = get_database_manager()
        session = db.get_config_session_sync()
        try:
            rows = session.query(LidarrArtist).all()
            pairs = [(r.artist_name or "", r.artist_mbid or "") for r in rows]
            return index_lidarr_artist_mbids_by_norm(pairs)
        finally:
            session.close()
    except Exception:
        return {}


def merge_similar_round_robin(
    per_seed_lists: list[list[dict[str, Any]]],
    max_artists: int,
) -> list[dict[str, Any]]:
    """Interleave similar rows from each seed (round-robin) until max_artists or exhausted.
    Each row should have at least 'name' and ideally 'match' (Last.fm similarity string).
    """
    if max_artists <= 0:
        return []
    out: list[dict[str, Any]] = []
    seen_norm: set[str] = set()
    indices = [0] * len(per_seed_lists)
    while len(out) < max_artists:
        progressed = False
        for i, lst in enumerate(per_seed_lists):
            if len(out) >= max_artists:
                break
            j = indices[i]
            while j < len(lst):
                row = lst[j]
                j += 1
                name = (row.get("name") or "").strip()
                if not name:
                    continue
                norm = normalize_text(name.lower())
                if norm in seen_norm:
                    continue
                seen_norm.add(norm)
                out.append(dict(row))
                progressed = True
                indices[i] = j
                break
            else:
                indices[i] = j
        if not progressed:
            break
    return out


def build_lfm_similar_artist_pool(
    seed_names: list[str],
    per_seed_similar: list[list[dict[str, Any]]],
    include_seeds: bool,
    max_artists: int,
) -> list[dict[str, Any]]:
    """Combine optional seed rows with round-robin similar artists; dedupe by normalized name; cap size."""
    seeds_used: list[dict[str, Any]] = []
    seen: set[str] = set()
    if include_seeds:
        for sn in seed_names:
            name = (sn or "").strip()
            if not name:
                continue
            norm = normalize_text(name.lower())
            if norm in seen:
                continue
            seen.add(norm)
            seeds_used.append({"name": name, "match": "1", "mbid": "", "url": ""})
            if len(seeds_used) >= max_artists:
                return seeds_used[:max_artists]
    remaining = max(0, max_artists - len(seeds_used))
    rr = merge_similar_round_robin(per_seed_similar, remaining)
    out = list(seeds_used)
    for row in rr:
        norm = normalize_text((row.get("name") or "").lower())
        if not norm or norm in seen:
            continue
        seen.add(norm)
        out.append(dict(row))
        if len(out) >= max_artists:
            break
    return out[:max_artists]


def compute_lfm_similar_playlist_title(config: dict[str, Any]) -> str:
    """Full playlist title from config (matches playlist_generator_lfm_similar naming rules)."""
    seeds_raw = config.get("seed_artists")
    if seeds_raw is None:
        seeds_raw = config.get("artists", [])
    if isinstance(seeds_raw, str):
        seeds_raw = [s.strip() for s in seeds_raw.split("\n") if s.strip()]
    seeds = [s for s in seeds_raw if (s or "").strip()]
    use_custom = config.get("use_custom_playlist_name", False)
    custom = (config.get("custom_playlist_name") or "").strip()
    if use_custom and custom:
        suffix = custom
    else:
        seed_display = [s.strip() for s in seeds if s.strip()]
        suffix = build_auto_playlist_suffix(seed_display) if seed_display else "Mix"
    return f"{PLAYLIST_TITLE_LFM_SIMILAR_PREFIX}: {suffix}"


def compute_setlistfm_playlist_title(config: dict[str, Any]) -> str:
    """Playlist title from config; uses ordered artist list for auto suffix."""
    artists_raw = config.get("artists", [])
    if isinstance(artists_raw, str):
        artists_raw = [a.strip() for a in artists_raw.split("\n") if a.strip()]
    names = [a.strip() for a in artists_raw if (a or "").strip()]
    use_custom = config.get("use_custom_playlist_name", False)
    custom = (config.get("custom_playlist_name") or "").strip()
    if use_custom and custom:
        suffix = custom
    else:
        suffix = build_auto_playlist_suffix(names[:50]) if names else "Mix"
    return f"{PLAYLIST_TITLE_SETLIST_PREFIX}: {suffix}"


def compute_top_tracks_playlist_title_from_config(config: dict[str, Any]) -> str:
    """Playlist title from stored config (all listed artists in auto suffix). Used on save/API."""
    artists_raw = config.get("artists", [])
    if isinstance(artists_raw, str):
        artists_raw = [a.strip() for a in artists_raw.split("\n") if a.strip()]
    names = [a.strip() for a in artists_raw if (a or "").strip()]
    use_custom = config.get("use_custom_playlist_name", False)
    custom = (config.get("custom_playlist_name") or "").strip()
    if use_custom and custom:
        suffix = custom
    else:
        suffix = build_auto_playlist_suffix(names[:50]) if names else "Mix"
    return f"{PLAYLIST_TITLE_TOP_TRACKS_PREFIX}: {suffix}"
