"""Unit tests for Lidarr add_artist profile selection."""

from unittest.mock import AsyncMock, MagicMock

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
async def test_add_artist_uses_selected_profiles():
    client = _client()
    client.get_artist_by_mbid = AsyncMock(return_value=None)
    client.get_quality_profiles = AsyncMock(
        return_value=[{"id": 1, "name": "Any"}, {"id": 2, "name": "Lossless"}]
    )
    client.get_metadata_profiles = AsyncMock(
        return_value=[{"id": 10, "name": "Standard"}, {"id": 11, "name": "None"}]
    )
    client.get_root_folders = AsyncMock(return_value=[{"path": "/music"}])
    client._make_request = AsyncMock(return_value={"id": 99, "artistName": "Sianvar"})

    result = await client.add_artist(
        mbid="5d1a111d-7fc3-41d5-b996-c2ca08ed76fd",
        artist_name="Sianvar",
        quality_profile_id=2,
        metadata_profile_id=11,
        search_for_missing_albums=True,
    )

    assert result["success"] is True
    payload = client._make_request.await_args.kwargs["json"]
    assert payload["qualityProfileId"] == 2
    assert payload["metadataProfileId"] == 11
    assert payload["addOptions"]["searchForMissingAlbums"] is True


@pytest.mark.asyncio
async def test_add_artist_falls_back_when_profile_id_invalid():
    client = _client()
    client.get_artist_by_mbid = AsyncMock(return_value=None)
    client.get_quality_profiles = AsyncMock(return_value=[{"id": 1, "name": "Any"}])
    client.get_metadata_profiles = AsyncMock(return_value=[{"id": 10, "name": "Standard"}])
    client.get_root_folders = AsyncMock(return_value=[{"path": "/music"}])
    client._make_request = AsyncMock(return_value={"id": 1})

    result = await client.add_artist(
        mbid="abc",
        artist_name="X",
        quality_profile_id=999,
        metadata_profile_id=999,
    )

    assert result["success"] is True
    payload = client._make_request.await_args.kwargs["json"]
    assert payload["qualityProfileId"] == 1
    assert payload["metadataProfileId"] == 10
