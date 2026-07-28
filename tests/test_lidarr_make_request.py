"""Unit tests for Lidarr client HTTP status handling."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from clients.client_lidarr import LidarrClient


def _client() -> LidarrClient:
    cfg = MagicMock()
    cfg.LIDARR_URL = "http://lidarr.test"
    cfg.LIDARR_API_KEY = "test-key"
    cfg.LIDARR_TIMEOUT = 30
    cfg.LIDARR_IGNORE_TLS = True
    client = LidarrClient(cfg)
    client.cache_enabled = False
    client.cache = None
    return client


@pytest.mark.asyncio
async def test_make_request_accepts_201_created():
    """Lidarr POST /artist returns 201 with the created artist body."""
    client = _client()
    created = {"id": 2540, "artistName": "Sianvar", "foreignArtistId": "abc"}

    response = MagicMock()
    response.status = 201
    response.json = AsyncMock(return_value=created)
    response.text = AsyncMock(return_value="")
    response.__aenter__ = AsyncMock(return_value=response)
    response.__aexit__ = AsyncMock(return_value=None)

    session = MagicMock()
    session.request = MagicMock(return_value=response)
    session.__aenter__ = AsyncMock(return_value=session)
    session.__aexit__ = AsyncMock(return_value=None)

    with patch("clients.client_lidarr.aiohttp.ClientSession", return_value=session):
        data = await client._make_request("artist", method="POST", json={"artistName": "Sianvar"})

    assert data == created


@pytest.mark.asyncio
async def test_make_request_still_rejects_4xx():
    client = _client()

    response = MagicMock()
    response.status = 400
    response.text = AsyncMock(return_value='{"message":"bad"}')
    response.raise_for_status = MagicMock(side_effect=Exception("400"))
    response.__aenter__ = AsyncMock(return_value=response)
    response.__aexit__ = AsyncMock(return_value=None)

    session = MagicMock()
    session.request = MagicMock(return_value=response)
    session.__aenter__ = AsyncMock(return_value=session)
    session.__aexit__ = AsyncMock(return_value=None)

    with (
        patch("clients.client_lidarr.aiohttp.ClientSession", return_value=session),
        pytest.raises(Exception, match="400"),
    ):
        await client._make_request("artist", method="POST", json={})


@pytest.mark.asyncio
async def test_get_all_artists_force_refresh_bypasses_cache():
    client = _client()
    client.cache_enabled = True
    cache = MagicMock()
    cache.get.return_value = [
        {"musicBrainzId": "stale", "artistName": "Stale"},
    ]
    cache.delete.return_value = True
    cache.set.return_value = None
    client.cache = cache
    client.config.NEW_RELEASES_CACHE_DAYS = 14

    live = [
        {
            "foreignArtistId": "fresh-mbid",
            "artistName": "Sianvar",
            "id": 1,
            "status": "continuing",
            "monitored": True,
            "monitorNewItems": "all",
            "links": [],
        }
    ]
    client._make_request = AsyncMock(return_value=live)

    artists = await client.get_all_artists(force_refresh=True)

    cache.delete.assert_called_once_with("lidarr_artists_v3", "lidarr")
    cache.get.assert_not_called()
    assert len(artists) == 1
    assert artists[0]["musicBrainzId"] == "fresh-mbid"
    assert artists[0]["artistName"] == "Sianvar"


@pytest.mark.asyncio
async def test_add_artist_success_invalidates_artists_cache():
    client = _client()
    client.cache_enabled = True
    cache = MagicMock()
    client.cache = cache

    client.get_artist_by_mbid = AsyncMock(return_value=None)
    client.get_quality_profiles = AsyncMock(return_value=[{"id": 1}])
    client.get_metadata_profiles = AsyncMock(return_value=[{"id": 2}])
    client.get_root_folders = AsyncMock(return_value=[{"path": "/music"}])
    client._make_request = AsyncMock(return_value={"id": 9, "artistName": "Sianvar"})

    result = await client.add_artist(
        "mbid-sianvar", "Sianvar", quality_profile_id=1, metadata_profile_id=2
    )

    assert result["success"] is True
    cache.delete.assert_called_once_with("lidarr_artists_v3", "lidarr")
