"""Tests for venue geocode cache and query building."""

import sqlite3

from utils.venue_geocode import (
    build_nominatim_query,
    read_geocode_cache,
    venue_geocode_cache_key,
    write_geocode_cache,
)


def test_build_nominatim_query_from_deezer_place():
    q = build_nominatim_query(
        "Freedom Mortgage Pavilion",
        "Camden, NJ, US",
        None,
    )
    assert "Freedom Mortgage Pavilion" in q
    assert "Camden" in q
    assert "NJ" in q
    assert "USA" in q


def test_geocode_cache_roundtrip():
    conn = sqlite3.connect(":memory:")
    cur = conn.cursor()
    key = venue_geocode_cache_key("Brooklyn Bowl", "Nashville", "TN")
    assert read_geocode_cache(cur, key) is None
    write_geocode_cache(cur, key, 36.16, -86.77)
    conn.commit()
    assert read_geocode_cache(cur, key) == (36.16, -86.77)
    conn.close()
