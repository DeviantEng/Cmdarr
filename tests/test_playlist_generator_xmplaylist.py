"""Unit tests for commands/playlist_generator_xmplaylist.py (no I/O)."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from commands.playlist_generator_xmplaylist import (
    PlaylistGeneratorXmplaylistCommand,
    _build_playlist_title,
    _build_xmplaylist_display_name,
    _build_xmplaylist_sync_title,
    _dedupe_tracks,
)
from utils.logger import setup_application_logging


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


def test_build_xmplaylist_sync_title_no_target_suffix():
    """Plex/Jellyfin playlist name must not include Cmdarr display-only '→ Plex/Jellyfin'."""
    plex_cfg = {
        "station_display_name": "Octane",
        "station_deeplink": "octane",
        "playlist_kind": "newest",
        "target": "plex",
    }
    assert _build_xmplaylist_sync_title(plex_cfg) == "[Cmdarr] SXM - Octane - Newest"
    jf_cfg = {
        **plex_cfg,
        "playlist_kind": "most_heard",
        "most_heard_days": 60,
        "target": "jellyfin",
    }
    assert _build_xmplaylist_sync_title(jf_cfg) == "[Cmdarr] SXM - Octane - Most Played (60d)"
    assert "→" not in _build_xmplaylist_sync_title(jf_cfg)


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
    assert t == "[Cmdarr] SXM - Octane - Newest"


def test_build_xmplaylist_display_name_multi_plex_bracket():
    cfg = {
        "station_display_name": "Octane",
        "station_deeplink": "octane",
        "playlist_kind": "newest",
        "target": "plex",
        "plex_account_ids": ["1", "2"],
    }
    fake_accounts = [{"id": "1", "name": "Alice"}, {"id": "2", "name": "Bob"}]
    with (
        patch("commands.config_adapter.Config"),
        patch("clients.client_plex.PlexClient") as MockPlex,
    ):
        MockPlex.return_value.get_accounts.return_value = fake_accounts
        t = _build_xmplaylist_display_name(cfg)
    assert "[Alice, Bob]" in t
    assert _build_xmplaylist_sync_title(cfg) == "[Cmdarr] SXM - Octane - Newest"


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


@pytest.fixture
def xmplaylist_command(monkeypatch):
    setup_application_logging(
        MagicMock(LOG_LEVEL="ERROR", LOG_FILE="data/logs/cmdarr_test.log", LOG_RETENTION_DAYS=1)
    )

    mock_plex = MagicMock()
    mock_plex.get_resolved_library_key.return_value = "1"
    monkeypatch.setattr(
        "commands.playlist_generator_xmplaylist.PlexClient",
        lambda *args, **kwargs: mock_plex,
    )
    monkeypatch.setattr(
        "commands.playlist_generator_xmplaylist.get_library_cache_manager",
        lambda config: None,
    )

    class DummyCfg:
        MUSICBRAINZ_ENABLED = False

        def get(self, key, default=None):
            return default

    cmd = PlaylistGeneratorXmplaylistCommand(DummyCfg())
    cmd.config_json = {
        "station_deeplink": "octane",
        "playlist_kind": "newest",
        "target": "plex",
    }
    cmd.plex_client = mock_plex
    return cmd


@pytest.mark.asyncio
async def test_execute_fails_when_xmplaylist_fetch_blocked(xmplaylist_command):
    mock_xm = MagicMock()
    mock_xm.fetch_tracks_newest = AsyncMock(return_value=[])
    mock_xm.fetch_failed = True
    mock_xm.fetch_error_summary.return_value = "xmplaylist API blocked by Cloudflare (HTTP 403)"

    class XmCtx:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return mock_xm

        async def __aexit__(self, *args):
            return None

    with patch("commands.playlist_generator_xmplaylist.XmplaylistClient", XmCtx):
        result = await xmplaylist_command.execute()

    assert result is False
    assert "Cloudflare" in xmplaylist_command.last_run_stats.get("error", "")
    assert xmplaylist_command.last_run_stats.get("source_tracks") == 0


@pytest.mark.asyncio
async def test_execute_succeeds_when_xmplaylist_returns_empty_without_error(xmplaylist_command):
    mock_xm = MagicMock()
    mock_xm.fetch_tracks_newest = AsyncMock(return_value=[])
    mock_xm.fetch_failed = False
    mock_xm.fetch_error_summary.return_value = ""

    class XmCtx:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return mock_xm

        async def __aexit__(self, *args):
            return None

    with patch("commands.playlist_generator_xmplaylist.XmplaylistClient", XmCtx):
        result = await xmplaylist_command.execute()

    assert result is True
    assert "error" not in xmplaylist_command.last_run_stats
