"""Unit tests for clients/client_xmplaylist.py (no network)."""

from unittest.mock import MagicMock

import pytest

from clients.client_xmplaylist import (
    MOST_HEARD_DAYS,
    XmplaylistClient,
    _join_artists,
    _normalize_track_row,
)
from utils.logger import setup_application_logging


def test_normalize_track_row_nested():
    raw = {
        "track": {
            "title": "Song",
            "artists": [{"name": "Artist One"}, {"name": "Artist Two"}],
            "album": {"title": "Album X"},
        }
    }
    out = _normalize_track_row(raw)
    assert out == {"track": "Song", "artist": "Artist One, Artist Two", "album": "Album X"}


def test_normalize_track_row_ignores_extra_keys():
    raw = {
        "track": {"title": "A", "artists": ["Solo"]},
        "spotify": {"id": "x"},
        "deezer": {"link": "y"},
    }
    out = _normalize_track_row(raw)
    assert out == {"track": "A", "artist": "Solo", "album": ""}


def test_normalize_track_row_rejects_missing_artist():
    assert _normalize_track_row({"track": {"title": "Only Title"}}) is None


def test_join_artists_mixed():
    assert _join_artists([{"name": "A"}, "B"]) == "A, B"
    assert _join_artists(None) == ""


def test_most_heard_days_constant():
    assert MOST_HEARD_DAYS == {1, 7, 14, 30, 60}


@pytest.fixture
def xmplaylist_client():
    setup_application_logging(
        MagicMock(LOG_LEVEL="ERROR", LOG_FILE="data/logs/cmdarr_test.log", LOG_RETENTION_DAYS=1)
    )

    class DummyCfg:
        XMPLAYLIST_RATE_LIMIT = 10.0

    return XmplaylistClient(DummyCfg())


def test_xmplaylist_client_user_agent_from_config():
    from utils.cmdarr_user_agent import DEFAULT_CMDARR_USER_AGENT

    setup_application_logging(
        MagicMock(LOG_LEVEL="ERROR", LOG_FILE="data/logs/cmdarr_test.log", LOG_RETENTION_DAYS=1)
    )

    class C:
        XMPLAYLIST_RATE_LIMIT = 10.0

    assert XmplaylistClient(C()).headers["User-Agent"] == DEFAULT_CMDARR_USER_AGENT

    class C2:
        XMPLAYLIST_RATE_LIMIT = 10.0
        CMDARR_USER_AGENT = "Cmdarr-test/1 (+https://example.test)"

    assert XmplaylistClient(C2()).headers["User-Agent"] == "Cmdarr-test/1 (+https://example.test)"


@pytest.mark.asyncio
async def test_fetch_tracks_newest_stops_at_max(xmplaylist_client, monkeypatch):
    """Paginate until max_tracks using synthetic `next` URLs."""

    client = xmplaylist_client
    calls: list[str] = []

    async def fake_make_request(endpoint, params=None, method="GET", **kwargs):
        calls.append(endpoint)
        if "page=2" in endpoint or endpoint.endswith("/newest?page=2"):
            return {
                "results": [{"track": {"title": "B", "artists": [{"name": "Ba"}]}}],
                "next": None,
            }
        return {
            "results": [{"track": {"title": "A", "artists": [{"name": "Aa"}]}}],
            "next": "https://xmplaylist.com/api/station/octane/newest?page=2",
        }

    monkeypatch.setattr(client, "_make_request", fake_make_request)

    tracks = await client.fetch_tracks_newest("octane", max_tracks=2, max_pages=5)
    assert len(tracks) == 2
    assert tracks[0]["track"] == "A"
    assert tracks[1]["track"] == "B"
    assert len(calls) == 2


@pytest.mark.asyncio
async def test_fetch_tracks_most_heard_invalid_days(xmplaylist_client):
    client = xmplaylist_client
    with pytest.raises(ValueError, match="most_heard days"):
        await client.fetch_tracks_most_heard("octane", days=99, max_tracks=5)
