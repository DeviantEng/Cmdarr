#!/usr/bin/env python3
"""
Migration framework for Cmdarr database schema changes
Provides a robust system for handling database migrations
"""

import sqlite3
import sys
from pathlib import Path
from typing import List, Callable, Dict, Any
from datetime import datetime

# Add project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

try:
    from utils.logger import get_logger
    from __version__ import __version__ as app_version
    logger = get_logger('cmdarr.migration_framework')
except Exception:
    import logging
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger('cmdarr.migration_framework')


class Migration:
    """Represents a single database migration"""
    
    def __init__(self, name: str, version: str, description: str, up_func: Callable[[sqlite3.Cursor], None]):
        self.name = name
        self.version = version
        self.description = description
        self.up_func = up_func
    
    def apply(self, cursor: sqlite3.Cursor) -> bool:
        """Apply this migration"""
        try:
            logger.info(f"Applying migration: {self.name} - {self.description}")
            self.up_func(cursor)
            logger.info(f"Migration {self.name} applied successfully")
            return True
        except Exception as e:
            logger.error(f"Migration {self.name} failed: {e}")
            return False


class MigrationRunner:
    """Handles running database migrations"""
    
    def __init__(self, db_path: str):
        self.db_path = db_path
        self.migrations: List[Migration] = []
    
    def add_migration(self, migration: Migration):
        """Add a migration to the runner"""
        self.migrations.append(migration)
    
    def run_migrations(self):
        """Run all pending migrations"""
        if not Path(self.db_path).exists():
            logger.info("Database does not exist, skipping migrations")
            return
        
        logger.info("Running database migrations...")
        
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Create migrations table (handle existing table structure)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS migrations (
                    id INTEGER PRIMARY KEY,
                    migration_name TEXT UNIQUE NOT NULL,
                    applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Check if version column exists, if not add it
            cursor.execute("PRAGMA table_info(migrations)")
            columns = [row[1] for row in cursor.fetchall()]
            
            if 'version' not in columns:
                try:
                    cursor.execute("ALTER TABLE migrations ADD COLUMN version TEXT DEFAULT '1.0.0';")
                    logger.info("Added version column to migrations table")
                except sqlite3.OperationalError:
                    pass  # Column might already exist
            
            if 'description' not in columns:
                try:
                    cursor.execute("ALTER TABLE migrations ADD COLUMN description TEXT;")
                    logger.info("Added description column to migrations table")
                except sqlite3.OperationalError:
                    pass  # Column might already exist
            
            # Get applied migrations
            cursor.execute("SELECT migration_name FROM migrations")
            applied_migrations = {row[0] for row in cursor.fetchall()}
            
            # Run pending migrations
            for migration in self.migrations:
                if migration.name not in applied_migrations:
                    if migration.apply(cursor):
                        cursor.execute("""
                            INSERT INTO migrations (migration_name, version, description) 
                            VALUES (?, ?, ?)
                        """, (migration.name, migration.version, migration.description))
                        conn.commit()
                    else:
                        logger.error(f"Migration {migration.name} failed, stopping")
                        break
                else:
                    logger.info(f"Migration {migration.name} already applied, skipping")
            
            logger.info("Database migrations completed successfully")
            
        except Exception as e:
            logger.error(f"Migration failed: {e}")
            raise
        finally:
            conn.close()


def get_migration_version(sequence: int, base_version: str = None) -> str:
    """Generate migration version based on app version and sequence number"""
    # Use provided base_version or current app_version
    # This gives us versions like "0.1.0.1", "0.1.0.2", etc.
    try:
        version_base = base_version if base_version else app_version
        return f"{version_base}.{sequence}"
    except:
        # Fallback if app_version import fails
        return f"1.0.0.{sequence}"


def create_migration_runner(db_path: str = "data/cmdarr.db") -> MigrationRunner:
    """Create a migration runner with all defined migrations"""
    runner = MigrationRunner(db_path)
    
    # Migration 1: Add status column to command_executions
    def add_status_column(cursor):
        # Check if column already exists
        cursor.execute("PRAGMA table_info(command_executions)")
        columns = [row[1] for row in cursor.fetchall()]
        
        if 'status' not in columns:
            cursor.execute("ALTER TABLE command_executions ADD COLUMN status VARCHAR(20) DEFAULT 'running';")
            logger.info("Added status column to command_executions table")
        else:
            logger.info("Status column already exists")
        
        # Update existing records
        cursor.execute("UPDATE command_executions SET status = 'completed' WHERE completed_at IS NOT NULL AND success = 1 AND (status IS NULL OR status = 'running');")
        cursor.execute("UPDATE command_executions SET status = 'failed' WHERE completed_at IS NOT NULL AND success = 0 AND (status IS NULL OR status = 'running');")
        logger.info("Updated existing execution records with correct status")
    
    # All migrations for v0.1.0 - use same base version for consistency
    BASE_VERSION_0_1_0 = "0.1.0"
    
    runner.add_migration(Migration(
        name="add_status_column_to_command_executions",
        version=get_migration_version(1, BASE_VERSION_0_1_0),
        description="Add status column to command_executions table",
        up_func=add_status_column
    ))
    
    # Migration 2: Ensure indexes exist
    def ensure_indexes(cursor):
        cursor.execute("PRAGMA index_list(command_executions)")
        existing_indexes = [row[1] for row in cursor.fetchall()]
        
        indexes_to_create = [
            ("ix_command_executions_command_name", "CREATE INDEX IF NOT EXISTS ix_command_executions_command_name ON command_executions (command_name)"),
            ("ix_command_executions_started_at", "CREATE INDEX IF NOT EXISTS ix_command_executions_started_at ON command_executions (started_at)"),
            ("ix_command_executions_id", "CREATE INDEX IF NOT EXISTS ix_command_executions_id ON command_executions (id)")
        ]
        
        for index_name, create_sql in indexes_to_create:
            if index_name not in existing_indexes:
                cursor.execute(create_sql)
                logger.info(f"Created index: {index_name}")
    
    runner.add_migration(Migration(
        name="ensure_command_executions_indexes",
        version=get_migration_version(2, BASE_VERSION_0_1_0),
        description="Ensure all required indexes exist on command_executions table",
        up_func=ensure_indexes
    ))
    
    # Migration 3: Add timeout_minutes column to command_configs
    def add_timeout_column(cursor):
        # Check if column already exists
        cursor.execute("PRAGMA table_info(command_configs)")
        columns = [row[1] for row in cursor.fetchall()]
        
        if 'timeout_minutes' not in columns:
            cursor.execute("ALTER TABLE command_configs ADD COLUMN timeout_minutes INTEGER;")
            logger.info("Added timeout_minutes column to command_configs table")
        else:
            logger.info("Timeout column already exists")
        
        # Set default timeout of 120 minutes for all existing commands
        cursor.execute("""
            UPDATE command_configs 
            SET timeout_minutes = 120
            WHERE timeout_minutes IS NULL
        """)
        logger.info("Set default timeout of 120 minutes for all existing commands")
    
    runner.add_migration(Migration(
        name="add_timeout_column_to_command_configs",
        version=get_migration_version(3, BASE_VERSION_0_1_0),
        description="Add timeout_minutes column to command_configs table with defaults",
        up_func=add_timeout_column
    ))
    
    # Migration 4: Remove playlist sync config options from global config
    def remove_playlist_sync_global_config(cursor):
        playlist_sync_keys = [
            'PLAYLIST_SYNC_LISTENBRAINZ_CURATED_ENABLED',
            'PLAYLIST_SYNC_LISTENBRAINZ_CURATED_SCHEDULE',
            'PLAYLIST_SYNC_LISTENBRAINZ_CURATED_TARGET',
            'PLAYLIST_SYNC_LISTENBRAINZ_CURATED_PLAYLISTS',
            'PLAYLIST_SYNC_LISTENBRAINZ_CURATED_CLEANUP',
            'PLAYLIST_SYNC_LISTENBRAINZ_CURATED_WEEKLY_EXPLORATION_RETENTION',
            'PLAYLIST_SYNC_LISTENBRAINZ_CURATED_WEEKLY_JAMS_RETENTION',
            'PLAYLIST_SYNC_LISTENBRAINZ_CURATED_DAILY_JAMS_RETENTION'
        ]
        
        for key in playlist_sync_keys:
            cursor.execute("DELETE FROM config_settings WHERE key = ?", (key,))
        
        logger.info("Removed playlist sync configuration options from global config (now command-specific only)")
    
    runner.add_migration(Migration(
        name="remove_playlist_sync_global_config",
        version=get_migration_version(4, BASE_VERSION_0_1_0),
        description="Remove playlist sync config options from global config (now command-specific)",
        up_func=remove_playlist_sync_global_config
    ))
    
    # Migration 5: Add command_type column to command_configs
    def add_command_type_column(cursor):
        # Check if column already exists
        cursor.execute("PRAGMA table_info(command_configs)")
        columns = [row[1] for row in cursor.fetchall()]
        
        if 'command_type' not in columns:
            cursor.execute("ALTER TABLE command_configs ADD COLUMN command_type VARCHAR(50);")
            logger.info("Added command_type column to command_configs table")
            
            # Set default command types for existing commands
            cursor.execute("""
                UPDATE command_configs 
                SET command_type = 'discovery' 
                WHERE command_name IN ('discovery_lastfm', 'playlist_sync_discovery_maintenance')
            """)
            logger.info("Set command_type for existing discovery commands")
        else:
            logger.info("Command_type column already exists")
    
    runner.add_migration(Migration(
        name="add_command_type_column_to_command_configs",
        version=get_migration_version(5, BASE_VERSION_0_1_0),
        description="Add command_type column to command_configs table with defaults",
        up_func=add_command_type_column
    ))
    
    # Future migrations for new app versions should use current app_version
    # Example for when you bump to 0.2.0:
    # runner.add_migration(Migration(
    #     name="your_new_migration",
    #     version=get_migration_version(1),  # Uses current app_version (0.2.0) -> 0.2.0.1
    #     description="Your new migration for v0.2.0",
    #     up_func=your_migration_function
    # ))
    
    return runner


def run_migrations():
    """Run all pending database migrations using the framework"""
    runner = create_migration_runner()
    runner.run_migrations()


if __name__ == "__main__":
    run_migrations()
