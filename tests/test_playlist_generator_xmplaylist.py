"""Unit tests for commands/playlist_generator_xmplaylist.py (no I/O)."""

from commands.playlist_generator_xmplaylist import _build_playlist_title, _dedupe_tracks


def test_build_playlist_title_newest_plex():
    t = _build_playlist_title(
        {
            "station_display_name": "Octane",
            "station_deeplink": "octane",
            "playlist_kind": "newest",
            "target": "plex",
        }
    )
    assert "[Cmdarr]" in t
    assert "Octane" in t
    assert "Newest" in t
    assert "Plex" in t


def test_build_playlist_title_most_heard_jellyfin():
    t = _build_playlist_title(
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
