"""Tests for NRD spotify_scraper source routing."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from utils.nrd_release_source import (
    normalize_nrd_source,
    nrd_lidarr_artist_id_key,
    nrd_mb_streaming_provider,
    nrd_release_client,
    nrd_uses_spotify,
)


def test_normalize_nrd_source_defaults_and_aliases():
    assert normalize_nrd_source(None) == "deezer"
    assert normalize_nrd_source("deezer") == "deezer"
    assert normalize_nrd_source("spotify_scraper") == "spotify_scraper"
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


def test_nrd_release_client_routes_to_scraper():
    config = MagicMock()
    with patch("clients.client_spotify.SpotifyClient") as mock_spotify:
        nrd_release_client("spotify_scraper", config)
        mock_spotify.assert_called_once_with(config, discography_source="scraper")


def test_nrd_release_client_routes_to_deezer():
    config = MagicMock()
    with patch("clients.client_deezer.DeezerClient") as mock_deezer:
        nrd_release_client("deezer", config)
        mock_deezer.assert_called_once_with(config)


def test_nrd_release_client_legacy_spotify_api():
    config = MagicMock()
    with patch("clients.client_spotify.SpotifyClient") as mock_spotify:
        nrd_release_client("spotify", config)
        mock_spotify.assert_called_once_with(config, discography_source="api")


@pytest.mark.asyncio
async def test_spotify_client_scraper_get_artist_albums():
    from clients.client_spotify import SpotifyClient

    config = MagicMock()
    config.NEW_RELEASES_CACHE_DAYS = 14
    client = SpotifyClient(config, discography_source="scraper")
    client.cache_enabled = False

    mock_albums = {
        "success": True,
        "albums": [{"id": "a1", "name": "Album", "primary_artist_id": "art1"}],
    }
    with patch.object(client, "_run_scraper", new=AsyncMock(return_value=mock_albums)):
        result = await client.get_artist_albums("art1", fetch_all=True)
    assert result["success"] is True
    assert len(result["albums"]) == 1


@pytest.mark.asyncio
async def test_enrich_nrd_album_scraper_mode():
    from clients.client_spotify import SpotifyClient

    config = MagicMock()
    client = SpotifyClient(config, discography_source="scraper")
    disc_album = {"id": "a1", "name": "Disc", "primary_artist_id": "art1"}
    enriched = {"id": "a1", "name": "Full", "primary_artist_id": "art1", "spotify_url": "http://x"}
    with patch.object(
        client, "_run_scraper", new=AsyncMock(return_value={"success": True, "album": enriched})
    ):
        result = await client.enrich_nrd_album(disc_album)
    assert result["name"] == "Full"


@pytest.mark.asyncio
async def test_enrich_scraper_nrd_album_skips_deezer():
    from utils.nrd_release_source import enrich_scraper_nrd_album

    album = {"id": "1", "name": "A"}
    client = MagicMock()
    result = await enrich_scraper_nrd_album(client, album, "deezer")
    assert result is album
    client.enrich_nrd_album.assert_not_called()


def test_new_releases_discovery_source_accepts_spotify_scraper():
    from commands.new_releases_discovery import NewReleasesDiscoveryCommand

    cmd = NewReleasesDiscoveryCommand()
    cmd.config_json = {"new_releases_source": "spotify_scraper"}
    assert cmd._get_new_releases_source() == "spotify_scraper"
