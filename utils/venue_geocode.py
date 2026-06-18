"""Nominatim geocoding for artist event venues with SQLite cache."""

from __future__ import annotations

import hashlib
import logging
import sqlite3
from typing import Any

import aiohttp

from utils.event_geo import coerce_location_str, parse_place_city_region

logger = logging.getLogger("cmdarr.venue_geocode")


def venue_geocode_cache_key(
    venue_name: str | None,
    city: str | None,
    region: str | None,
    *,
    country: str = "US",
) -> str:
    city_p, region_p = parse_place_city_region(city, region)
    parts = [
        (coerce_location_str(venue_name) or "").strip().lower(),
        (city_p or "").strip().lower(),
        (region_p or "").strip().lower(),
        country.strip().upper(),
    ]
    raw = "|".join(parts)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _ensure_cache_table(cursor: sqlite3.Cursor) -> None:
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS venue_geocode_cache (
            cache_key TEXT PRIMARY KEY,
            lat REAL NOT NULL,
            lon REAL NOT NULL,
            queried_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)


def read_geocode_cache(cursor: sqlite3.Cursor, cache_key: str) -> tuple[float, float] | None:
    _ensure_cache_table(cursor)
    cursor.execute(
        "SELECT lat, lon FROM venue_geocode_cache WHERE cache_key = ?",
        (cache_key,),
    )
    row = cursor.fetchone()
    if not row:
        return None
    return float(row[0]), float(row[1])


def write_geocode_cache(cursor: sqlite3.Cursor, cache_key: str, lat: float, lon: float) -> None:
    _ensure_cache_table(cursor)
    cursor.execute(
        """
        INSERT OR REPLACE INTO venue_geocode_cache (cache_key, lat, lon, queried_at)
        VALUES (?, ?, ?, CURRENT_TIMESTAMP)
        """,
        (cache_key, lat, lon),
    )


def build_nominatim_query(
    venue_name: str | None,
    city: str | None,
    region: str | None,
    *,
    country: str = "US",
) -> str:
    city_p, region_p = parse_place_city_region(city, region)
    bits: list[str] = []
    if venue_name:
        bits.append(coerce_location_str(venue_name) or "")
    if city_p:
        bits.append(city_p)
    if region_p:
        bits.append(region_p)
    if country.upper() in ("US", "USA"):
        bits.append("USA")
    else:
        bits.append(country)
    return ", ".join(b for b in bits if b)


async def geocode_us_venue(
    session: aiohttp.ClientSession,
    venue_name: str | None,
    city: str | None,
    region: str | None,
    *,
    user_agent: str,
    country: str = "US",
) -> tuple[float, float] | None:
    """Resolve a US venue to lat/lon via Nominatim (best effort)."""
    query = build_nominatim_query(venue_name, city, region, country=country)
    if not query.strip():
        return None
    url = "https://nominatim.openstreetmap.org/search"
    params = {"q": query, "format": "json", "limit": "1", "countrycodes": "us"}
    try:
        async with session.get(
            url,
            params=params,
            headers={"User-Agent": user_agent},
            timeout=aiohttp.ClientTimeout(total=15),
        ) as resp:
            if resp.status != 200:
                logger.warning("Nominatim HTTP %s for venue geocode", resp.status)
                return None
            data: Any = await resp.json()
    except Exception as exc:
        logger.warning("Nominatim venue geocode failed: %s", exc)
        return None
    if not data or not isinstance(data, list):
        return None
    row = data[0]
    try:
        return float(row["lat"]), float(row["lon"])
    except KeyError, TypeError, ValueError:
        return None


async def resolve_venue_coordinates(
    session: aiohttp.ClientSession,
    cursor: sqlite3.Cursor,
    venue_name: str | None,
    city: str | None,
    region: str | None,
    *,
    user_agent: str,
    country: str = "US",
) -> tuple[float, float] | None:
    """Cache lookup, then Nominatim on miss."""
    key = venue_geocode_cache_key(venue_name, city, region, country=country)
    cached = read_geocode_cache(cursor, key)
    if cached:
        return cached
    coords = await geocode_us_venue(
        session,
        venue_name,
        city,
        region,
        user_agent=user_agent,
        country=country,
    )
    if coords:
        write_geocode_cache(cursor, key, coords[0], coords[1])
    return coords
