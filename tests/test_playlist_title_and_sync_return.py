"""Tests for playlist title helpers and sync_playlist return contract."""

from unittest.mock import MagicMock, patch

from clients.client_plex import PlexClient
from commands.playlist_generator_helpers import (
    compute_setlistfm_playlist_title,
    compute_top_tracks_playlist_title,
    compute_top_tracks_playlist_title_from_config,
    ordered_library_validated_artist_names,
)

SYNC_PLAYLIST_KEYS = {
    "success",
    "playlist_id",
    "playlist_title",
    "action",
    "total_tracks",
    "found_tracks",
    "message",
}


def test_compute_top_tracks_playlist_title_uses_validated_names():
    config = {"use_custom_playlist_name": False}
    title = compute_top_tracks_playlist_title(["Radiohead", "Björk"], config)
    assert title == "[Cmdarr] Artist Essentials: Radiohead · Björk"


def test_compute_top_tracks_playlist_title_custom_name():
    config = {
        "use_custom_playlist_name": True,
        "custom_playlist_name": "My Mix",
    }
    title = compute_top_tracks_playlist_title(["Ignored"], config)
    assert title == "[Cmdarr] Artist Essentials: My Mix"


def test_ordered_library_validated_artist_names_falls_back_without_cache():
    names = ordered_library_validated_artist_names(["A", "B"], None)
    assert names == ["A", "B"]


def test_compute_top_tracks_playlist_title_from_config_with_cache():
    cached = {
        "artist_index": {
            "radiohead": ["1"],
            "bjork": ["2"],
        }
    }
    config = {
        "artists": ["Radiohead", "Not In Library", "Björk"],
        "target": "plex",
        "target_library_key": "1",
    }
    with patch(
        "commands.playlist_generator_helpers.get_library_cache_for_target_config",
        return_value=cached,
    ):
        title = compute_top_tracks_playlist_title_from_config(config)
    assert "Radiohead" in title
    assert "Björk" in title
    assert "Not In Library" not in title


def test_compute_setlistfm_playlist_title_with_display_names():
    config = {"use_custom_playlist_name": False}
    title = compute_setlistfm_playlist_title(
        config, artist_display_names=["Pearl Jam", "Soundgarden"]
    )
    assert title == "[Cmdarr] Setlist: Pearl Jam · Soundgarden"


def test_plex_sync_playlist_skipped_empty_return_shape():
    client = PlexClient(MagicMock())
    client.logger = MagicMock()
    result = client.sync_playlist("Test Playlist", [], summary="test", cleanup_empty=True)
    assert SYNC_PLAYLIST_KEYS.issubset(result.keys())
    assert result["playlist_id"] is None
    assert result["playlist_title"] == "Test Playlist"
