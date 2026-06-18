#!/usr/bin/env python3
"""
Schema migration system for Cmdarr.

Each migration is recorded in a ``schema_migration`` ledger by name. On startup
(and via the dev manual run), any registered migration not yet in the ledger is
applied in registration order. Version tags on migrations are metadata for release
notes only.

Early alpha (0.x): jumping between minor versions may still require a fresh install.
The ledger is the foundation for reliable upgrades once we reach 1.x.
"""

import sqlite3
import sys
from collections.abc import Callable
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from utils.logger import get_logger


# Lazy-load logger to avoid initialization issues
def get_migrations_logger():
    return get_logger("cmdarr.migrations")


def _table_exists(cursor: sqlite3.Cursor, name: str) -> bool:
    cursor.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name = ?",
        (name,),
    )
    return cursor.fetchone() is not None


def _column_exists(cursor: sqlite3.Cursor, table: str, column: str) -> bool:
    if not _table_exists(cursor, table):
        return False
    cursor.execute(f"PRAGMA table_info({table})")
    return column in [row[1] for row in cursor.fetchall()]


def _config_key_exists(cursor: sqlite3.Cursor, key: str) -> bool:
    if not _table_exists(cursor, "config_settings"):
        return False
    cursor.execute("SELECT 1 FROM config_settings WHERE key = ?", (key,))
    return cursor.fetchone() is not None


class VersionMigration:
    """Represents a registered schema migration."""

    def __init__(
        self,
        version: str,
        name: str,
        description: str,
        up_func: Callable,
        *,
        applied_check: Callable[[sqlite3.Cursor], bool] | None = None,
    ):
        self.version = version
        self.name = name
        self.description = description
        self.up_func = up_func
        self.applied_check = applied_check

    def apply(self, cursor: sqlite3.Cursor) -> bool:
        """Apply the migration"""
        try:
            get_migrations_logger().info(
                f"Applying migration {self.name} for version {self.version}"
            )
            self.up_func(cursor)
            get_migrations_logger().info(f"Migration {self.name} completed successfully")
            return True
        except Exception as e:
            get_migrations_logger().error(f"Migration {self.name} failed: {e}")
            return False


class VersionMigrationRunner:
    """Runs registered schema migrations tracked in a per-migration ledger."""

    def __init__(self, config_db_path: str = "data/cmdarr_config.db"):
        self.config_db_path = config_db_path
        self.migrations: list[VersionMigration] = []
        self.current_version = self._get_current_version()

    def _get_current_version(self) -> str:
        """Get the current application version"""
        try:
            from __version__ import __version__

            return __version__
        except ImportError:
            return "0.3.13"  # Fallback when __version__ missing

    def add_migration(self, migration: VersionMigration):
        """Add a migration to the runner"""
        self.migrations.append(migration)

    def _ensure_ledger_table(self, cursor: sqlite3.Cursor) -> None:
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS schema_migration (
                name TEXT PRIMARY KEY,
                version TEXT NOT NULL,
                description TEXT,
                applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS app_version (
                id INTEGER PRIMARY KEY,
                version TEXT UNIQUE NOT NULL,
                last_run TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

    def _get_applied_names(self, cursor: sqlite3.Cursor) -> set[str]:
        cursor.execute("SELECT name FROM schema_migration")
        return {row[0] for row in cursor.fetchall()}

    def _record_migration(self, cursor: sqlite3.Cursor, migration: VersionMigration) -> None:
        cursor.execute(
            """
            INSERT OR IGNORE INTO schema_migration (name, version, description)
            VALUES (?, ?, ?)
            """,
            (migration.name, migration.version, migration.description),
        )

    def _backfill_ledger_if_needed(self, cursor: sqlite3.Cursor) -> None:
        """Seed ledger rows for migrations already applied before the ledger existed."""
        if self._get_applied_names(cursor):
            return

        cursor.execute("SELECT version FROM app_version ORDER BY last_run DESC LIMIT 1")
        has_app_version = cursor.fetchone() is not None
        if not has_app_version and not _table_exists(cursor, "config_settings"):
            return

        log = get_migrations_logger()
        for migration in self.migrations:
            if migration.applied_check and migration.applied_check(cursor):
                self._record_migration(cursor, migration)
                log.info("Backfilled ledger for already-applied migration %s", migration.name)

    def get_last_run_version(self) -> str | None:
        """Legacy app_version row (informational)."""
        if not Path(self.config_db_path).exists():
            return None

        try:
            conn = sqlite3.connect(self.config_db_path)
            cursor = conn.cursor()
            self._ensure_ledger_table(cursor)
            cursor.execute("SELECT version FROM app_version ORDER BY last_run DESC LIMIT 1")
            result = cursor.fetchone()
            conn.close()
            return result[0] if result else None

        except Exception as e:
            get_migrations_logger().warning(f"Failed to get last run version: {e}")
            return None

    def update_last_run_version(self, version: str):
        """Update informational app_version after migrations run."""
        try:
            conn = sqlite3.connect(self.config_db_path)
            cursor = conn.cursor()
            self._ensure_ledger_table(cursor)
            cursor.execute(
                """
                INSERT OR REPLACE INTO app_version (id, version, last_run)
                VALUES (1, ?, CURRENT_TIMESTAMP)
                """,
                (version,),
            )
            conn.commit()
            conn.close()
            get_migrations_logger().info(f"Updated last run version to {version}")

        except Exception as e:
            get_migrations_logger().error(f"Failed to update last run version: {e}")

    def _applied_migrations(self, cursor: sqlite3.Cursor) -> list[dict]:
        cursor.execute(
            """
            SELECT name, version, description, applied_at
            FROM schema_migration
            ORDER BY applied_at, name
            """
        )
        return [
            {
                "name": row[0],
                "version": row[1],
                "description": row[2],
                "applied_at": row[3],
            }
            for row in cursor.fetchall()
        ]

    def _pending_migrations(self, applied_names: set[str]) -> list[VersionMigration]:
        return [m for m in self.migrations if m.name not in applied_names]

    def get_migration_status(self) -> dict:
        """Snapshot for status API / dev manual migration UI."""
        last_version = self.get_last_run_version()
        dev_manual_available = "-dev" in self.current_version

        if not Path(self.config_db_path).exists():
            pending = [
                {
                    "name": m.name,
                    "version": m.version,
                    "description": m.description,
                }
                for m in self.migrations
            ]
            return {
                "current_version": self.current_version,
                "last_run_version": last_version,
                "applied_migrations": [],
                "pending_migrations": pending,
                "dev_manual_available": dev_manual_available,
            }

        conn = sqlite3.connect(self.config_db_path)
        cursor = conn.cursor()
        self._ensure_ledger_table(cursor)
        applied_names = self._get_applied_names(cursor)
        applied = self._applied_migrations(cursor)
        pending = [
            {
                "name": m.name,
                "version": m.version,
                "description": m.description,
            }
            for m in self._pending_migrations(applied_names)
        ]
        conn.close()

        return {
            "current_version": self.current_version,
            "last_run_version": last_version,
            "applied_migrations": applied,
            "pending_migrations": pending,
            "dev_manual_available": dev_manual_available,
        }

    def run_migrations(self) -> dict:
        """Apply any registered migrations not yet recorded in the ledger."""
        current_version = self.current_version
        log = get_migrations_logger()

        if not Path(self.config_db_path).exists():
            log.info("Config database does not exist, skipping migrations")
            return {
                "ran": False,
                "reason": "no_database",
                "migrations_run": 0,
                "migration_names": [],
            }

        try:
            conn = sqlite3.connect(self.config_db_path)
            cursor = conn.cursor()
            self._ensure_ledger_table(cursor)
            self._backfill_ledger_if_needed(cursor)
            conn.commit()

            applied_names = self._get_applied_names(cursor)
            pending = self._pending_migrations(applied_names)
            if not pending:
                conn.close()
                log.info("No pending schema migrations")
                return {
                    "ran": False,
                    "reason": "none_pending",
                    "migrations_run": 0,
                    "migration_names": [],
                }

            log.info("Running %s pending schema migration(s)", len(pending))
            migrations_run = 0
            migration_names: list[str] = []
            for migration in pending:
                if migration.apply(cursor):
                    self._record_migration(cursor, migration)
                    migrations_run += 1
                    migration_names.append(migration.name)
                else:
                    log.error("Migration %s failed, stopping", migration.name)
                    conn.rollback()
                    conn.close()
                    return {
                        "ran": False,
                        "reason": "migration_failed",
                        "failed_migration": migration.name,
                        "migrations_run": migrations_run,
                        "migration_names": migration_names,
                    }

            conn.commit()
            conn.close()

            self.update_last_run_version(current_version)
            log.info(
                "Successfully ran %s schema migration(s) for version %s",
                migrations_run,
                current_version,
            )
            return {
                "ran": True,
                "reason": "pending_applied",
                "migrations_run": migrations_run,
                "migration_names": migration_names,
            }

        except Exception as e:
            log.error("Migration failed: %s", e)
            raise

    def run_migrations_if_needed(self):
        """Run pending migrations on startup."""
        self.run_migrations()

    def run_migrations_manual(self) -> dict:
        """Dev-only: apply pending migrations (same as startup)."""
        return self.run_migrations()


def create_version_migration_runner() -> VersionMigrationRunner:
    """Create a migration runner with version-based migrations"""
    from database.database import _get_data_dir

    config_db_path = str(Path(_get_data_dir()) / "cmdarr_config.db")
    runner = VersionMigrationRunner(config_db_path=config_db_path)

    def migrate_artist_events_naming(cursor):
        """Rename CONCERT_EVENTS_* config keys and concert_events_refresh command."""
        key_map = [
            ("CONCERT_EVENTS_BANDSINTOWN_ENABLED", "ARTIST_EVENTS_BANDSINTOWN_ENABLED"),
            ("CONCERT_EVENTS_BANDSINTOWN_APP_ID", "ARTIST_EVENTS_BANDSINTOWN_APP_ID"),
            ("CONCERT_EVENTS_SONGKICK_ENABLED", "ARTIST_EVENTS_SONGKICK_ENABLED"),
            ("CONCERT_EVENTS_SONGKICK_API_KEY", "ARTIST_EVENTS_SONGKICK_API_KEY"),
            ("CONCERT_EVENTS_TICKETMASTER_ENABLED", "ARTIST_EVENTS_TICKETMASTER_ENABLED"),
            ("CONCERT_EVENTS_TICKETMASTER_API_KEY", "ARTIST_EVENTS_TICKETMASTER_API_KEY"),
            ("CONCERT_EVENTS_USER_LAT", "ARTIST_EVENTS_USER_LAT"),
            ("CONCERT_EVENTS_USER_LON", "ARTIST_EVENTS_USER_LON"),
            ("CONCERT_EVENTS_USER_LABEL", "ARTIST_EVENTS_USER_LABEL"),
            ("CONCERT_EVENTS_RADIUS_MILES", "ARTIST_EVENTS_RADIUS_MILES"),
        ]
        for old_key, new_key in key_map:
            cursor.execute("SELECT 1 FROM config_settings WHERE key = ?", (new_key,))
            has_new = cursor.fetchone() is not None
            cursor.execute("SELECT 1 FROM config_settings WHERE key = ?", (old_key,))
            has_old = cursor.fetchone() is not None
            if has_new and has_old:
                cursor.execute("DELETE FROM config_settings WHERE key = ?", (old_key,))
            elif has_old:
                cursor.execute(
                    "UPDATE config_settings SET key = ?, category = ? WHERE key = ?",
                    (new_key, "artist_events", old_key),
                )

        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='command_configs'"
        )
        if cursor.fetchone():
            cursor.execute(
                """
                UPDATE command_configs
                SET command_name = 'artist_events_refresh',
                    display_name = 'Artist Events Refresh',
                    description = 'Fetch upcoming events for Lidarr artists (Ticketmaster Discovery)'
                WHERE command_name = 'concert_events_refresh'
                """
            )
        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='command_executions'"
        )
        if cursor.fetchone():
            cursor.execute(
                """
                UPDATE command_executions
                SET command_name = 'artist_events_refresh'
                WHERE command_name = 'concert_events_refresh'
                """
            )

    def migrate_concert_event_user_interested(cursor):
        """Add user_interested flag for Artist events page."""
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='concert_event'")
        if not cursor.fetchone():
            return
        cursor.execute("PRAGMA table_info(concert_event)")
        cols = [r[1] for r in cursor.fetchall()]
        if "user_interested" not in cols:
            cursor.execute(
                "ALTER TABLE concert_event ADD COLUMN user_interested BOOLEAN NOT NULL DEFAULT 0"
            )

    # v0.3.14: artist events (finder) — run in order when upgrading from ≤0.3.13
    runner.add_migration(
        VersionMigration(
            version="0.3.14",
            name="artist_events_naming",
            description="Rename concert event config keys to ARTIST_EVENTS_* and command to artist_events_refresh",
            up_func=migrate_artist_events_naming,
            applied_check=lambda c: _config_key_exists(c, "ARTIST_EVENTS_TICKETMASTER_ENABLED"),
        )
    )
    runner.add_migration(
        VersionMigration(
            version="0.3.14",
            name="concert_event_user_interested",
            description="Add user_interested to concert_event for Artist Events page",
            up_func=migrate_concert_event_user_interested,
            applied_check=lambda c: _column_exists(c, "concert_event", "user_interested"),
        )
    )

    def migrate_concert_event_dedupe_coalesce(cursor):
        """
        Recompute venue fingerprints using the current `utils.event_geo.venue_fingerprint`
        (name-first dedupe with normalized venue/city/region), merge duplicate
        concert_event rows that now share the same dedupe key — preserving per-source
        links, user-interested state, and per-event hides — then refresh dedupe_key for
        all remaining rows.
        """
        from collections import defaultdict

        from utils.event_geo import coerce_location_str, make_dedupe_key, venue_fingerprint

        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='concert_event'")
        if not cursor.fetchone():
            return

        cursor.execute(
            """
            SELECT id, artist_mbid, artist_name, venue_name, venue_city, venue_region,
                   venue_lat, venue_lon, local_date, user_interested
            FROM concert_event
            """
        )
        rows = cursor.fetchall()
        if not rows:
            return

        def compute_dedupe_key(
            artist_mbid: str,
            local_date: str,
            venue_name,
            venue_city,
            venue_region,
            venue_lat,
            venue_lon,
        ) -> str:
            v_name = coerce_location_str(venue_name)
            v_city = coerce_location_str(venue_city)
            v_region = coerce_location_str(venue_region)
            fp = venue_fingerprint(v_name, v_city, v_region, venue_lat, venue_lon)
            return make_dedupe_key(artist_mbid, local_date, fp)

        groups: dict[str, list[int]] = defaultdict(list)
        for row in rows:
            _id, artist_mbid, _an, vn, vc, vr, vlat, vlon, local_date, _ui = row
            dk = compute_dedupe_key(artist_mbid, local_date, vn, vc, vr, vlat, vlon)
            groups[dk].append(_id)

        for _dk, ids in groups.items():
            ids.sort()
            if len(ids) <= 1:
                continue
            winner = ids[0]
            for loser in ids[1:]:
                cursor.execute(
                    "SELECT id, provider, external_id FROM concert_event_source WHERE concert_event_id = ?",
                    (loser,),
                )
                for src_id, prov, ext in cursor.fetchall():
                    cursor.execute(
                        """
                        SELECT 1 FROM concert_event_source
                        WHERE concert_event_id = ?
                          AND provider = ?
                          AND IFNULL(external_id, '') = IFNULL(?, '')
                        """,
                        (winner, prov, ext),
                    )
                    if cursor.fetchone():
                        cursor.execute("DELETE FROM concert_event_source WHERE id = ?", (src_id,))
                    else:
                        cursor.execute(
                            "UPDATE concert_event_source SET concert_event_id = ? WHERE id = ?",
                            (winner, src_id),
                        )

                cursor.execute("SELECT user_interested FROM concert_event WHERE id = ?", (loser,))
                urow = cursor.fetchone()
                if urow and urow[0]:
                    cursor.execute(
                        "UPDATE concert_event SET user_interested = 1 WHERE id = ?", (winner,)
                    )

                cursor.execute(
                    "SELECT name FROM sqlite_master WHERE type='table' AND name='artist_concert_hidden_event'"
                )
                if cursor.fetchone():
                    cursor.execute(
                        "SELECT hidden_at FROM artist_concert_hidden_event WHERE event_id = ?",
                        (loser,),
                    )
                    hr = cursor.fetchone()
                    if hr:
                        cursor.execute(
                            """
                            INSERT OR IGNORE INTO artist_concert_hidden_event (event_id, hidden_at)
                            VALUES (?, ?)
                            """,
                            (winner, hr[0]),
                        )

                cursor.execute("DELETE FROM concert_event WHERE id = ?", (loser,))

        cursor.execute(
            """
            SELECT id, artist_mbid, venue_name, venue_city, venue_region,
                   venue_lat, venue_lon, local_date
            FROM concert_event
            """
        )
        for row in cursor.fetchall():
            eid, artist_mbid, vn, vc, vr, vlat, vlon, local_date = row
            new_dk = compute_dedupe_key(artist_mbid, local_date, vn, vc, vr, vlat, vlon)
            cursor.execute(
                "UPDATE concert_event SET dedupe_key = ? WHERE id = ?",
                (new_dk, eid),
            )

    def migrate_concert_event_festival_fields(cursor):
        """TM event display name, festival/tour classification, festival grouping key."""
        cursor.execute("PRAGMA table_info(concert_event)")
        cols = [r[1] for r in cursor.fetchall()]
        if "tm_event_name" not in cols:
            cursor.execute("ALTER TABLE concert_event ADD COLUMN tm_event_name VARCHAR(500)")
        if "event_kind" not in cols:
            cursor.execute(
                "ALTER TABLE concert_event ADD COLUMN event_kind VARCHAR(32) NOT NULL DEFAULT 'show'"
            )
        if "festival_key" not in cols:
            cursor.execute("ALTER TABLE concert_event ADD COLUMN festival_key VARCHAR(256)")
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS ix_concert_event_event_kind ON concert_event(event_kind)"
        )
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS ix_concert_event_festival_key ON concert_event(festival_key)"
        )

    runner.add_migration(
        VersionMigration(
            version="0.3.14",
            name="concert_event_dedupe_coalesce",
            description="Recompute venue fingerprints (name-first dedupe) and merge duplicate concert_event rows",
            up_func=migrate_concert_event_dedupe_coalesce,
            applied_check=lambda c: _column_exists(c, "concert_event", "event_kind"),
        )
    )
    runner.add_migration(
        VersionMigration(
            version="0.3.14",
            name="concert_event_festival_fields",
            description="Add tm_event_name, event_kind, festival_key for festival UX and TM ingest",
            up_func=migrate_concert_event_festival_fields,
            applied_check=lambda c: _column_exists(c, "concert_event", "event_kind"),
        )
    )

    def migrate_lidarr_artist_jambase_id(cursor):
        """Cache resolved JamBase artist IDs on Lidarr artist rows."""
        cursor.execute("PRAGMA table_info(lidarr_artist)")
        cols = [r[1] for r in cursor.fetchall()]
        if "jambase_artist_id" not in cols:
            cursor.execute("ALTER TABLE lidarr_artist ADD COLUMN jambase_artist_id VARCHAR(64)")

    runner.add_migration(
        VersionMigration(
            version="0.3.16",
            name="lidarr_artist_jambase_id",
            description="Add jambase_artist_id cache column on lidarr_artist",
            up_func=migrate_lidarr_artist_jambase_id,
            applied_check=lambda c: _column_exists(c, "lidarr_artist", "jambase_artist_id"),
        )
    )

    def migrate_lidarr_artist_deezer_id(cursor):
        """Cache Deezer artist IDs from Lidarr links for concert GraphQL lookups."""
        cursor.execute("PRAGMA table_info(lidarr_artist)")
        cols = [r[1] for r in cursor.fetchall()]
        if "deezer_artist_id" not in cols:
            cursor.execute("ALTER TABLE lidarr_artist ADD COLUMN deezer_artist_id VARCHAR(64)")

    runner.add_migration(
        VersionMigration(
            version="0.3.16",
            name="lidarr_artist_deezer_id",
            description="Add deezer_artist_id cache column on lidarr_artist",
            up_func=migrate_lidarr_artist_deezer_id,
            applied_check=lambda c: _column_exists(c, "lidarr_artist", "deezer_artist_id"),
        )
    )

    return runner


def run_version_migrations():
    """Run version-based migrations"""
    runner = create_version_migration_runner()
    runner.run_migrations_if_needed()


def get_migration_status() -> dict:
    runner = create_version_migration_runner()
    return runner.get_migration_status()


def run_version_migrations_manual() -> dict:
    """Apply pending migrations (dev builds expose this via the Status page)."""
    runner = create_version_migration_runner()
    return runner.run_migrations_manual()


if __name__ == "__main__":
    run_version_migrations()
