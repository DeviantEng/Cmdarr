#!/usr/bin/env python3
"""
Version-based migration system for Cmdarr

This system tracks the application version in the database and only runs migrations
when the version changes, avoiding unnecessary migration checks on every startup.
"""

import sqlite3
import os
import sys
from pathlib import Path
from typing import List, Callable, Optional

# Add project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from utils.logger import setup_application_logging, get_logger

# Lazy-load logger to avoid initialization issues
def get_migrations_logger():
    return get_logger('cmdarr.migrations')


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
            get_migrations_logger().info(f"Applying migration {self.name} for version {self.version}")
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
        self.migrations: List[VersionMigration] = []
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
    
    def get_last_run_version(self) -> Optional[str]:
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
            cursor.execute("""
                INSERT OR REPLACE INTO app_version (id, version, last_run) 
                VALUES (1, ?, CURRENT_TIMESTAMP)
            """, (version,))
            
            conn.commit()
            conn.close()
            get_migrations_logger().info(f"Updated last run version to {version}")
            
        except Exception as e:
            get_migrations_logger().error(f"Failed to update last run version: {e}")
    
    def run_migrations_if_needed(self):
        """Run migrations only if the version has changed"""
        last_version = self.get_last_run_version()
        current_version = self.current_version
        
        get_migrations_logger().info(f"Current version: {current_version}, Last run version: {last_version}")
        
        if last_version == current_version:
            get_migrations_logger().info("Version unchanged, skipping migrations")
            return
        
        if not Path(self.config_db_path).exists():
            get_migrations_logger().info("Config database does not exist, skipping migrations")
            return
        
        get_migrations_logger().info(f"Version changed from {last_version} to {current_version}, running migrations...")
        
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
                        get_migrations_logger().error(f"Migration {migration.name} failed, stopping")
                        conn.rollback()
                        conn.close()
                        return
            
            conn.commit()
            conn.close()
            
            # Update the last run version
            self.update_last_run_version(current_version)
            
            get_migrations_logger().info(f"Successfully ran {migrations_run} migrations for version {current_version}")
            
        except Exception as e:
            get_migrations_logger().error(f"Migration failed: {e}")
            raise


def create_version_migration_runner() -> VersionMigrationRunner:
    """Create a migration runner with version-based migrations"""
    runner = VersionMigrationRunner()
    
    # Migration for v0.1.5: Database split
    def migrate_database_split(cursor):
        """Migrate from single database to split databases"""
        get_migrations_logger().info("Running database split migration...")
        
        # Check if we're running on the old single database
        old_db_path = "data/cmdarr.db"
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
    
    runner.add_migration(VersionMigration(
        version="0.1.5",
        name="database_split",
        description="Split single database into config and cache databases",
        up_func=migrate_database_split
    ))

    def migrate_dismissed_artist_name(cursor):
        """Add artist_name to dismissed_artist_album for restore UI"""
        cursor.execute("PRAGMA table_info(dismissed_artist_album)")
        cols = [r[1] for r in cursor.fetchall()]
        if 'artist_name' not in cols:
            cursor.execute("ALTER TABLE dismissed_artist_album ADD COLUMN artist_name VARCHAR(500)")

    runner.add_migration(VersionMigration(
        version="0.2.4",
        name="dismissed_artist_name",
        description="Add artist_name to dismissed_artist_album",
        up_func=migrate_dismissed_artist_name
    ))
    
    # Add future migrations here for new versions
    # Example:
    # runner.add_migration(VersionMigration(
    #     version="0.1.6",
    #     name="new_feature",
    #     description="Add new feature",
    #     up_func=your_migration_function
    # ))
    
    return runner


def run_version_migrations():
    """Run version-based migrations"""
    runner = create_version_migration_runner()
    runner.run_migrations_if_needed()


if __name__ == "__main__":
    run_version_migrations()
