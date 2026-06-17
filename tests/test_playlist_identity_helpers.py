"""Tests for playlist identity helpers."""

from unittest.mock import MagicMock, patch

from commands.playlist_generator_helpers import (
    delete_playlist_on_target,
    persist_playlist_identity,
)


def test_persist_playlist_identity_writes_title_and_id():
    mock_cmd = MagicMock()
    mock_cmd.config_json = {}
    mock_session = MagicMock()
    mock_session.query.return_value.filter.return_value.first.return_value = mock_cmd

    mock_db = MagicMock()
    mock_db.get_config_session_sync.return_value = mock_session

    with patch(
        "database.database.get_database_manager",
        return_value=mock_db,
    ):
        persist_playlist_identity(
            "top_tracks_foo",
            "top_tracks_",
            "[Cmdarr] Artist Essentials: A · B",
            "plex-123",
            MagicMock(),
        )

    assert mock_cmd.config_json["last_playlist_title"] == "[Cmdarr] Artist Essentials: A · B"
    assert mock_cmd.config_json["last_playlist_id"] == "plex-123"
    mock_session.commit.assert_called_once()


def test_delete_playlist_on_target_prefers_id():
    client = MagicMock()
    client.get_playlist_by_id.return_value = {"ratingKey": "rk1"}
    delete_playlist_on_target(client, playlist_id="rk1", playlist_title="Old Title")
    client.delete_playlist.assert_called_once_with("rk1")
    client.find_playlist_by_name.assert_not_called()
