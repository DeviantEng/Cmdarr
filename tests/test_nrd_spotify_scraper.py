"""Tests for NRD Spotify source routing and unified client behavior."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from utils.nrd_release_source import (
    enrich_nrd_album_if_needed,
    normalize_nrd_source,
    nrd_lidarr_artist_id_key,
    nrd_mb_streaming_provider,
    nrd_release_client,
    nrd_uses_spotify,
)


def test_normalize_nrd_source_defaults_and_aliases():
    assert normalize_nrd_source(None) == "deezer"
    assert normalize_nrd_source("deezer") == "deezer"
    assert normalize_nrd_source("spotify_scraper") == "spotify"
    assert normalize_nrd_source("spotify") == "spotify"
    assert normalize_nrd_source("unknown") == "deezer"


def test_nrd_uses_spotify():
    assert nrd_uses_spotify("deezer") is False
    assert nrd_uses_spotify("spotify_scraper") is True
    assert nrd_uses_spotify("spotify") is True


def test_nrd_mb_streaming_provider():
    assert nrd_mb_streaming_provider("deezer") == "deezer"
    assert nrd_mb_streaming_provider("spotify_scraper") == "spotify"
    assert nrd_mb_streaming_provider("spotify") == "spotify"


def test_nrd_lidarr_artist_id_key():
    assert nrd_lidarr_artist_id_key("deezer") == "deezerArtistId"
    assert nrd_lidarr_artist_id_key("spotify_scraper") == "spotifyArtistId"


def test_nrd_release_client_routes_to_spotify():
    config = MagicMock()
    with patch("clients.client_spotify.SpotifyClient") as mock_spotify:
        nrd_release_client("spotify_scraper", config)
        mock_spotify.assert_called_once_with(config)


def test_nrd_release_client_routes_to_deezer():
    config = MagicMock()
    with patch("clients.client_deezer.DeezerClient") as mock_deezer:
        nrd_release_client("deezer", config)
        mock_deezer.assert_called_once_with(config)


def test_nrd_release_client_spotify_unified():
    config = MagicMock()
    with patch("clients.client_spotify.SpotifyClient") as mock_spotify:
        nrd_release_client("spotify", config)
        mock_spotify.assert_called_once_with(config)


@pytest.mark.asyncio
async def test_spotify_client_get_artist_albums_uses_scraper_without_creds():
    from clients.client_spotify import SpotifyClient

    config = MagicMock()
    config.SPOTIFY_CLIENT_ID = ""
    config.SPOTIFY_CLIENT_SECRET = ""
    config.NEW_RELEASES_CACHE_DAYS = 14
    client = SpotifyClient(config)
    client.cache_enabled = False

    mock_albums = {
        "success": True,
        "albums": [{"id": "a1", "name": "Album", "primary_artist_id": "art1"}],
    }
    with patch.object(client, "_run_scraper", new=AsyncMock(return_value=mock_albums)):
        result = await client.get_artist_albums("art1", fetch_all=True)
    assert result["success"] is True
    assert result["via"] == "scraper"
    assert len(result["albums"]) == 1


@pytest.mark.asyncio
async def test_spotify_client_get_artist_albums_api_fallback_to_scraper():
    from clients.client_spotify import SpotifyClient

    config = MagicMock()
    config.SPOTIFY_CLIENT_ID = "id"
    config.SPOTIFY_CLIENT_SECRET = "secret"
    config.NEW_RELEASES_CACHE_DAYS = 14
    client = SpotifyClient(config)
    client.cache_enabled = False

    scraper_result = {
        "success": True,
        "albums": [{"id": "a1", "name": "Album", "primary_artist_id": "art1"}],
    }
    with (
        patch.object(client, "_can_try_api", new=AsyncMock(return_value=True)),
        patch.object(
            client,
            "_get_artist_albums_api",
            new=AsyncMock(return_value={"success": False, "error": "fail", "albums": []}),
        ),
        patch.object(client, "_run_scraper", new=AsyncMock(return_value=scraper_result)),
    ):
        result = await client.get_artist_albums("art1", fetch_all=True)
    assert result["success"] is True
    assert result["via"] == "scraper"


@pytest.mark.asyncio
async def test_enrich_nrd_album_scraper_fallback():
    from clients.client_spotify import SpotifyClient

    config = MagicMock()
    config.SPOTIFY_CLIENT_ID = ""
    config.SPOTIFY_CLIENT_SECRET = ""
    client = SpotifyClient(config)
    disc_album = {"id": "a1", "name": "Disc", "primary_artist_id": "art1"}
    enriched = {"id": "a1", "name": "Full", "primary_artist_id": "art1", "spotify_url": "http://x"}
    with patch.object(
        client, "_run_scraper", new=AsyncMock(return_value={"success": True, "album": enriched})
    ):
        result = await client.enrich_nrd_album(disc_album)
    assert result["name"] == "Full"


@pytest.mark.asyncio
async def test_enrich_nrd_album_if_needed_skips_deezer():
    album = {"id": "1", "name": "A"}
    client = MagicMock()
    result = await enrich_nrd_album_if_needed(client, album, "deezer")
    assert result is album
    client.enrich_nrd_album.assert_not_called()


@pytest.mark.asyncio
async def test_test_connection_detail_scraper_when_no_creds():
    from clients.client_spotify import SpotifyClient

    config = MagicMock()
    config.SPOTIFY_CLIENT_ID = ""
    config.SPOTIFY_CLIENT_SECRET = ""
    client = SpotifyClient(config)
    with patch.object(client, "_test_scraper_connection", new=AsyncMock(return_value=True)):
        detail = await client.test_connection_detail()
    assert detail["success"] is True
    assert detail["mode"] == "scraper"


@pytest.mark.asyncio
async def test_test_connection_detail_api_failed_scraper_ok():
    from clients.client_spotify import SpotifyClient

    config = MagicMock()
    config.SPOTIFY_CLIENT_ID = "id"
    config.SPOTIFY_CLIENT_SECRET = "secret"
    client = SpotifyClient(config)
    with (
        patch.object(client, "_can_try_api", new=AsyncMock(return_value=True)),
        patch.object(client, "_get", new=AsyncMock(return_value=None)),
        patch.object(client, "_test_scraper_connection", new=AsyncMock(return_value=True)),
    ):
        detail = await client.test_connection_detail()
    assert detail["success"] is True
    assert detail["message"] == "API failed; scraper connected"


def test_new_releases_discovery_source_normalizes_spotify_scraper():
    from commands.new_releases_discovery import NewReleasesDiscoveryCommand

    cmd = NewReleasesDiscoveryCommand()
    cmd.config_json = {"new_releases_source": "spotify_scraper"}
    assert cmd._get_new_releases_source() == "spotify"
