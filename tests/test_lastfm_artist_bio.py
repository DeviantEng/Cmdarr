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
async def test_get_artist_info_prefer_bio_uses_name_bio():
    client = _client()
    client._make_request = AsyncMock(
        side_effect=[
            {
                "artist": {
                    "name": "Radiohead",
                    "mbid": "a74b1b7f-71a5-4011-9441-d0b5e4122711",
                    "url": "https://www.last.fm/music/Radiohead",
                    "stats": {"listeners": "10", "playcount": "20"},
                    "bio": {"summary": "A band from Oxford.", "content": "Full bio."},
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
async def test_get_artist_info_prefer_bio_falls_back_to_mbid_bio():
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
                    "bio": {"summary": "MBID bio.", "content": ""},
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


@pytest.mark.asyncio
async def test_parse_artist_info_falls_back_to_wiki_key():
    """Legacy/docs shape used wiki; live JSON uses bio — accept either."""
    client = _client()
    info = client._parse_artist_info_response(
        {
            "artist": {
                "name": "Radiohead",
                "mbid": "a74b1b7f-71a5-4011-9441-d0b5e4122711",
                "url": "https://www.last.fm/music/Radiohead",
                "stats": {"listeners": "10", "playcount": "20"},
                "wiki": {"summary": "Wiki-shaped summary.", "content": ""},
            }
        }
    )
    assert info is not None
    assert info["bio_summary"] == "Wiki-shaped summary."
