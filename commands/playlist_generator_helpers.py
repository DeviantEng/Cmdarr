#!/usr/bin/env python3
"""Shared helpers for playlist generator commands (Artist Essentials, Last.fm Similar, etc.)."""

from difflib import SequenceMatcher
from typing import Any

from utils.text_normalizer import normalize_text

SEP = " · "
MAX_ARTIST_LEN = 40


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
