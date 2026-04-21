"""Ticketmaster Discovery event helpers: public URL selection and festival/tour classification."""

from __future__ import annotations

import re
from typing import Any
from urllib.parse import urlparse

_TOKEN_RE = re.compile(r"[a-z0-9']+", re.I)


def _tokens(text: str) -> list[str]:
    return _TOKEN_RE.findall((text or "").lower())


def _artist_slug_score(path_lower: str, artist_name: str) -> float:
    tokens = _tokens(artist_name)
    if not tokens:
        return 0.0
    full = "-".join(tokens)
    if full and full in path_lower:
        return 400.0
    if tokens[0] == "the" and len(tokens) > 1:
        rest = "-".join(tokens[1:])
        if rest and rest in path_lower:
            return 380.0
    for t in tokens:
        if len(t) >= 4 and t in path_lower:
            return 120.0
    return 0.0


def _domain_score(hostname: str) -> float:
    h = hostname.lower()
    if h.endswith("ticketmaster.com"):
        return 100.0
    if h.endswith("livenation.com"):
        return 88.0
    if h.endswith("ticketweb.com"):
        return 72.0
    if h.endswith("axs.com"):
        return 65.0
    if h.endswith("etix.com"):
        return 58.0
    if h.endswith("universe.com"):
        return 52.0
    if "fgtix.com" in h:
        return 6.0
    if h.endswith("gracelandlive.com"):
        return 44.0
    return 36.0


def score_ticketmaster_url(url: str, artist_name: str) -> float:
    """Higher is better (mirrors frontend eventSourceLinks scoring)."""
    try:
        parsed = urlparse(url)
    except Exception:
        return -1e9
    path = f"{parsed.path}{parsed.query}".lower()
    score = _domain_score(parsed.hostname or "")
    score += _artist_slug_score(path, artist_name)
    if "/event/" in path:
        score += 35.0
    if "/trk/" in path:
        score -= 80.0
    if "/venue/" in path:
        score += 8.0
    return score


def collect_ticketmaster_url_candidates(ev: dict[str, Any]) -> list[str]:
    """Gather URL strings TM may attach to an event."""
    out: list[str] = []
    u = (ev.get("url") or "").strip()
    if u:
        out.append(u)
    for op in ev.get("outlets") or []:
        if isinstance(op, dict):
            ou = (op.get("url") or "").strip()
            if ou:
                out.append(ou)
    # de-dupe preserving order
    seen: set[str] = set()
    uniq: list[str] = []
    for x in out:
        if x in seen:
            continue
        seen.add(x)
        uniq.append(x)
    return uniq


def pick_best_ticketmaster_url(ev: dict[str, Any], artist_name: str) -> str | None:
    """Prefer ticketmaster.com /event/ URLs over fgtix shortlinks when TM exposes both."""
    cands = collect_ticketmaster_url_candidates(ev)
    if not cands:
        return None
    if len(cands) == 1:
        return cands[0][:1024]
    best = max(cands, key=lambda url: (score_ticketmaster_url(url, artist_name), len(url)))
    return best[:1024] if best else None


_FESTIVAL_NAME_HINTS = (
    "festival",
    "sonic temple",
    "rockville",
    "aftershock",
    "inkcarceration",
    "lollapalooza",
    "bonnaroo",
    "coachella",
    "welcome to rock",
    "hellfest",
    "riot fest",
    "bamboozle",
    "ohana",
    "download festival",
    "tortuga",
)


def classify_ticketmaster_event(ev: dict[str, Any]) -> tuple[str, str | None, str | None]:
    """
    Returns (event_kind, festival_key, tm_event_name).

    event_kind: show | festival | tour_package
    festival_key: stable id for UI grouping (tm:<discovery_event_id>) when not a plain show.
    """
    name = (ev.get("name") or "").strip()
    name_lower = name.lower()
    ext_id = str(ev.get("id") or "").strip()
    key_base = f"tm:{ext_id}" if ext_id else None

    emb = ev.get("_embedded") or {}
    attractions = emb.get("attractions") or []
    n_attr = len(attractions) if isinstance(attractions, list) else 0

    venues = emb.get("venues") or []
    venue_lower = ""
    if venues and isinstance(venues[0], dict):
        venue_lower = (venues[0].get("name") or "").lower()

    url_l = (ev.get("url") or "").lower()
    is_fgtix = "fgtix.com" in url_l or "/trk/" in url_l

    if any(h in name_lower for h in _FESTIVAL_NAME_HINTS) or "festival" in venue_lower:
        return ("festival", key_base, name or None)

    if n_attr >= 10 or (n_attr >= 6 and is_fgtix):
        return ("tour_package", key_base, name or None)

    if n_attr >= 5:
        return ("tour_package", key_base, name or None)

    return ("show", None, name or None)


def event_kind_rank(kind: str) -> int:
    return {"show": 0, "tour_package": 1, "festival": 2}.get(kind, 0)


def merge_event_kind(existing: str | None, incoming: str | None) -> str:
    a = (existing or "show").strip() or "show"
    b = (incoming or "show").strip() or "show"
    return b if event_kind_rank(b) > event_kind_rank(a) else a
