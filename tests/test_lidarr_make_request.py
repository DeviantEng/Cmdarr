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
