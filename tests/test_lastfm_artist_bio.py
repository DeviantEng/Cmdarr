"""Unit tests for Last.fm artist info / bio preference."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from clients.client_lastfm import LastFMClient


def _client() -> LastFMClient:
    cfg = MagicMock()
    cfg.LASTFM_API_KEY = "test"
    cfg.LASTFM_RATE_LIMIT = 100.0
    client = LastFMClient(cfg)
    client.cache_enabled = False
    client.cache = None
    return client


@pytest.mark.asyncio
async def test_get_artist_info_prefer_bio_uses_name_wiki():
    client = _client()
    client._make_request = AsyncMock(
        side_effect=[
            {
                "artist": {
                    "name": "Radiohead",
                    "mbid": "a74b1b7f-71a5-4011-9441-d0b5e4122711",
                    "url": "https://www.last.fm/music/Radiohead",
                    "stats": {"listeners": "10", "playcount": "20"},
                    "wiki": {"summary": "A band from Oxford.", "content": "Full bio."},
                }
            }
        ]
    )

    info = await client.get_artist_info(
        mbid="a74b1b7f-71a5-4011-9441-d0b5e4122711",
        artist_name="Radiohead",
        prefer_bio=True,
    )

    assert info is not None
    assert info["bio_summary"] == "A band from Oxford."
    assert client._make_request.await_count == 1
    assert client._make_request.await_args.args[0]["artist"] == "Radiohead"
    assert client._make_request.await_args.args[0]["autocorrect"] == "1"


@pytest.mark.asyncio
async def test_get_artist_info_prefer_bio_falls_back_to_mbid_wiki():
    client = _client()
    client._make_request = AsyncMock(
        side_effect=[
            {
                "artist": {
                    "name": "Radiohead",
                    "mbid": "a74b1b7f-71a5-4011-9441-d0b5e4122711",
                    "url": "https://www.last.fm/music/Radiohead",
                    "stats": {"listeners": "10", "playcount": "20"},
                }
            },
            {
                "artist": {
                    "name": "Radiohead",
                    "mbid": "a74b1b7f-71a5-4011-9441-d0b5e4122711",
                    "url": "https://www.last.fm/music/Radiohead",
                    "stats": {"listeners": "10", "playcount": "20"},
                    "wiki": {"summary": "MBID bio.", "content": ""},
                }
            },
        ]
    )

    info = await client.get_artist_info(
        mbid="a74b1b7f-71a5-4011-9441-d0b5e4122711",
        artist_name="Radiohead",
        prefer_bio=True,
    )

    assert info is not None
    assert info["bio_summary"] == "MBID bio."
    assert client._make_request.await_count == 2
