"""Unit tests for schema migration ledger runner."""

import sqlite3
from pathlib import Path

from database.version_migrations import VersionMigration, VersionMigrationRunner


def _make_db(path: Path) -> sqlite3.Cursor:
    conn = sqlite3.connect(path)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE config_settings (
            key TEXT PRIMARY KEY,
            value TEXT,
            category TEXT
        )
    """)
    cursor.execute("""
        INSERT INTO config_settings (key, value, category)
        VALUES ('ARTIST_EVENTS_TICKETMASTER_ENABLED', 'true', 'artist_events')
    """)
    conn.commit()
    return cursor


def test_ledger_table_created_on_status(tmp_path):
    db_path = tmp_path / "cmdarr_config.db"
    _make_db(db_path).connection.close()

    runner = VersionMigrationRunner(config_db_path=str(db_path))
    status = runner.get_migration_status()

    assert "applied_migrations" in status
    assert "pending_migrations" in status
    assert status["dev_manual_available"] is ("-dev" in runner.current_version)


def test_pending_migration_runs_and_records_ledger(tmp_path):
    db_path = tmp_path / "cmdarr_config.db"
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE lidarr_artist (
            id INTEGER PRIMARY KEY,
            name TEXT
        )
    """)
    conn.commit()
    conn.close()

    conn.close()

    def add_flag_column(cur):
        cur.execute("ALTER TABLE lidarr_artist ADD COLUMN test_flag INTEGER DEFAULT 0")

    runner = VersionMigrationRunner(config_db_path=str(db_path))
    runner.add_migration(
        VersionMigration(
            version="0.9.9",
            name="test_add_flag",
            description="Test migration",
            up_func=add_flag_column,
            applied_check=lambda c: False,
        )
    )

    result = runner.run_migrations()
    assert result["ran"] is True
    assert result["migrations_run"] == 1
    assert result["migration_names"] == ["test_add_flag"]

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM schema_migration")
    assert [row[0] for row in cursor.fetchall()] == ["test_add_flag"]
    cursor.execute("PRAGMA table_info(lidarr_artist)")
    cols = [row[1] for row in cursor.fetchall()]
    assert "test_flag" in cols
    conn.close()

    second = runner.run_migrations()
    assert second["ran"] is False
    assert second["reason"] == "none_pending"


def test_backfill_skips_already_applied_schema(tmp_path):
    db_path = tmp_path / "cmdarr_config.db"
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE lidarr_artist (
            id INTEGER PRIMARY KEY,
            deezer_artist_id VARCHAR(64)
        )
    """)
    cursor.execute("""
        CREATE TABLE app_version (
            id INTEGER PRIMARY KEY,
            version TEXT UNIQUE NOT NULL,
            last_run TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    cursor.execute("INSERT INTO app_version (id, version) VALUES (1, '0.3.16-dev')")
    conn.commit()
    conn.close()

    ran: list[str] = []

    def should_not_run(cur):
        ran.append("deezer")
        cur.execute("ALTER TABLE lidarr_artist ADD COLUMN deezer_artist_id VARCHAR(64)")

    runner = VersionMigrationRunner(config_db_path=str(db_path))
    runner.add_migration(
        VersionMigration(
            version="0.3.16",
            name="lidarr_artist_deezer_id",
            description="Add deezer_artist_id",
            up_func=should_not_run,
            applied_check=lambda c: (
                "deezer_artist_id"
                in [r[1] for r in c.execute("PRAGMA table_info(lidarr_artist)").fetchall()]
            ),
        )
    )

    result = runner.run_migrations()
    assert result["ran"] is False
    assert result["reason"] == "none_pending"
    assert ran == []

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM schema_migration")
    assert [row[0] for row in cursor.fetchall()] == ["lidarr_artist_deezer_id"]
    conn.close()


def test_migration_failure_stops_without_ledger_entry(tmp_path):
    db_path = tmp_path / "cmdarr_config.db"
    conn = sqlite3.connect(db_path)
    conn.commit()
    conn.close()

    def fail_migration(cur):
        raise RuntimeError("boom")

    runner = VersionMigrationRunner(config_db_path=str(db_path))
    runner.add_migration(
        VersionMigration(
            version="0.9.9",
            name="failing_migration",
            description="Fails on purpose",
            up_func=fail_migration,
        )
    )

    result = runner.run_migrations()
    assert result["ran"] is False
    assert result["reason"] == "migration_failed"
    assert result["failed_migration"] == "failing_migration"

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM schema_migration")
    assert cursor.fetchone()[0] == 0
    conn.close()


def test_create_runner_registers_all_migrations_with_checks():
    from database.version_migrations import create_version_migration_runner

    runner = create_version_migration_runner()
    names = [m.name for m in runner.migrations]
    assert "lidarr_artist_deezer_id" in names
    assert all(m.applied_check is not None for m in runner.migrations)
