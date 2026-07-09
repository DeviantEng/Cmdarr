"""Tests for Last.fm top tracks MBID parameter and fallback."""

import pytest

from clients.client_lastfm import LastFMClient


@pytest.fixture
def lastfm_client():
    client = LastFMClient.__new__(LastFMClient)
    client.cache_enabled = False
    client.cache = None
    client.logger = __import__("logging").getLogger("test.lastfm")
    client.config = type(
        "Cfg", (), {"CACHE_FAILED_LOOKUP_TTL_DAYS": 7, "CACHE_LASTFM_TTL_DAYS": 7}
    )()
    return client


@pytest.mark.asyncio
async def test_get_top_tracks_uses_mbid_param(lastfm_client, monkeypatch):
    captured: dict = {}

    async def fake_request(params, context_info=""):
        captured["params"] = params
        captured["context"] = context_info
        return {
            "toptracks": {
                "track": [{"name": "Song", "artist": {"name": "Gore."}, "playcount": "1"}]
            }
        }

    monkeypatch.setattr(lastfm_client, "_make_request", fake_request)
    tracks = await lastfm_client.get_top_tracks(
        "Gore.", limit=5, mbid="f5d4e4ae-90b8-4b30-aa74-a9bf36170bd4"
    )
    assert captured["params"]["mbid"] == "f5d4e4ae-90b8-4b30-aa74-a9bf36170bd4"
    assert "artist" not in captured["params"]
    assert len(tracks) == 1
    assert tracks[0]["name"] == "Song"


@pytest.mark.asyncio
async def test_get_top_tracks_mbid_empty_falls_back_to_name(lastfm_client, monkeypatch):
    calls: list[dict] = []

    async def fake_request(params, context_info=""):
        calls.append(dict(params))
        if "mbid" in params:
            return {"toptracks": {"track": []}}
        return {
            "toptracks": {
                "track": [
                    {"name": "Mean Man's Dream", "artist": {"name": "Gore."}, "playcount": "5"}
                ]
            }
        }

    monkeypatch.setattr(lastfm_client, "_make_request", fake_request)
    tracks = await lastfm_client.get_top_tracks(
        "Gore.", limit=5, mbid="f5d4e4ae-90b8-4b30-aa74-a9bf36170bd4"
    )
    assert len(calls) == 2
    assert "mbid" in calls[0]
    assert calls[1]["artist"] == "Gore."
    assert len(tracks) == 1
    assert tracks[0]["name"] == "Mean Man's Dream"


@pytest.mark.asyncio
async def test_get_top_tracks_mbid_failure_falls_back_to_name(lastfm_client, monkeypatch):
    calls: list[dict] = []

    async def fake_request(params, context_info=""):
        calls.append(dict(params))
        if "mbid" in params:
            return None
        return {
            "toptracks": {
                "track": [{"name": "Song", "artist": {"name": "Gore."}, "playcount": "1"}]
            }
        }

    monkeypatch.setattr(lastfm_client, "_make_request", fake_request)
    tracks = await lastfm_client.get_top_tracks(
        "Gore.", limit=5, mbid="f5d4e4ae-90b8-4b30-aa74-a9bf36170bd4"
    )
    assert len(calls) == 2
    assert len(tracks) == 1
