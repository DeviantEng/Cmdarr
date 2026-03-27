"""
Shared track-matching helpers for Plex and Jellyfin.

Put logic here when both platforms should behave the same (fuzzy compare, collaboration
penalties, etc.). Keep platform-only concerns in the clients: API search strategies, field
names (e.g. grandparentTitle vs AlbumArtist), cache record shape, and auth/HTTP details.
"""

from __future__ import annotations

# Subtracted from total score when Plex/Jellyfin credits collaborators but the source does not.
COLLABORATION_MISMATCH_PENALTY_POINTS = 40

# Words stripped before character-set fuzzy compare (same list as legacy Plex client).
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
