"""Ticketmaster Discovery event helpers: public URL selection and festival/tour classification."""

from __future__ import annotations

import re
from typing import Any
from urllib.parse import urlparse

_TOKEN_RE = re.compile(r"[a-z0-9']+", re.I)


def _hostname_is_domain_or_subdomain(hostname: str, domain: str) -> bool:
    """True for `ticketmaster.com` or `www.ticketmaster.com`, not `evilticketmaster.com`."""
    h = hostname.lower()
    d = domain.lower()
    return h == d or h.endswith("." + d)


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


_KNOWN_EVENT_DOMAINS: tuple[tuple[str, float], ...] = (
    ("ticketmaster.com", 100.0),
    ("livenation.com", 88.0),
    ("ticketweb.com", 72.0),
    ("axs.com", 65.0),
    ("etix.com", 58.0),
    ("universe.com", 52.0),
    ("gracelandlive.com", 44.0),
    ("fgtix.com", 6.0),
)


def _domain_score(hostname: str) -> float:
    h = hostname.lower()
    for domain, score in _KNOWN_EVENT_DOMAINS:
        if _hostname_is_domain_or_subdomain(h, domain):
            return score
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


def _group_title_for_festival_key(name: str) -> str:
    """Strip per-lineup / day suffixes so one festival shares one group key across TM event ids."""
    n = (name or "").strip()
    if not n:
        return ""
    if ":" in n:
        left = n.split(":", 1)[0].strip()
        if len(left) >= 4:
            n = left
    n = re.sub(
        r"\s+-\s+(?:day\s*\d+|friday|saturday|sunday|thursday|wednesday|monday|tuesday)\s*$",
        "",
        n,
        flags=re.I,
    ).strip()
    n = re.sub(r"\s*\([^)]*\)\s*$", "", n).strip()
    return n


def stable_festival_group_key(ev: dict[str, Any]) -> str | None:
    """Stable id across TM Discovery events that refer to the same festival/tour stop.

    TM returns a different `id` per keyword hit (e.g. each headliner day). We group by
    venue + calendar year + normalized title prefix instead of `tm:<event_id>`.
    """
    ext_id = str(ev.get("id") or "").strip()
    emb = ev.get("_embedded") or {}
    venues = emb.get("venues") or []
    venue_id = ""
    if venues and isinstance(venues[0], dict):
        venue_id = str(venues[0].get("id") or "").strip()
    dates = ev.get("dates") or {}
    start = dates.get("start") or {}
    local_date = str(start.get("localDate") or "")[:10]
    year = local_date[:4] if len(local_date) >= 4 else ""
    if not year:
        dt_raw = str(start.get("dateTime") or "")
        if len(dt_raw) >= 4 and dt_raw[:4].isdigit():
            year = dt_raw[:4]
    if not year:
        year = "0000"
    raw_name = (ev.get("name") or "").strip()
    title = _group_title_for_festival_key(raw_name)
    if not title:
        return f"tm:{ext_id}" if ext_id else None
    slug = re.sub(r"[^a-z0-9]+", "-", title.lower())
    slug = re.sub(r"-+", "-", slug).strip("-")[:96]
    if not slug:
        return f"tm:{ext_id}" if ext_id else None
    if venue_id:
        return f"tmfest:{venue_id}:{year}:{slug}"
    if ext_id:
        return f"tm:{ext_id}"
    return None


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
    "louder than life",
)

# TM appends "presented by …" tails; a hint there (e.g. "Riot Fest") is a sponsor, not the event name.
_SPONSOR_TAIL_START = re.compile(
    r"\b(?:presented by|presented in partnership with|brought to you by)\b",
    re.I,
)


def _festival_name_hint_matches(name_lower: str, hint: str) -> bool:
    if hint not in name_lower:
        return False
    m = _SPONSOR_TAIL_START.search(name_lower)
    if m is not None and name_lower.find(hint) >= m.start():
        return False
    return True


def classify_ticketmaster_event(ev: dict[str, Any]) -> tuple[str, str | None, str | None]:
    """
    Returns (event_kind, festival_key, tm_event_name).

    event_kind: show | festival | tour_package
    festival_key: stable id for UI grouping (tmfest:… from venue+year+title) when not a plain show.
    """
    name = (ev.get("name") or "").strip()
    name_lower = name.lower()

    emb = ev.get("_embedded") or {}
    attractions = emb.get("attractions") or []
    n_attr = len(attractions) if isinstance(attractions, list) else 0

    venues = emb.get("venues") or []
    venue_lower = ""
    if venues and isinstance(venues[0], dict):
        venue_lower = (venues[0].get("name") or "").lower()

    url_l = (ev.get("url") or "").lower()
    is_fgtix = "fgtix.com" in url_l or "/trk/" in url_l

    if (
        any(_festival_name_hint_matches(name_lower, h) for h in _FESTIVAL_NAME_HINTS)
        or "festival" in venue_lower
    ):
        return ("festival", stable_festival_group_key(ev), name or None)

    # Large multi-act TM events only: headliner + a few openers often yields 5–7 attractions.
    if n_attr >= 10 or (n_attr >= 6 and is_fgtix):
        return ("tour_package", stable_festival_group_key(ev), name or None)

    if n_attr >= 8:
        return ("tour_package", stable_festival_group_key(ev), name or None)

    return ("show", None, name or None)


def event_kind_rank(kind: str) -> int:
    return {"show": 0, "tour_package": 1, "festival": 2}.get(kind, 0)


def merge_event_kind(existing: str | None, incoming: str | None) -> str:
    a = (existing or "show").strip() or "show"
    b = (incoming or "show").strip() or "show"
    return b if event_kind_rank(b) > event_kind_rank(a) else a
