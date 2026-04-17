#!/usr/bin/env python3
"""
Version-based migration system for Cmdarr

This system tracks the application version in the database and only runs migrations
when the version changes, avoiding unnecessary migration checks on every startup.
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


class VersionMigration:
    """Represents a migration tied to a specific version"""

    def __init__(self, version: str, name: str, description: str, up_func: Callable):
        self.version = version
        self.name = name
        self.description = description
        self.up_func = up_func

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
    """Handles version-based database migrations"""

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
            return "0.1.5"  # Fallback version

    def add_migration(self, migration: VersionMigration):
        """Add a migration to the runner"""
        self.migrations.append(migration)

    def get_last_run_version(self) -> str | None:
        """Get the last version that ran migrations"""
        if not Path(self.config_db_path).exists():
            return None

        try:
            conn = sqlite3.connect(self.config_db_path)
            cursor = conn.cursor()

            # Create version tracking table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS app_version (
                    id INTEGER PRIMARY KEY,
                    version TEXT UNIQUE NOT NULL,
                    last_run TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Get the latest version
            cursor.execute("SELECT version FROM app_version ORDER BY last_run DESC LIMIT 1")
            result = cursor.fetchone()

            conn.close()
            return result[0] if result else None

        except Exception as e:
            get_migrations_logger().warning(f"Failed to get last run version: {e}")
            return None

    def update_last_run_version(self, version: str):
        """Update the last run version in the database"""
        try:
            conn = sqlite3.connect(self.config_db_path)
            cursor = conn.cursor()

            # Insert or update the version
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

    def run_migrations_if_needed(self):
        """Run migrations only if the version has changed"""
        last_version = self.get_last_run_version()
        current_version = self.current_version

        get_migrations_logger().info(
            f"Current version: {current_version}, Last run version: {last_version}"
        )

        if last_version == current_version:
            get_migrations_logger().info("Version unchanged, skipping migrations")
            return

        if not Path(self.config_db_path).exists():
            get_migrations_logger().info("Config database does not exist, skipping migrations")
            return

        get_migrations_logger().info(
            f"Version changed from {last_version} to {current_version}, running migrations..."
        )

        try:
            conn = sqlite3.connect(self.config_db_path)
            cursor = conn.cursor()

            # Run migrations for the current version
            migrations_run = 0
            for migration in self.migrations:
                if migration.version == current_version:
                    if migration.apply(cursor):
                        migrations_run += 1
                    else:
                        get_migrations_logger().error(
                            f"Migration {migration.name} failed, stopping"
                        )
                        conn.rollback()
                        conn.close()
                        return

            conn.commit()
            conn.close()

            # Update the last run version
            self.update_last_run_version(current_version)

            get_migrations_logger().info(
                f"Successfully ran {migrations_run} migrations for version {current_version}"
            )

        except Exception as e:
            get_migrations_logger().error(f"Migration failed: {e}")
            raise


def create_version_migration_runner() -> VersionMigrationRunner:
    """Create a migration runner with version-based migrations"""
    from database.database import _get_data_dir

    config_db_path = str(Path(_get_data_dir()) / "cmdarr_config.db")
    runner = VersionMigrationRunner(config_db_path=config_db_path)

    # Migration for v0.1.5: Database split
    def migrate_database_split(cursor):
        """Migrate from single database to split databases"""
        get_migrations_logger().info("Running database split migration...")

        from database.database import _get_data_dir

        # Check if we're running on the old single database
        old_db_path = str(Path(_get_data_dir()) / "cmdarr.db")
        if not Path(old_db_path).exists():
            get_migrations_logger().info("Old database not found, skipping split migration")
            return

        # Import and run the simplified migration
        try:
            from database.migrate_split_simple import main as run_split_migration

            run_split_migration()
            get_migrations_logger().info("Database split migration completed")
        except Exception as e:
            get_migrations_logger().error(f"Database split migration failed: {e}")
            raise

    runner.add_migration(
        VersionMigration(
            version="0.1.5",
            name="database_split",
            description="Split single database into config and cache databases",
            up_func=migrate_database_split,
        )
    )

    def migrate_dismissed_artist_name(cursor):
        """Add artist_name to dismissed_artist_album for restore UI"""
        cursor.execute("PRAGMA table_info(dismissed_artist_album)")
        cols = [r[1] for r in cursor.fetchall()]
        if "artist_name" not in cols:
            cursor.execute("ALTER TABLE dismissed_artist_album ADD COLUMN artist_name VARCHAR(500)")

    runner.add_migration(
        VersionMigration(
            version="0.2.4",
            name="dismissed_artist_name",
            description="Add artist_name to dismissed_artist_album",
            up_func=migrate_dismissed_artist_name,
        )
    )

    def migrate_scheduler_cron(cursor):
        """Replace schedule_hours with schedule_cron for cron-only scheduler"""
        cursor.execute("PRAGMA table_info(command_configs)")
        cols = [r[1] for r in cursor.fetchall()]
        if "schedule_cron" not in cols:
            cursor.execute("ALTER TABLE command_configs ADD COLUMN schedule_cron VARCHAR(100)")
        if "schedule_hours" in cols:
            cursor.execute("ALTER TABLE command_configs DROP COLUMN schedule_hours")

    runner.add_migration(
        VersionMigration(
            version="0.3.2",
            name="scheduler_cron",
            description="Replace schedule_hours with schedule_cron for cron-only scheduler",
            up_func=migrate_scheduler_cron,
        )
    )

    def migrate_command_aggregate_stats(cursor):
        """Add aggregate execution stats to command_configs"""
        cursor.execute("PRAGMA table_info(command_configs)")
        cols = [r[1] for r in cursor.fetchall()]
        if "total_execution_count" not in cols:
            cursor.execute(
                "ALTER TABLE command_configs ADD COLUMN total_execution_count INTEGER NOT NULL DEFAULT 0"
            )
        if "total_success_count" not in cols:
            cursor.execute(
                "ALTER TABLE command_configs ADD COLUMN total_success_count INTEGER NOT NULL DEFAULT 0"
            )
        if "total_failure_count" not in cols:
            cursor.execute(
                "ALTER TABLE command_configs ADD COLUMN total_failure_count INTEGER NOT NULL DEFAULT 0"
            )

    runner.add_migration(
        VersionMigration(
            version="0.3.6",
            name="command_aggregate_stats",
            description="Add total_execution_count, total_success_count, total_failure_count to command_configs",
            up_func=migrate_command_aggregate_stats,
        )
    )

    def migrate_command_deleted_at(cursor):
        """Add deleted_at for soft-delete (keeps execution history for 7 days)"""
        cursor.execute("PRAGMA table_info(command_configs)")
        cols = [r[1] for r in cursor.fetchall()]
        if "deleted_at" not in cols:
            cursor.execute("ALTER TABLE command_configs ADD COLUMN deleted_at DATETIME NULL")

    runner.add_migration(
        VersionMigration(
            version="0.3.7",
            name="command_deleted_at",
            description="Add deleted_at for soft-delete of commands",
            up_func=migrate_command_deleted_at,
        )
    )

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
                    description = 'Fetch upcoming events for Lidarr artists (Bandsintown / Songkick / Ticketmaster)'
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

    runner.add_migration(
        VersionMigration(
            version="0.3.15",
            name="artist_events_naming",
            description="Rename concert event config keys to ARTIST_EVENTS_* and command to artist_events_refresh",
            up_func=migrate_artist_events_naming,
        )
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

    runner.add_migration(
        VersionMigration(
            version="0.3.14-dev",
            name="concert_event_user_interested",
            description="Add user_interested to concert_event for Artist Events page",
            up_func=migrate_concert_event_user_interested,
        )
    )

    def migrate_concert_event_dedupe_coalesce(cursor):
        """
        Recompute venue fingerprints with coarser geo (see utils.event_geo.venue_fingerprint),
        merge duplicate concert_event rows that now share the same dedupe key, then refresh
        dedupe_key for all rows.
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

    runner.add_migration(
        VersionMigration(
            version="0.3.14-dev",
            name="concert_event_dedupe_coalesce",
            description="Merge duplicate concert_event rows after coarser venue fingerprinting",
            up_func=migrate_concert_event_dedupe_coalesce,
        )
    )

    return runner


def run_version_migrations():
    """Run version-based migrations"""
    runner = create_version_migration_runner()
    runner.run_migrations_if_needed()


if __name__ == "__main__":
    run_version_migrations()
