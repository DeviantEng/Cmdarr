"""Plex top-listened artist ranking for Last.fm Discovery Phase 2 seeds."""

from __future__ import annotations

from collections import Counter
from datetime import datetime, timedelta
from typing import Any

from utils.timezone import get_scheduler_timezone


def _parse_viewed_at(item: dict[str, Any], tz) -> datetime | None:
    raw = item.get("viewedAt")
    if raw is None:
        return None
    try:
        ts = int(raw)
        return datetime.fromtimestamp(ts, tz=tz)
    except TypeError, ValueError, OSError, OverflowError:
        return None


def rank_plex_top_artists(
    history_items: list[dict[str, Any]],
    *,
    lookback_days: int,
    limit: int,
    now: datetime | None = None,
) -> list[tuple[str, int]]:
    """Return [(artist_name, play_count), ...] ranked by plays in the lookback window.

    Mirrors Local Discovery aggregation on grandparentTitle (no random sample).
    """
    tz = get_scheduler_timezone()
    if now is None:
        now = datetime.now(tz)
    elif now.tzinfo is None:
        now = now.replace(tzinfo=tz)
    else:
        now = now.astimezone(tz)

    lookback_days = max(7, min(365, int(lookback_days)))
    limit = max(1, min(50, int(limit)))
    history_start = now - timedelta(days=lookback_days)

    artist_plays: Counter[str] = Counter()
    for h in history_items:
        if str(h.get("type", "")) != "track":
            continue
        viewed = _parse_viewed_at(h, tz)
        if not viewed or viewed < history_start:
            continue
        artist = (h.get("grandparentTitle") or "").strip()
        if not artist:
            continue
        artist_plays[artist] += 1

    return list(artist_plays.most_common(limit))
