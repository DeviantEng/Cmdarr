"""Unit tests for event geo helpers."""

from utils.event_geo import (
    coerce_location_str,
    haversine_miles,
    lat_lon_deg_bounds_for_radius_miles,
    make_dedupe_key,
    parse_float,
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


def test_lat_lon_bounds_contains_center():
    lat_min, lat_max, lon_min, lon_max = lat_lon_deg_bounds_for_radius_miles(38.0, -84.5, 100)
    assert lat_min < 38.0 < lat_max
    assert lon_min < -84.5 < lon_max


def test_venue_fingerprint_accepts_dict_region():
    """Bandsintown may return region as a nested object."""
    fp_str = venue_fingerprint("Venue", "Portland", "Oregon", 45.5, -122.6)
    fp_dict = venue_fingerprint("Venue", "Portland", {"name": "Oregon"}, 45.5, -122.6)
    assert fp_str == fp_dict


def test_venue_fingerprint_merges_slightly_different_coords():
    """Same venue from two API responses with noisy coordinates should dedupe together."""
    fp_a = venue_fingerprint("Nissan Stadium", "Nashville", "TN", 36.16251, -86.77148)
    fp_b = venue_fingerprint("Nissan Stadium", "Nashville", "TN", 36.16284, -86.77112)
    assert fp_a == fp_b


def test_venue_fingerprint_differs_for_distinct_venues():
    a = venue_fingerprint("Nissan Stadium", "Nashville", "TN", 36.1625, -86.7714)
    b = venue_fingerprint("Bridgestone Arena", "Nashville", "TN", 36.1591, -86.7784)
    c = venue_fingerprint("Nissan Stadium", "Nashville", "TN", 40.0, -80.0)
    assert a != b
    assert a != c


def test_haversine_self_is_zero_and_symmetric():
    p = (36.1625, -86.7714)
    q = (34.0522, -118.2437)
    assert haversine_miles(*p, *p) == 0
    assert abs(haversine_miles(*p, *q) - haversine_miles(*q, *p)) < 1e-9


def test_make_dedupe_key_changes_with_inputs():
    fp = venue_fingerprint("V", "C", "R", 1.0, 2.0)
    k1 = make_dedupe_key("mbid", "2026-06-01", fp)
    k2 = make_dedupe_key("mbid", "2026-06-02", fp)
    fp2 = venue_fingerprint("V2", "C", "R", 1.0, 2.0)
    k3 = make_dedupe_key("mbid", "2026-06-01", fp2)
    assert k1 != k2
    assert k1 != k3


def test_parse_float_handles_inputs():
    assert parse_float(None) is None
    assert parse_float("") is None
    assert parse_float("abc") is None
    assert parse_float("1.5") == 1.5
    assert parse_float(2) == 2.0
    assert parse_float({"x": 1}) is None
