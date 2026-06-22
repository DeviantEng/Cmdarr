"""Helpers for comparing Spotify/Deezer release_date strings (YYYY, YYYY-MM, YYYY-MM-DD)."""

from __future__ import annotations

from datetime import date, timedelta

RELEASE_WITHIN_CHOICES = frozenset({"all", "30d", "90d", "180d", "this_year", "previous_year"})


def parse_release_date(value: str | None) -> date | None:
    if not value:
        return None
    text = value.strip()
    if not text:
        return None
    try:
        if len(text) >= 10:
            return date.fromisoformat(text[:10])
        if len(text) >= 7:
            year, month = text[:7].split("-", 1)
            return date(int(year), int(month), 1)
        if len(text) >= 4 and text[:4].isdigit():
            return date(int(text[:4]), 1, 1)
    except ValueError, TypeError:
        return None
    return None


def release_within_bounds(within: str) -> tuple[date | None, date | None]:
    """Inclusive (start, end) for a within filter. None end means no upper bound."""
    today = date.today()
    if within == "this_year":
        return date(today.year, 1, 1), None
    if within == "previous_year":
        year = today.year - 1
        return date(year, 1, 1), date(year, 12, 31)
    days_map = {"30d": 30, "90d": 90, "180d": 180}
    days = days_map.get(within)
    if days is None:
        return None, None
    return today - timedelta(days=days), None


def release_within_cutoff(within: str) -> date | None:
    """Earliest release date (inclusive) for a within filter."""
    start, _ = release_within_bounds(within)
    return start


def release_date_within(value: str | None, within: str) -> bool:
    if not within or within == "all":
        return True
    parsed = parse_release_date(value)
    if parsed is None:
        return False
    start, end = release_within_bounds(within)
    if start is None and end is None:
        return True
    if start is not None and parsed < start:
        return False
    if end is not None and parsed > end:
        return False
    return True
