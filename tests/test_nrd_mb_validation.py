"""Unit tests for NRD MusicBrainz continual validation helpers."""

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from database.config_models import (
    ConfigBase,
    DismissedArtistAlbum,
    NewReleaseIgnoredArtist,
    NewReleasePending,
)
from utils.nrd_mb_validation import (
    apply_mb_found,
    apply_mb_not_found,
    is_due_for_recheck,
    run_validation_batch,
    select_validation_candidates,
    validation_cutoff,
)


@pytest.fixture()
def session():
    from sqlalchemy.pool import StaticPool

    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    ConfigBase.metadata.create_all(engine)
    TestSession = sessionmaker(bind=engine)
    s = TestSession()
    try:
        yield s
    finally:
        s.close()
        engine.dispose()


def _pending(**kwargs) -> NewReleasePending:
    defaults = {
        "artist_mbid": "mbid-a",
        "artist_name": "Artist A",
        "album_title": "Album One",
        "release_date": "2026-01-01",
        "source": "scheduled",
        "status": "pending",
    }
    defaults.update(kwargs)
    return NewReleasePending(**defaults)


def test_is_due_for_recheck_null_or_stale():
    now = datetime(2026, 6, 1, tzinfo=UTC)
    cutoff = validation_cutoff(14, now)
    row = _pending()
    assert is_due_for_recheck(row, cutoff) is True
    row.last_mb_recheck_at = now - timedelta(days=15)
    assert is_due_for_recheck(row, cutoff) is True
    row.last_mb_recheck_at = now - timedelta(days=7)
    assert is_due_for_recheck(row, cutoff) is False


def test_is_due_for_recheck_requires_mbid_and_title():
    row = _pending(artist_mbid="", album_title="X")
    assert is_due_for_recheck(row, validation_cutoff(14)) is False


def test_select_validation_candidates_pending_before_dismissed(session):
    now = datetime(2026, 6, 1, tzinfo=UTC)
    for i in range(3):
        session.add(_pending(album_title=f"P{i}", status="pending"))
    for i in range(3):
        session.add(_pending(album_title=f"D{i}", status="dismissed"))
    session.commit()

    selected = select_validation_candidates(session, batch_size=4, interval_days=14, now=now)
    assert len(selected) == 4
    assert sum(1 for r in selected if r.status == "pending") == 3
    assert sum(1 for r in selected if r.status == "dismissed") == 1


def test_select_validation_candidates_respects_interval(session):
    now = datetime(2026, 6, 1, tzinfo=UTC)
    due = _pending(album_title="Due")
    recent = _pending(
        album_title="Recent",
        last_mb_recheck_at=now - timedelta(days=1),
    )
    session.add_all([due, recent])
    session.commit()

    selected = select_validation_candidates(session, batch_size=10, interval_days=14, now=now)
    assert [r.album_title for r in selected] == ["Due"]


def test_select_validation_candidates_skips_ignored_artists(session):
    session.add(NewReleaseIgnoredArtist(artist_mbid="mbid-a", artist_name="Artist A"))
    session.add(_pending())
    session.add(_pending(artist_mbid="mbid-b", album_title="Other"))
    session.commit()

    selected = select_validation_candidates(
        session, batch_size=10, interval_days=14, now=datetime(2026, 6, 1, tzinfo=UTC)
    )
    assert len(selected) == 1
    assert selected[0].artist_mbid == "mbid-b"


def test_apply_mb_found_deletes_pending_and_dismissed(session):
    row = _pending(status="dismissed")
    session.add(row)
    session.add(
        DismissedArtistAlbum(
            artist_mbid="mbid-a",
            artist_name="Artist A",
            album_title="Album One",
            release_date="2026-01-01",
        )
    )
    session.commit()
    row_id = row.id

    apply_mb_found(session, row)
    session.commit()

    assert session.query(NewReleasePending).filter(NewReleasePending.id == row_id).first() is None
    assert session.query(DismissedArtistAlbum).count() == 0


def test_apply_mb_not_found_sets_timestamp(session):
    row = _pending()
    session.add(row)
    session.commit()
    now = datetime(2026, 6, 1, 12, 0, tzinfo=UTC)

    apply_mb_not_found(session, row, now=now)
    session.commit()

    refreshed = session.query(NewReleasePending).filter(NewReleasePending.id == row.id).one()
    assert refreshed.last_mb_recheck_at is not None
    stored = refreshed.last_mb_recheck_at
    if stored.tzinfo is None:
        stored = stored.replace(tzinfo=UTC)
    assert stored == now


@pytest.mark.asyncio
async def test_run_validation_batch_found_and_not_found(session):
    found_row = _pending(album_title="In MB")
    missing_row = _pending(album_title="Missing")
    session.add_all([found_row, missing_row])
    session.commit()

    mb_client = MagicMock()
    mb_client.release_exists_by_artist_and_title = AsyncMock(
        side_effect=lambda mbid, title, cache_ttl_days=0: title == "In MB"
    )

    stats = await run_validation_batch(session, mb_client, batch_size=10, interval_days=14)
    session.commit()

    assert stats["validation_checked"] == 2
    assert stats["validation_removed"] == 1
    assert stats["validation_pending_checked"] == 2
    assert session.query(NewReleasePending).count() == 1
    remaining = session.query(NewReleasePending).one()
    assert remaining.album_title == "Missing"
    assert remaining.last_mb_recheck_at is not None


@pytest.mark.asyncio
async def test_run_validation_batch_stops_on_mb_error(session):
    session.add(_pending(album_title="One"))
    session.add(_pending(album_title="Two"))
    session.commit()

    mb_client = MagicMock()
    mb_client.release_exists_by_artist_and_title = AsyncMock(side_effect=RuntimeError("rate limit"))

    stats = await run_validation_batch(session, mb_client, batch_size=10, interval_days=14)
    assert stats["validation_checked"] == 0


def test_new_release_pending_last_mb_recheck_migration_registered():
    from database.version_migrations import create_version_migration_runner

    runner = create_version_migration_runner()
    names = [m.name for m in runner.migrations]
    assert "new_release_pending_last_mb_recheck_at" in names


def test_new_release_pending_last_mb_recheck_migration_applies(tmp_path):
    import sqlite3

    from database.version_migrations import create_version_migration_runner

    db_path = tmp_path / "cmdarr_config.db"
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE new_release_pending (
            id INTEGER PRIMARY KEY,
            artist_mbid VARCHAR(100) NOT NULL,
            artist_name VARCHAR(500) NOT NULL,
            album_title VARCHAR(500) NOT NULL,
            source VARCHAR(50) NOT NULL DEFAULT 'scheduled',
            status VARCHAR(50) NOT NULL DEFAULT 'pending'
        )
    """)
    conn.commit()
    conn.close()

    runner = create_version_migration_runner()
    migration = next(
        m for m in runner.migrations if m.name == "new_release_pending_last_mb_recheck_at"
    )
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    assert migration.apply(cursor)
    conn.commit()
    cursor.execute("PRAGMA table_info(new_release_pending)")
    cols = [row[1] for row in cursor.fetchall()]
    assert "last_mb_recheck_at" in cols
    conn.close()
