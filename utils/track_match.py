"""
Shared track-matching helpers for Plex and Jellyfin.

Put logic here when both platforms should behave the same (fuzzy compare, collaboration
penalties, etc.). Keep platform-only concerns in the clients: API search strategies, field
names (e.g. grandparentTitle vs AlbumArtist), cache record shape, and auth/HTTP details.
"""

from __future__ import annotations

import re
from typing import Any

# Subtracted from total score when Plex/Jellyfin credits collaborators but the source does not.
# Large enough that album bonuses (+50) cannot flip the winner vs the primary-artist line.
COLLABORATION_MISMATCH_PENALTY_POINTS = 60

# Words stripped before character-set fuzzy compare (same list as the Plex client).
_FUZZY_COMMON_WORDS = frozenset(
    {
        "the",
        "a",
        "an",
        "and",
        "or",
        "but",
        "in",
        "on",
        "at",
        "to",
        "for",
        "of",
        "with",
        "by",
        "from",
        "up",
        "about",
        "into",
        "over",
        "after",
    }
)


def collaboration_mismatch_penalty(target_artist_raw: str, library_artist_raw: str) -> int:
    """
    When the source names a single headliner but the library credits collaborators, prefer the
    primary-artist line (e.g. BMTH over "BMTH & Draper" for the same song title).

    Uses raw display strings so '&' is still visible (normalize_text strips '&').
    """
    t = (target_artist_raw or "").lower()
    p = (library_artist_raw or "").lower()
    if not p or not t:
        return 0
    markers = (" & ", " feat.", " feat ", " ft.", " ft ", " featuring ")
    if any(m in t for m in markers):
        return 0
    if any(m in p for m in markers):
        return COLLABORATION_MISMATCH_PENALTY_POINTS
    return 0


def primary_artist_segment_raw(library_artist_raw: str) -> str:
    """Headline segment before the first collaboration marker (raw display string)."""
    raw = (library_artist_raw or "").strip()
    if not raw:
        return ""
    lower = raw.lower()
    best_idx: int | None = None
    # Longer markers first so " featuring " wins over " feat." inside the same string
    for sep in (" featuring ", " feat.", " feat ", " ft.", " ft ", " & "):
        idx = lower.find(sep)
        if idx != -1 and (best_idx is None or idx < best_idx):
            best_idx = idx
    if best_idx is not None:
        return raw[:best_idx].strip()
    return raw


def normalized_primary_artist_for_collab_match(library_artist_raw: str) -> str | None:
    """
    If library_artist_raw contains collaborators, return normalize_text(primary segment), else None.
    Used so we score the source against 'Bring Me The Horizon' only, not '... & Draper'.
    """
    from utils.text_normalizer import normalize_text

    primary = primary_artist_segment_raw(library_artist_raw)
    full_stripped = (library_artist_raw or "").strip()
    if not primary or primary.lower() == full_stripped.lower():
        return None
    return normalize_text(primary.lower())


_MBID_UUID_RE = re.compile(
    r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}",
    re.IGNORECASE,
)

# Unicode fold map mirrored from utils.text_normalizer (artist identity only).
_UNICODE_TO_ASCII = {
    "ö": "o",
    "ü": "u",
    "ä": "a",
    "ß": "ss",
    "ø": "o",
    "œ": "oe",
    "æ": "ae",
    "ñ": "n",
    "é": "e",
    "è": "e",
    "ê": "e",
    "ë": "e",
    "á": "a",
    "à": "a",
    "â": "a",
    "ã": "a",
    "å": "a",
    "í": "i",
    "ì": "i",
    "î": "i",
    "ï": "i",
    "ó": "o",
    "ò": "o",
    "ô": "o",
    "õ": "o",
    "ú": "u",
    "ù": "u",
    "û": "u",
    "ý": "y",
    "ÿ": "y",
    "ç": "c",
    "ð": "d",
    "þ": "th",
}

_PUNCT_STRIP_RE = re.compile(r"[^\w\s\'-]")


def _fold_unicode_lower(text: str) -> str:
    text = text.lower().strip()
    for uchar, ascii_char in _UNICODE_TO_ASCII.items():
        text = text.replace(uchar, ascii_char)
    return text


def extract_mbid_from_guid(guid: str | None) -> str | None:
    """Extract the first UUID MusicBrainz id embedded in a Plex/Jellyfin guid string."""
    if not guid:
        return None
    match = _MBID_UUID_RE.search(guid)
    return match.group(0).lower() if match else None


def artist_identity_matches(source: str, library: str) -> bool:
    """
    True when two artist display names refer to the same identity for matching.

    After normalize_text() equality, rejects punctuation-only collisions (e.g. ``Gore.`` vs
    ``gore``) while still allowing unicode-fold differences (e.g. ``Motörhead`` vs ``Motorhead``).
    """
    from utils.text_normalizer import normalize_text

    source = (source or "").strip()
    library = (library or "").strip()
    if not source or not library:
        return False
    if normalize_text(source) != normalize_text(library):
        return False
    if source.lower().strip() == library.lower().strip():
        return True

    s_fold = _fold_unicode_lower(source)
    l_fold = _fold_unicode_lower(library)
    if s_fold == l_fold:
        return True

    s_nopunct = _PUNCT_STRIP_RE.sub("", s_fold)
    l_nopunct = _PUNCT_STRIP_RE.sub("", l_fold)
    if s_nopunct == l_nopunct:
        if _PUNCT_STRIP_RE.sub("", s_fold) != s_fold or _PUNCT_STRIP_RE.sub("", l_fold) != l_fold:
            return False
        return True
    return True


def lastfm_exact_name_candidates(display_name: str, library_artist: str) -> list[str]:
    """Distinct Last.fm artist names preserving punctuation."""
    seen_lower: set[str] = set()
    names: list[str] = []
    for raw in (display_name, library_artist):
        name = (raw or "").strip()
        key = name.lower()
        if name and key not in seen_lower:
            seen_lower.add(key)
            names.append(name)
    return names


def lastfm_query_plan(
    display_name: str,
    library_artist: str,
    norm: str,
    mbids: list[str],
) -> list[tuple[str, str | None, str]]:
    """Last.fm lookup order: MBID, exact names, normalized name (last resort)."""
    from utils.text_normalizer import normalize_text

    plan: list[tuple[str, str | None, str]] = []
    mbid = mbids[0] if len(mbids) == 1 else None
    exact = lastfm_exact_name_candidates(display_name, library_artist)

    if mbid:
        plan.append((display_name or (exact[0] if exact else ""), mbid, "mbid"))

    for name in exact:
        plan.append((name, None, "exact"))

    norm_key = (norm or "").strip()
    if norm_key:
        exact_norms = {normalize_text(n) for n in exact}
        if norm_key not in exact_norms:
            plan.append((norm_key, None, "normalized"))

    return plan


def plex_search_variants(match_context: dict[str, Any]) -> list[tuple[str, list[str] | None, str]]:
    """Plex track search order: MBID + exact names, exact names, normalized (last)."""
    from utils.text_normalizer import normalize_text

    display = (match_context.get("display_name") or "").strip()
    library = (match_context.get("library_artist") or "").strip()
    norm = (match_context.get("norm") or "").strip()
    mbids_raw = match_context.get("mbids") or []
    mbid_list = [m for m in mbids_raw if (m or "").strip()] or None

    exact = lastfm_exact_name_candidates(display, library)
    variants: list[tuple[str, list[str] | None, str]] = []
    seen: set[tuple[str, str | None]] = set()

    def add(name: str, mbids: list[str] | None, label: str) -> None:
        name = (name or "").strip()
        if not name:
            return
        mb_key = tuple(mbids) if mbids else None
        key = (name.lower(), mb_key)
        if key in seen:
            return
        seen.add(key)
        variants.append((name, mbids, label))

    if mbid_list:
        for name in exact:
            add(name, mbid_list, "mbid_exact")

    for name in exact:
        add(name, None, "exact")

    if norm:
        exact_norms = {normalize_text(n) for n in exact}
        if norm not in exact_norms:
            add(norm, None, "normalized")

    return variants


def lastfm_tracks_match_artist(
    tracks: list[dict[str, Any]], display_name: str, library_artist: str
) -> bool:
    """True if any Last.fm row artist string matches the expected identity."""
    for track in tracks:
        lfm_artist = (track.get("artist") or "").strip()
        if artist_identity_matches(display_name, lfm_artist):
            return True
        if library_artist and artist_identity_matches(library_artist, lfm_artist):
            return True
    return False


def normalized_artist_for_source_vs_library(
    target_artist_raw: str,
    library_artist_raw: str,
    library_artist_normalized_full: str,
) -> str:
    """
    When the source names a single headliner but the library credits collaborators, compare
    against the library primary line only (avoids substring partial matches on the full string).
    """
    if collaboration_mismatch_penalty(target_artist_raw, library_artist_raw) <= 0:
        return library_artist_normalized_full
    primary = normalized_primary_artist_for_collab_match(library_artist_raw)
    return primary if primary is not None else library_artist_normalized_full


def fuzzy_char_overlap_match(str1: str, str2: str, threshold: float = 0.8) -> bool:
    """
    Character-set Jaccard similarity after dropping common words — same algorithm as Plex
    _fuzzy_match (used for title/artist fuzzy legs in both clients).
    """
    if not str1 or not str2:
        return False

    def clean_string(s: str) -> str:
        words = s.split()
        return " ".join(w for w in words if w not in _FUZZY_COMMON_WORDS)

    clean_str1 = clean_string(str1)
    clean_str2 = clean_string(str2)

    set1 = set(clean_str1.replace(" ", ""))
    set2 = set(clean_str2.replace(" ", ""))

    if not set1 or not set2:
        return False

    overlap = len(set1.intersection(set2))
    total = len(set1.union(set2))

    return (overlap / total) >= threshold
