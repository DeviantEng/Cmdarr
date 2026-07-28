"""Unit tests for Lidarr maintenance helpers, commands, and stats helpers."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.api.lidarr_maintenance import _command_rollups, _serialize_ignore
from commands.lidarr_update_all import LidarrUpdateAllCommand
from commands.lidarr_wanted_search import LidarrWantedSearchCommand
from database.config_models import CommandConfig, ConfigBase, LidarrWantedSearchIgnore
from services.command_executor import CommandExecutor
from utils.lidarr_maintenance import (
    album_matches_types,
    extract_album_ids_from_history,
    extract_album_ids_from_queue,
    map_lidarr_album_type,
    normalize_album_types,
    normalize_wanted_record,
    resolve_sort,
)


@pytest.fixture()
def session():
    engine = create_engine("sqlite://")
    ConfigBase.metadata.create_all(engine)
    TestSession = sessionmaker(bind=engine)
    s = TestSession()
    try:
        yield s
    finally:
        s.close()
        engine.dispose()


def _wanted_record(
    album_id: int,
    *,
    title: str = "Album",
    album_type: str = "Album",
    artist: str = "Artist",
) -> dict:
    return {
        "id": album_id,
        "title": title,
        "albumType": album_type,
        "foreignAlbumId": f"mbid-{album_id}",
        "releaseDate": "2020-01-01",
        "artistId": 1,
        "artist": {"artistName": artist, "foreignArtistId": "mbid-a"},
    }


# --- helpers -----------------------------------------------------------------


def test_normalize_album_types_defaults_and_filters():
    assert normalize_album_types(None) == {"album"}
    assert normalize_album_types("") == {"album"}
    assert normalize_album_types("album,ep,bogus") == {"album", "ep"}
    assert normalize_album_types(["Single", "OTHER"]) == {"single", "other"}


def test_map_lidarr_album_type():
    assert map_lidarr_album_type("Album") == "album"
    assert map_lidarr_album_type("EP") == "ep"
    assert map_lidarr_album_type("Single") == "single"
    assert map_lidarr_album_type("Broadcast") == "other"
    assert map_lidarr_album_type(None) == "other"


def test_album_matches_types():
    assert album_matches_types("Album", {"album"})
    assert not album_matches_types("EP", {"album"})
    assert album_matches_types("Remix", {"other"})


def test_resolve_sort():
    assert resolve_sort("oldest_release_date") == ("releaseDate", "ascending")
    assert resolve_sort("newest_release_date") == ("releaseDate", "descending")
    assert resolve_sort("artist_name_asc") == ("artist.sortName", "ascending")
    assert resolve_sort("album_title_asc") == ("title", "ascending")
    assert resolve_sort("unknown") == ("releaseDate", "ascending")


def test_extract_album_ids_from_queue_and_history():
    queue = [{"albumId": 1}, {"album": {"id": 2}}, {"albumId": "3"}, {}]
    assert extract_album_ids_from_queue(queue) == {1, 2, 3}
    history = [{"albumId": 9}, {"album": {"id": 10}}]
    assert extract_album_ids_from_history(history) == {9, 10}


def test_normalize_wanted_record():
    out = normalize_wanted_record(_wanted_record(42, title="Test Album", album_type="EP"))
    assert out["lidarr_album_id"] == 42
    assert out["album_type"] == "ep"
    assert out["artist_name"] == "Artist"
    assert out["album_title"] == "Test Album"


# --- Update All command ------------------------------------------------------


@pytest.mark.asyncio
async def test_update_all_not_configured():
    cmd = LidarrUpdateAllCommand(config=MagicMock())
    cmd.config_adapter = MagicMock(LIDARR_API_KEY="", LIDARR_URL="")
    assert await cmd.execute() is False
    assert "not configured" in (cmd.last_run_stats.get("error") or "")


@pytest.mark.asyncio
async def test_update_all_queues_refresh_artist():
    cmd = LidarrUpdateAllCommand(config=MagicMock())
    cmd.config_adapter = MagicMock(LIDARR_API_KEY="key", LIDARR_URL="http://lidarr")
    client = MagicMock()
    client.post_command = AsyncMock(return_value={"id": 9, "status": "started"})
    client.session = None

    with patch("commands.lidarr_update_all.LidarrClient", return_value=client):
        ok = await cmd.execute()

    assert ok is True
    client.post_command.assert_awaited_once_with("RefreshArtist")
    assert cmd.last_run_stats["lidarr_command_id"] == 9
    assert cmd.last_run_stats["lidarr_status"] == "started"
    assert "waited_for_completion" not in cmd.last_run_stats


@pytest.mark.asyncio
async def test_update_all_failed_status():
    cmd = LidarrUpdateAllCommand(config=MagicMock())
    cmd.config_adapter = MagicMock(LIDARR_API_KEY="key", LIDARR_URL="http://lidarr")
    client = MagicMock()
    client.post_command = AsyncMock(return_value={"id": 1, "status": "failed"})
    client.session = None

    with patch("commands.lidarr_update_all.LidarrClient", return_value=client):
        ok = await cmd.execute()

    assert ok is False
    assert "failed" in (cmd.last_run_stats.get("error") or "").lower()


@pytest.mark.asyncio
async def test_update_all_empty_response():
    cmd = LidarrUpdateAllCommand(config=MagicMock())
    cmd.config_adapter = MagicMock(LIDARR_API_KEY="key", LIDARR_URL="http://lidarr")
    client = MagicMock()
    client.post_command = AsyncMock(return_value=None)
    client.session = None

    with patch("commands.lidarr_update_all.LidarrClient", return_value=client):
        assert await cmd.execute() is False


# --- Wanted Search helpers / selection ---------------------------------------


def test_purge_and_active_ignores(session):
    cmd = LidarrWantedSearchCommand(config=MagicMock())
    now = datetime(2026, 7, 1, tzinfo=UTC)
    session.add(
        LidarrWantedSearchIgnore(
            lidarr_album_id=1,
            album_title="Expired",
            ignored_until=now - timedelta(days=1),
            reason="no_release_found",
        )
    )
    session.add(
        LidarrWantedSearchIgnore(
            lidarr_album_id=2,
            album_title="Active",
            ignored_until=now + timedelta(days=7),
            reason="no_release_found",
        )
    )
    session.commit()

    purged = cmd._purge_expired_ignores(session, now)
    session.commit()
    assert purged == 1
    assert cmd._active_ignored_album_ids(session, now) == {2}


def test_bump_lifetime_counters(session):
    cmd = LidarrWantedSearchCommand(config=MagicMock())
    row = CommandConfig(
        command_name="lidarr_wanted_search_00001",
        display_name="Wanted Search",
        description="test",
        enabled=True,
        config_json={"lifetime_searched": 5, "lifetime_downloads_found": 1, "lifetime_ignored": 2},
        command_type="lidarr_maintenance",
    )
    session.add(row)
    session.commit()

    cmd._bump_lifetime_counters(
        session, "lidarr_wanted_search_00001", searched=3, found=1, ignored=2
    )
    session.commit()
    session.refresh(row)
    assert row.config_json["lifetime_searched"] == 8
    assert row.config_json["lifetime_downloads_found"] == 2
    assert row.config_json["lifetime_ignored"] == 4


@pytest.mark.asyncio
async def test_select_wanted_albums_filters_types_and_ignores():
    cmd = LidarrWantedSearchCommand(config=MagicMock())
    client = MagicMock()
    client.get_wanted_missing = AsyncMock(
        return_value={
            "page": 1,
            "pageSize": 50,
            "totalRecords": 3,
            "records": [
                _wanted_record(1, title="A", album_type="Album"),
                _wanted_record(2, title="B", album_type="EP"),
                _wanted_record(3, title="C", album_type="Album"),
            ],
        }
    )

    selected = await cmd._select_wanted_albums(
        client,
        top_x=10,
        album_types={"album"},
        sort_key="releaseDate",
        sort_direction="ascending",
        ignored_ids={1},
    )
    assert [a["lidarr_album_id"] for a in selected] == [3]
    assert selected[0]["album_title"] == "C"


@pytest.mark.asyncio
async def test_select_wanted_albums_respects_top_x_and_pages():
    cmd = LidarrWantedSearchCommand(config=MagicMock())
    client = MagicMock()

    async def _pages(**kwargs):
        page = kwargs["page"]
        if page == 1:
            return {
                "totalRecords": 3,
                "records": [
                    _wanted_record(1, album_type="Album"),
                    _wanted_record(2, album_type="Album"),
                ],
            }
        return {
            "totalRecords": 3,
            "records": [_wanted_record(3, album_type="Album")],
        }

    client.get_wanted_missing = AsyncMock(side_effect=_pages)
    selected = await cmd._select_wanted_albums(
        client,
        top_x=2,
        album_types={"album"},
        sort_key="releaseDate",
        sort_direction="ascending",
        ignored_ids=set(),
    )
    assert [a["lidarr_album_id"] for a in selected] == [1, 2]
    assert client.get_wanted_missing.await_count == 1


@pytest.mark.asyncio
async def test_wanted_search_not_configured():
    cmd = LidarrWantedSearchCommand(config=MagicMock())
    cmd.config_adapter = MagicMock(LIDARR_API_KEY="", LIDARR_URL="")
    assert await cmd.execute() is False


@pytest.mark.asyncio
async def test_wanted_search_ignores_empty_and_keeps_queued(session):
    cmd = LidarrWantedSearchCommand(config=MagicMock())
    cmd.config_adapter = MagicMock(LIDARR_API_KEY="key", LIDARR_URL="http://lidarr")
    cmd.config_json = {
        "command_name": "lidarr_wanted_search_00001",
        "top_x": 5,
        "ignore_days": 14,
        "settle_seconds": 0,
        "album_types": "album",
        "sort_by": "oldest_release_date",
    }
    session.add(
        CommandConfig(
            command_name="lidarr_wanted_search_00001",
            display_name="Wanted Search",
            description="test",
            enabled=True,
            config_json={
                "lifetime_searched": 0,
                "lifetime_downloads_found": 0,
                "lifetime_ignored": 0,
            },
            command_type="lidarr_maintenance",
        )
    )
    session.commit()

    client = MagicMock()
    client.post_command = AsyncMock(return_value={"id": 50, "status": "completed"})
    client.wait_for_command = AsyncMock(return_value={"id": 50, "status": "completed"})
    client.get_queue = AsyncMock(return_value=[{"albumId": 10}])
    client.get_history_for_albums = AsyncMock(return_value=[])
    client.session = None
    client.get_wanted_missing = AsyncMock(
        return_value={
            "totalRecords": 2,
            "records": [
                _wanted_record(10, title="Found"),
                _wanted_record(11, title="Missing"),
            ],
        }
    )

    db_manager = MagicMock()
    db_manager.get_config_session_sync.return_value = session

    with (
        patch("commands.lidarr_wanted_search.LidarrClient", return_value=client),
        patch("commands.lidarr_wanted_search.get_database_manager", return_value=db_manager),
        patch("commands.lidarr_wanted_search.asyncio.sleep", new_callable=AsyncMock),
    ):
        # Prevent the command from closing the shared test session
        session.close = MagicMock()
        ok = await cmd.execute()

    assert ok is True
    assert cmd.last_run_stats["albums_searched"] == 2
    assert cmd.last_run_stats["downloads_found"] == 1
    assert cmd.last_run_stats["grabbed_cooled"] == 1
    assert cmd.last_run_stats["ignored_added"] == 1
    ignored = {row.lidarr_album_id: row for row in session.query(LidarrWantedSearchIgnore).all()}
    assert set(ignored) == {10, 11}
    assert ignored[10].reason == "grabbed"
    assert ignored[11].reason == "no_release_found"

    row = (
        session.query(CommandConfig)
        .filter(CommandConfig.command_name == "lidarr_wanted_search_00001")
        .one()
    )
    assert row.config_json["lifetime_searched"] == 2
    assert row.config_json["lifetime_downloads_found"] == 1
    assert row.config_json["lifetime_ignored"] == 1


@pytest.mark.asyncio
async def test_wanted_search_skips_grabbed_cooldown_on_next_run(session):
    """Albums cooled after a grab must not be re-searched while ignore is active."""
    now = datetime.now(UTC)
    session.add(
        LidarrWantedSearchIgnore(
            lidarr_album_id=10,
            artist_name="Artist",
            album_title="Found",
            album_type="album",
            ignored_at=now,
            ignored_until=now + timedelta(days=14),
            reason="grabbed",
            command_name="lidarr_wanted_search_00001",
            search_count=1,
        )
    )
    session.add(
        CommandConfig(
            command_name="lidarr_wanted_search_00001",
            display_name="Wanted Search",
            description="test",
            enabled=True,
            config_json={
                "lifetime_searched": 2,
                "lifetime_downloads_found": 1,
                "lifetime_ignored": 1,
            },
            command_type="lidarr_maintenance",
        )
    )
    session.commit()

    cmd = LidarrWantedSearchCommand(config=MagicMock())
    cmd.config_adapter = MagicMock(LIDARR_API_KEY="key", LIDARR_URL="http://lidarr")
    cmd.config_json = {
        "command_name": "lidarr_wanted_search_00001",
        "top_x": 5,
        "ignore_days": 14,
        "settle_seconds": 0,
        "album_types": "album",
        "sort_by": "oldest_release_date",
    }

    client = MagicMock()
    client.post_command = AsyncMock(return_value={"id": 51, "status": "completed"})
    client.wait_for_command = AsyncMock(return_value={"id": 51, "status": "completed"})
    client.get_queue = AsyncMock(return_value=[])
    client.get_history_for_albums = AsyncMock(return_value=[])
    client.session = None
    client.get_wanted_missing = AsyncMock(
        return_value={
            "totalRecords": 2,
            "records": [
                _wanted_record(10, title="Found"),
                _wanted_record(12, title="Next"),
            ],
        }
    )

    db_manager = MagicMock()
    db_manager.get_config_session_sync.return_value = session

    with (
        patch("commands.lidarr_wanted_search.LidarrClient", return_value=client),
        patch("commands.lidarr_wanted_search.get_database_manager", return_value=db_manager),
        patch("commands.lidarr_wanted_search.asyncio.sleep", new_callable=AsyncMock),
    ):
        session.close = MagicMock()
        ok = await cmd.execute()

    assert ok is True
    client.post_command.assert_awaited_once_with("AlbumSearch", albumIds=[12])
    assert cmd.last_run_stats["albums_searched"] == 1
    assert (
        session.query(LidarrWantedSearchIgnore)
        .filter(LidarrWantedSearchIgnore.lidarr_album_id == 10)
        .one()
        .reason
        == "grabbed"
    )
    cooled_next = (
        session.query(LidarrWantedSearchIgnore)
        .filter(LidarrWantedSearchIgnore.lidarr_album_id == 12)
        .one()
    )
    assert cooled_next.reason == "no_release_found"


@pytest.mark.asyncio
async def test_wanted_search_no_matches_still_succeeds(session):
    cmd = LidarrWantedSearchCommand(config=MagicMock())
    cmd.config_adapter = MagicMock(LIDARR_API_KEY="key", LIDARR_URL="http://lidarr")
    cmd.config_json = {
        "command_name": "lidarr_wanted_search_00002",
        "top_x": 5,
        "settle_seconds": 0,
        "album_types": "album",
    }
    session.add(
        CommandConfig(
            command_name="lidarr_wanted_search_00002",
            display_name="Wanted Search",
            description="test",
            enabled=True,
            config_json={},
            command_type="lidarr_maintenance",
        )
    )
    session.commit()

    client = MagicMock()
    client.get_wanted_missing = AsyncMock(return_value={"totalRecords": 0, "records": []})
    client.session = None
    db_manager = MagicMock()
    db_manager.get_config_session_sync.return_value = session

    with (
        patch("commands.lidarr_wanted_search.LidarrClient", return_value=client),
        patch("commands.lidarr_wanted_search.get_database_manager", return_value=db_manager),
    ):
        session.close = MagicMock()
        ok = await cmd.execute()

    assert ok is True
    assert cmd.last_run_stats["albums_searched"] == 0
    assert "No matching" in (cmd.last_run_stats.get("message") or "")


# --- Executor summaries / API helpers ----------------------------------------


def test_update_all_summary():
    summary = CommandExecutor()._build_lidarr_update_all_summary(
        {"lidarr_status": "started", "lidarr_command_id": 42}, 1.5
    )
    assert "Update All completed in 1.5s" in summary
    assert "started" in summary
    assert "42" in summary


def test_wanted_search_summary_with_samples():
    summary = CommandExecutor()._build_lidarr_wanted_search_summary(
        {
            "albums_searched": 3,
            "downloads_found": 1,
            "ignored_added": 2,
            "active_ignores": 5,
            "found_sample": ["A – One"],
            "ignored_sample": ["B – Two", "C – Three"],
        },
        8.0,
    )
    assert "searched 3" in summary
    assert "downloads 1" in summary
    assert "ignored 2" in summary
    assert "A – One" in summary
    assert "B – Two" in summary
    assert "Downloads (cooled)" in summary
    assert "Ignored (no release)" in summary


def test_serialize_ignore_and_rollups(session):
    now = datetime(2026, 7, 1, tzinfo=UTC)
    row = LidarrWantedSearchIgnore(
        lidarr_album_id=99,
        foreign_album_id="mbid-99",
        artist_name="Artist",
        album_title="Title",
        album_type="album",
        release_date="2024-01-01",
        ignored_at=now,
        ignored_until=now + timedelta(days=14),
        reason="no_release_found",
        command_name="lidarr_wanted_search_00001",
        search_count=2,
    )
    session.add(row)
    session.add(
        CommandConfig(
            command_name="lidarr_wanted_search_00001",
            display_name="Wanted Search",
            description="test",
            enabled=True,
            total_execution_count=4,
            total_success_count=3,
            total_failure_count=1,
            config_json={
                "top_x": 10,
                "lifetime_searched": 20,
                "lifetime_downloads_found": 5,
                "lifetime_ignored": 12,
            },
            command_type="lidarr_maintenance",
        )
    )
    session.commit()

    serialized = _serialize_ignore(row)
    assert serialized["lidarr_album_id"] == 99
    assert serialized["search_count"] == 2
    assert serialized["ignored_until"] is not None

    rollups = _command_rollups(session, "lidarr_wanted_search")
    assert rollups["command_count"] == 1
    assert rollups["total_execution_count"] == 4
    assert rollups["lifetime_searched"] == 20
    assert rollups["lifetime_downloads_found"] == 5
    assert rollups["lifetime_ignored"] == 12
    assert rollups["commands"][0]["config_json"]["top_x"] == 10
