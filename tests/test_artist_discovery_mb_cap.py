"""Tests that artist discovery caps MusicBrainz lookups before querying."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from commands.playlist_sync import PlaylistSyncCommand
from utils.discovery import DiscoveryUtils


def _make_utils(musicbrainz=None):
    config = MagicMock()
    config.MUSICBRAINZ_ENABLED = True
    return DiscoveryUtils(config=config, lidarr_client=MagicMock(), musicbrainz_client=musicbrainz)


@pytest.mark.asyncio
async def test_process_artists_through_musicbrainz_respects_max_lookups():
    musicbrainz = MagicMock()
    musicbrainz.fuzzy_search_artist = AsyncMock(
        side_effect=lambda name: {
            "mbid": f"mbid-{name}",
            "name": name,
            "similarity_score": 1.0,
        }
    )
    utils = _make_utils(musicbrainz)

    artists = [{"name": f"Artist {i}"} for i in range(10)]
    recovered = await utils.process_artists_through_musicbrainz(
        artists,
        existing_mbids=set(),
        existing_names=set(),
        excluded_mbids=set(),
        source_name="test",
        max_lookups=2,
    )

    assert musicbrainz.fuzzy_search_artist.await_count == 2
    assert len(recovered) == 2


@pytest.mark.asyncio
async def test_process_artists_skips_lidarr_names_before_mb_lookup():
    musicbrainz = MagicMock()
    musicbrainz.fuzzy_search_artist = AsyncMock(
        side_effect=lambda name: {
            "mbid": f"mbid-{name}",
            "name": name,
            "similarity_score": 1.0,
        }
    )
    utils = _make_utils(musicbrainz)

    artists = [{"name": "Known Artist"}, {"name": "New Artist"}]
    recovered = await utils.process_artists_through_musicbrainz(
        artists,
        existing_mbids=set(),
        existing_names={"known artist"},
        excluded_mbids=set(),
        source_name="test",
        max_lookups=2,
    )

    assert musicbrainz.fuzzy_search_artist.await_count == 1
    musicbrainz.fuzzy_search_artist.assert_awaited_once_with("New Artist")
    assert len(recovered) == 1
    assert recovered[0]["ArtistName"] == "New Artist"


@pytest.mark.asyncio
async def test_discover_and_add_artists_caps_mb_lookups_before_query():
    cmd = PlaylistSyncCommand(config=MagicMock())
    cmd.config.MUSICBRAINZ_ENABLED = True
    cmd.config_json = {
        "enable_artist_discovery": True,
        "artist_discovery_max_per_run": 2,
        "is_first_run": False,
        "playlist_name": "Test Playlist",
    }
    cmd.logger = MagicMock()

    mb_client = MagicMock()
    mb_client.fuzzy_search_artist = AsyncMock(
        side_effect=lambda name: {"mbid": f"mbid-{name}", "name": name}
    )
    mb_client.close = AsyncMock()

    discovery_utils = MagicMock()
    discovery_utils.get_lidarr_context = AsyncMock(return_value=(set(), set(), set()))
    discovery_utils.create_artist_entry = lambda mbid, name, source, **kwargs: {
        "MusicBrainzId": mbid,
        "ArtistName": name,
        "source": source,
    }

    tracks = [{"artist": f"Artist {i}", "track": f"Song {i}"} for i in range(20)]

    with (
        patch("clients.client_lidarr.LidarrClient"),
        patch("clients.client_musicbrainz.MusicBrainzClient", return_value=mb_client),
        patch("utils.discovery.DiscoveryUtils", return_value=discovery_utils),
        patch.object(cmd, "_save_discovered_artists", new_callable=AsyncMock) as save_mock,
    ):
        stats = await cmd._discover_and_add_artists(tracks, None)

    assert mb_client.fuzzy_search_artist.await_count == 2
    assert stats["artists_deferred"] == 18
    assert stats["artists_discovered"] == 2
    assert stats["artists_added"] == 2
    save_mock.assert_awaited_once()
    saved = save_mock.await_args.args[0]
    assert len(saved) == 2
