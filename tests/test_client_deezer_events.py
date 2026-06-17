"""Unit tests for Deezer events client normalization."""

from datetime import UTC, datetime

from clients.client_deezer_events import DeezerEventsClient, _event_features_artist


def test_event_features_artist_matches_title_tokens():
    node = {"name": "Autumn Kings at Brooklyn Bowl"}
    assert _event_features_artist(node, "Autumn Kings") is True


def test_normalize_event_maps_deezer_fields():
    client = DeezerEventsClient(config={}, arl="arl")
    now = datetime(2026, 1, 1, tzinfo=UTC)
    node = {
        "id": "evt-99",
        "name": "Autumn Kings at Brooklyn Bowl",
        "startDate": "2026-09-18",
        "venue": "Brooklyn Bowl",
        "cityName": "Nashville",
        "countryCode": "US",
        "types": {"isConcert": True, "isFestival": False},
        "sources": {"defaultUrl": "https://www.songkick.com/concerts/12345"},
    }
    norm = client._normalize_event(node, "mbid-1", "Autumn Kings", now, "27")
    assert norm is not None
    assert norm["provider"] == "deezer"
    assert norm["external_id"] == "evt-99"
    assert norm["source_url"] == "https://www.songkick.com/concerts/12345"
    assert norm["local_date"] == "2026-09-18"
