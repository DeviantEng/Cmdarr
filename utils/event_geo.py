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


def coerce_location_str(val: Any) -> str | None:
    """Normalize city/region/name fields from APIs that sometimes return nested objects."""
    if val is None:
        return None
    if isinstance(val, str):
        s = val.strip()
        return s if s else None
    if isinstance(val, (int, float)):
        return str(val)
    if isinstance(val, dict):
        # Ticketmaster: { stateCode, name }; country: { countryCode, name }
        for k in (
            "stateCode",
            "countryCode",
            "name",
            "code",
            "region",
            "state",
            "abbreviation",
            "displayName",
        ):
            v = val.get(k)
            if isinstance(v, str) and v.strip():
                return v.strip()
            if isinstance(v, (int, float)):
                return str(v)
        return None
    return str(val).strip() or None


def normalize_city_name(city: str | None) -> str:
    """Normalize US city names for dedupe: expand St./Mt./Ft., strip punctuation, lowercase."""
    if not city:
        return ""
    s = str(city).strip().lower()
    s = re.sub(r"\bst\.?\s+", "saint ", s)
    s = re.sub(r"\bmt\.?\s+", "mount ", s)
    s = re.sub(r"\bft\.?\s+", "fort ", s)
    s = re.sub(r"[^a-z0-9\s]+", "", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def normalize_venue_name(name: str | None, city: str | None = None) -> str:
    """
    Normalize a venue name for dedupe. Examples this collapses:
      "The Basement East"      -> "basement east"
      "Roxy Theatre-CA"        -> "roxy theatre"
      "Madison Live (734)"     -> "madison live"
      "Madison Live - Covington" (city=Covington) -> "madison live"
    """
    if not name:
        return ""
    s = str(name).strip().lower()
    s = re.sub(r"^the\s+", "", s)
    s = re.sub(r"\s*\([^)]*\)\s*$", "", s)
    s = re.sub(r"\s*[-–]\s*[a-z]{2,3}\s*$", "", s)
    if city:
        city_norm = normalize_city_name(city)
        if city_norm:
            s = re.sub(rf"\s*[-–]\s*{re.escape(city_norm)}\s*$", "", s)
    s = re.sub(r"\s*[-–]\s*[a-z][a-z\s]*$", "", s)
    s = re.sub(r"[^a-z0-9]+", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def venue_fingerprint(
    venue_name: str | None,
    city: str | None,
    region: str | None,
    lat: float | None,
    lon: float | None,
) -> str:
    """
    Stable string for dedupe heuristics.

    When a venue name is present, it is authoritative together with normalized city/region
    and geo is IGNORED — two TM/BIT/SK responses for the same venue often disagree on
    coordinates by 0.01°–0.05° (venue centroid vs. street address geocode), and letting
    that drive dedupe splits one show into multiple canonical rows.

    When no venue name is available, fall back to geo (rounded to ~11 km) plus city/region
    so events sharing a city/date with no venue info still merge.
    """
    c_norm = normalize_city_name(coerce_location_str(city))
    r_norm = (coerce_location_str(region) or "").strip().lower()
    vn = normalize_venue_name(coerce_location_str(venue_name), c_norm)
    if vn:
        raw = f"v|{vn}|{c_norm}|{r_norm}"
    else:
        if lat is not None and lon is not None:
            geo = f"{round(lat, 1)},{round(lon, 1)}"
        else:
            geo = ""
        raw = f"g|{c_norm}|{r_norm}|{geo}"
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


def lat_lon_deg_bounds_for_radius_miles(
    lat: float, lon: float, miles: float
) -> tuple[float, float, float, float]:
    """
    Axis-aligned bounding box in degrees that contains a circle of `miles` around (lat, lon).
    Used to narrow SQL before haversine (US-scale distances).
    """
    if miles <= 0:
        miles = 0.01
    lat_pad = miles / 69.0
    cos_lat = max(0.2, abs(math.cos(math.radians(lat))))
    lon_pad = miles / (69.0 * cos_lat)
    return lat - lat_pad, lat + lat_pad, lon - lon_pad, lon + lon_pad
