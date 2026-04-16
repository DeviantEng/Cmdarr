"""Unit tests for event geo helpers."""

from utils.event_geo import haversine_miles, make_dedupe_key, venue_fingerprint


def test_haversine_miles_approx_known():
    # ~2450 mi NYC to LA (rough)
    nyc = (40.7128, -74.006)
    la = (34.0522, -118.2437)
    d = haversine_miles(nyc[0], nyc[1], la[0], la[1])
    assert 2400 < d < 2500


def test_dedupe_key_stable():
    fp = venue_fingerprint("The Fillmore", "San Francisco", "CA", 37.7845, -122.4324)
    k1 = make_dedupe_key("mbid-1", "2026-06-01", fp)
    k2 = make_dedupe_key("mbid-1", "2026-06-01", fp)
    assert k1 == k2
    assert k1 != make_dedupe_key("mbid-2", "2026-06-01", fp)
