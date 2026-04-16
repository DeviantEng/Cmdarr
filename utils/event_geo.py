"""Haversine distance and venue fingerprinting for artist events (US-focused)."""

from __future__ import annotations

import hashlib
import math
import re
from typing import Any


def haversine_miles(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance in miles between two WGS84 points."""
    r = 3958.7613  # Earth radius in miles
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlmb = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlmb / 2) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(max(0.0, 1 - a)))
    return r * c


def normalize_venue_name(name: str | None) -> str:
    if not name:
        return ""
    s = name.strip().lower()
    s = re.sub(r"^the\s+", "", s)
    s = re.sub(r"\s+", " ", s)
    return s


def venue_fingerprint(
    venue_name: str | None,
    city: str | None,
    region: str | None,
    lat: float | None,
    lon: float | None,
) -> str:
    """Stable string for dedupe heuristics."""
    vn = normalize_venue_name(venue_name)
    c = (city or "").strip().lower()
    r = (region or "").strip().lower()
    if lat is not None and lon is not None:
        geo = f"{round(lat, 4)},{round(lon, 4)}"
    else:
        geo = ""
    raw = f"{vn}|{c}|{r}|{geo}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:24]


def make_dedupe_key(artist_mbid: str, local_date: str, fp: str) -> str:
    raw = f"{artist_mbid}|{local_date}|{fp}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def parse_float(val: Any) -> float | None:
    if val is None:
        return None
    try:
        return float(val)
    except TypeError, ValueError:
        return None
