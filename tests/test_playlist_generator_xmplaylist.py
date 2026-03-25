"""Unit tests for commands/playlist_generator_xmplaylist.py (no I/O)."""

from unittest.mock import patch

from commands.playlist_generator_xmplaylist import (
    _build_playlist_title,
    _build_xmplaylist_display_name,
    _build_xmplaylist_sync_title,
    _dedupe_tracks,
)


def test_build_xmplaylist_display_name_newest_plex():
    t = _build_xmplaylist_display_name(
        {
            "station_display_name": "Octane",
            "station_deeplink": "octane",
            "playlist_kind": "newest",
            "target": "plex",
        }
    )
    assert t == "[Cmdarr] SXM - Octane - Newest → Plex"


def test_build_playlist_title_alias_matches_display():
    cfg = {
        "station_display_name": "Octane",
        "station_deeplink": "octane",
        "playlist_kind": "newest",
        "target": "plex",
    }
    assert _build_playlist_title(cfg) == _build_xmplaylist_display_name(cfg)


def test_build_xmplaylist_sync_title_never_includes_plex_user():
    t = _build_xmplaylist_sync_title(
        {
            "station_display_name": "Octane",
            "station_deeplink": "octane",
            "playlist_kind": "newest",
            "target": "plex",
            "plex_playlist_account_id": "999",
        }
    )
    assert t == "[Cmdarr] SXM - Octane - Newest → Plex"


def test_build_xmplaylist_display_name_multi_plex_bracket():
    cfg = {
        "station_display_name": "Octane",
        "station_deeplink": "octane",
        "playlist_kind": "newest",
        "target": "plex",
        "plex_account_ids": ["1", "2"],
    }
    fake_accounts = [{"id": "1", "name": "Alice"}, {"id": "2", "name": "Bob"}]
    with patch("commands.config_adapter.Config"), patch("clients.client_plex.PlexClient") as MockPlex:
        MockPlex.return_value.get_accounts.return_value = fake_accounts
        t = _build_xmplaylist_display_name(cfg)
    assert "[Alice, Bob]" in t
    assert _build_xmplaylist_sync_title(cfg) == "[Cmdarr] SXM - Octane - Newest → Plex"


def test_build_xmplaylist_display_name_most_heard_jellyfin():
    t = _build_xmplaylist_display_name(
        {
            "station_display_name": "The Pulse",
            "station_deeplink": "thepulse",
            "playlist_kind": "most_heard",
            "most_heard_days": 7,
            "target": "jellyfin",
        }
    )
    assert "Most Played (7d)" in t
    assert "Jellyfin" in t


def test_dedupe_tracks():
    rows = [
        {"artist": "A", "track": "T", "album": ""},
        {"artist": "A", "track": "T", "album": "x"},
        {"artist": "B", "track": "T2", "album": ""},
    ]
    out = _dedupe_tracks(rows)
    assert len(out) == 2
