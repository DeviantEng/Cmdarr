"""Parse setlist.fm API JSON into ordered song lists (unit-testable)."""

from __future__ import annotations

from datetime import date
from statistics import median
from typing import Any

# Tracks above this count are preferred; stubs (covers only, etc.) are excluded until fallback.
STUB_TRACK_THRESHOLD = 3
# Collector stops paging after gathering this many "substantial" in-window setlists.
TARGET_SUBSTANTIAL_SETLISTS = 5
# Hard cap on setlist.fm API paginated fetches per artist.
MAX_ARTIST_SETLIST_PAGES = 20
# Only consider gigs within this many calendar days including today (rolling window).
SHOW_LOOKBACK_DAYS = 365


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


def _parse_setlist_event_date(event_date: str) -> tuple[int, int, int] | None:
    """Parse setlist.fm REST eventDate (typically dd-MM-yyyy). Returns (year, month, day) or None."""
    s = (event_date or "").strip()
    if not s:
        return None
    parts = s.split("-")
    if len(parts) != 3:
        return None
    try:
        day, month, year = (int(parts[0]), int(parts[1]), int(parts[2]))
    except ValueError:
        return None
    if not (1 <= month <= 12 and 1 <= day <= 31 and 1900 <= year <= 2100):
        return None
    return (year, month, day)


def setlist_rank_key(setlist_obj: dict[str, Any]) -> tuple[int, int, int, int]:
    """Sort key: higher is better — newest performance date, then more songs (same-day tiebreak)."""
    titles = extract_ordered_songs_from_setlist(setlist_obj)
    parsed = _parse_setlist_event_date(str(setlist_obj.get("eventDate") or ""))
    if parsed:
        y, m, d = parsed
    else:
        y, m, d = 0, 0, 0
    return (y, m, d, len(titles))


def setlists_from_api_page(page: dict[str, Any]) -> list[dict[str, Any]]:
    """Setlist.fm API body `setlist` field as a list of setlist documents."""
    return _setlist_entries(page)


def _stable_event_key(sl: dict[str, Any]) -> str:
    sid = str(sl.get("id") or "").strip()
    if sid:
        return f"id:{sid}"
    venue = sl.get("venue") or {}
    vname = ""
    if isinstance(venue, dict):
        vname = str(venue.get("name") or venue.get("id") or "").strip().lower()
    return f"noid:{sl.get('eventDate')}|{vname}"


def dedupe_by_event_key(setlists: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[str] = set()
    out: list[dict[str, Any]] = []
    for sl in setlists:
        k = _stable_event_key(sl)
        if k in seen:
            continue
        seen.add(k)
        out.append(sl)
    return out


def _event_date_calendar(sl: dict[str, Any]) -> date | None:
    parsed = _parse_setlist_event_date(str(sl.get("eventDate") or ""))
    if not parsed:
        return None
    y, m, d = parsed
    try:
        return date(y, m, d)
    except ValueError:
        return None


def event_within_lookback_days(
    sl: dict[str, Any], *, today: date, days: int = SHOW_LOOKBACK_DAYS
) -> bool:
    """Past-only: event must lie on ``today`` or within ``days`` days before."""
    ed = _event_date_calendar(sl)
    if ed is None:
        return False
    if ed > today:
        return False
    return (today - ed).days <= days


def track_count_nonempty(sl: dict[str, Any]) -> int:
    return len(extract_ordered_songs_from_setlist(sl))


def _ordinal_ymd(sl: dict[str, Any]) -> int:
    p = _parse_setlist_event_date(str(sl.get("eventDate") or ""))
    if not p:
        return 0
    y, m, d = p
    return y * 372 + m * 31 + d


def finalize_candidate_pool_after_scan(
    substantial: list[dict[str, Any]],
    stub: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Dedup, keep up to TARGET_SUBSTANTIAL_SETLISTS newest substantive shows; fallback to stubs."""
    sub = dedupe_by_event_key(substantial)
    sub.sort(key=_ordinal_ymd, reverse=True)
    pool = sub[:TARGET_SUBSTANTIAL_SETLISTS]
    if pool:
        return pool
    st = dedupe_by_event_key(stub)
    st.sort(key=_ordinal_ymd, reverse=True)
    return st[:TARGET_SUBSTANTIAL_SETLISTS]


def choose_repr_setlist_for_playlist(pool: list[dict[str, Any]]) -> dict[str, Any] | None:
    """Pick closest to median track count among pool, then longest; same distance prefers newer gig."""
    if not pool:
        return None
    counts = [track_count_nonempty(sl) for sl in pool]
    med = float(median(counts))

    def cmp_key(sl: dict[str, Any]) -> tuple[float, float, float]:
        c = track_count_nonempty(sl)
        return (abs(c - med), -float(c), -float(_ordinal_ymd(sl)))

    return min(pool, key=cmp_key)


def pick_best_setlist_for_block(setlists_page: dict[str, Any]) -> dict[str, Any] | None:
    """Choose the setlist with the newest eventDate; if tied, prefer the one with more parsed songs."""
    best: dict[str, Any] | None = None
    best_key: tuple[int, int, int, int] | None = None
    for sl in _setlist_entries(setlists_page):
        key = setlist_rank_key(sl)
        if key[3] == 0:
            continue
        if best_key is None or key > best_key:
            best_key = key
            best = sl
    return best


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
