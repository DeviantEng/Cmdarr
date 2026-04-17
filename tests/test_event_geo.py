"""Unit tests for event geo helpers."""

from utils.event_geo import (
    coerce_location_str,
    haversine_miles,
    make_dedupe_key,
    venue_fingerprint,
)


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


def test_coerce_location_str_nested_region():
    assert coerce_location_str({"name": "California"}) == "California"
    assert coerce_location_str({"code": "CA"}) == "CA"


def test_coerce_location_str_ticketmaster_style():
    assert coerce_location_str({"name": "Florida", "stateCode": "FL"}) == "FL"
    assert coerce_location_str({"name": "United States Of America", "countryCode": "US"}) == "US"


def test_venue_fingerprint_accepts_dict_region():
    """Bandsintown may return region as a nested object."""
    fp_str = venue_fingerprint("Venue", "Portland", "Oregon", 45.5, -122.6)
    fp_dict = venue_fingerprint("Venue", "Portland", {"name": "Oregon"}, 45.5, -122.6)
    assert fp_str == fp_dict
