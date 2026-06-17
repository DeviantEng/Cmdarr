"""Unit tests for SeatGeek client normalization and matching."""

from datetime import UTC, datetime

from clients.client_seatgeek import SeatGeekClient, _event_features_artist, _pick_performer


def test_pick_performer_prefers_exact_name():
    performers = [
        {"id": 2, "name": "Autumn"},
        {"id": 1, "name": "Autumn Kings"},
    ]
    picked = _pick_performer(performers, "Autumn Kings")
    assert picked["id"] == 1


def test_event_features_artist_on_performer_list():
    ev = {
        "title": "Rock Night",
        "performers": [{"name": "Autumn Kings"}, {"name": "Support Act"}],
    }
    assert _event_features_artist(ev, "Autumn Kings") is True
    assert _event_features_artist(ev, "Other Band") is False


def test_normalize_event_maps_seatgeek_fields():
    client = SeatGeekClient(config={}, client_id="test-id")
    now = datetime(2026, 1, 1, tzinfo=UTC)
    ev = {
        "id": 721901,
        "title": "Young the Giant",
        "url": "https://seatgeek.com/young-the-giant-tickets/new-york-2012-03-09/concert/721901/",
        "datetime_utc": "2026-09-18T01:00:00",
        "datetime_local": "2026-09-17T21:00:00",
        "performers": [{"name": "Young the Giant"}],
        "venue": {
            "name": "Terminal 5",
            "city": "New York",
            "state": "NY",
            "country": "US",
            "location": {"lat": 40.77, "lon": -74.0},
        },
    }
    norm = client._normalize_event(ev, "mbid-1", "Young the Giant", now)
    assert norm is not None
    assert norm["provider"] == "seatgeek"
    assert norm["external_id"] == "721901"
    assert norm["venue_city"] == "New York"
    assert norm["venue_lat"] == 40.77
