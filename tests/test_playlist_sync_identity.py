"""Playlist sync title, append mode, and stored playlist id."""

import asyncio
import logging

from commands.playlist_sync import PlaylistSyncCommand
from commands.playlist_sync_titles import (
    build_playlist_sync_title,
    is_append_sync_mode,
    prefix_for_source,
)


def test_prefix_empty_disables_and_custom_replaces_default():
    assert prefix_for_source("spotify", None) == "[Spotify]"
    assert prefix_for_source("deezer", "  ") == ""
    assert prefix_for_source("spotify", "[S]") == "[S]"
    assert build_playlist_sync_title("Nice Tunes", "[Spotify]") == "[Spotify] Nice Tunes"
    assert build_playlist_sync_title("Nice Tunes", "") == "Nice Tunes"


def test_append_aliases():
    assert is_append_sync_mode("append")
    assert is_append_sync_mode("additive")
    assert not is_append_sync_mode("full")
    assert not is_append_sync_mode(None)


class _Target:
    def __init__(self, playlist=None):
        self.playlist = playlist
        self.sync_calls = []
        self.added = []
        self.renames = []

    def get_playlist_by_id(self, playlist_id):
        if self.playlist and str(self.playlist.get("ratingKey")) == str(playlist_id):
            return self.playlist
        return None

    def find_playlist_by_name(self, _name):
        return None

    def update_playlist_metadata(self, _key, title=None, summary=None):
        self.renames.append(title)
        return True

    def get_playlist_track_rating_keys(self, _key):
        return ["already"]

    def search_for_track(self, *_args, **_kwargs):
        return "new-track"

    def add_tracks_to_playlist(self, _key, tracks):
        self.added.append(list(tracks))
        return True

    def sync_playlist(self, **kwargs):
        self.sync_calls.append(kwargs)
        return {"success": True, "playlist_id": "created", "action": "synced"}


def _command(target):
    cmd = PlaylistSyncCommand.__new__(PlaylistSyncCommand)
    cmd.logger = logging.getLogger("test.playlist_sync")
    cmd.config_json = {
        "command_name": "playlist_sync_00001",
        "source": "spotify",
        "last_playlist_id": "99",
        "last_playlist_title": "[Spotify] Mine",
    }
    cmd.library_cache_manager = None
    cmd.target_client = target
    cmd._persist_playlist_identity = lambda: None
    return cmd


def _tracks():
    return [{"artist": "Artist", "track": "Song"}]


def test_append_adds_tracks_and_restores_title_without_recreating():
    target = _Target({"ratingKey": "99", "title": "Nice Tunes"})
    cmd = _command(target)

    result = asyncio.run(
        cmd._sync_one(
            playlist_title="[Spotify] Mine",
            tracks=_tracks(),
            summary="Synced",
            cached_data=None,
            library_key=None,
            sync_mode="append",
        )
    )

    assert result["success"] is True
    assert result["added_tracks"] == 1
    assert target.sync_calls == []
    assert target.added == [["new-track"]]
    assert target.renames == ["[Spotify] Mine"]
    assert cmd.config_json["last_playlist_id"] == "99"


def test_full_sync_updates_the_stored_playlist():
    target = _Target({"ratingKey": "99", "title": "[Spotify] Mine"})
    cmd = _command(target)

    asyncio.run(
        cmd._sync_one(
            playlist_title="[Spotify] Mine",
            tracks=_tracks(),
            summary="Synced",
            cached_data=None,
            library_key=None,
            sync_mode="full",
        )
    )

    assert target.added == []
    assert target.sync_calls[0]["existing_playlist_id"] == "99"
    assert cmd.config_json["last_playlist_id"] == "created"


def test_append_creates_when_no_playlist_is_tracked():
    target = _Target(None)
    cmd = _command(target)
    cmd.config_json.pop("last_playlist_id")

    asyncio.run(
        cmd._sync_one(
            playlist_title="[Spotify] Mine",
            tracks=_tracks(),
            summary="Synced",
            cached_data=None,
            library_key=None,
            sync_mode="append",
        )
    )

    assert len(target.sync_calls) == 1
    assert target.sync_calls[0]["existing_playlist_id"] is None
    assert cmd.config_json["last_playlist_id"] == "created"
