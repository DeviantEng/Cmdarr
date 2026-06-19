"""Helpers for comparing Spotify/Deezer release_date strings (YYYY, YYYY-MM, YYYY-MM-DD)."""

from __future__ import annotations

from datetime import date, timedelta

RELEASE_WITHIN_CHOICES = frozenset({"all", "30d", "60d", "90d", "180d", "this_year"})


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


def release_within_cutoff(within: str) -> date | None:
    """Earliest release date (inclusive) for a within filter."""
    today = date.today()
    if within == "this_year":
        return date(today.year, 1, 1)
    days_map = {"30d": 30, "60d": 60, "90d": 90, "180d": 180}
    days = days_map.get(within)
    if days is None:
        return None
    return today - timedelta(days=days)


def release_date_within(value: str | None, within: str) -> bool:
    if not within or within == "all":
        return True
    parsed = parse_release_date(value)
    if parsed is None:
        return False
    cutoff = release_within_cutoff(within)
    if cutoff is None:
        return True
    return parsed >= cutoff
