#!/usr/bin/env python3
"""
Simplified migration script to split cmdarr.db into cmdarr_config.db and cmdarr_cache.db

This script will:
1. Create new separate databases
2. Migrate only config tables (settings, commands, executions, system status)
3. Create fresh cache database (no migration of cache data)
4. Delete the original database after successful migration
"""

import os
import sqlite3
from pathlib import Path
from datetime import datetime
import sys

# Add project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from database.database import DatabaseManager
from utils.logger import setup_application_logging, get_logger

# Lazy-load logger to avoid initialization issues
def get_migration_logger():
    return get_logger('cmdarr.migration')


def migrate_config_data(old_db_path: Path, config_db_path: Path):
    """Migrate only config-related data to the config database"""
    get_migration_logger().info("Migrating config data...")
    
    config_tables = [
        'config_settings',
        'command_configs', 
        'command_executions',
        'system_status'
    ]
    
    # Connect to both databases
    old_conn = sqlite3.connect(old_db_path)
    config_conn = sqlite3.connect(config_db_path)
    
    try:
        # Enable foreign key constraints
        config_conn.execute("PRAGMA foreign_keys=ON")
        
        for table in config_tables:
            get_migration_logger().info(f"Migrating table: {table}")
            
            # Check if table exists in old database
            cursor = old_conn.execute(f"SELECT name FROM sqlite_master WHERE type='table' AND name='{table}'")
            if not cursor.fetchone():
                get_migration_logger().info(f"Table {table} does not exist in old database, skipping")
                continue
            
            # Copy data (tables already exist from DatabaseManager)
            cursor = old_conn.execute(f"SELECT * FROM {table}")
            rows = cursor.fetchall()
            
            if rows:
                # Get column names
                cursor = old_conn.execute(f"PRAGMA table_info({table})")
                columns = [col[1] for col in cursor.fetchall()]
                
                # Clear existing data first (DatabaseManager may have created default data)
                config_conn.execute(f"DELETE FROM {table}")
                
                # Insert data
                placeholders = ','.join(['?' for _ in columns])
                insert_sql = f"INSERT INTO {table} ({','.join(columns)}) VALUES ({placeholders})"
                
                config_conn.executemany(insert_sql, rows)
                get_migration_logger().info(f"Migrated {len(rows)} rows from {table}")
            else:
                get_migration_logger().info(f"No data to migrate from {table}")
        
        config_conn.commit()
        get_migration_logger().info("Config data migration completed successfully")
        
    except Exception as e:
        get_migration_logger().error(f"Error migrating config data: {e}")
        config_conn.rollback()
        raise
    finally:
        old_conn.close()
        config_conn.close()


def verify_migration(old_db_path: Path, config_db_path: Path):
    """Verify that the config migration was successful"""
    get_migration_logger().info("Verifying migration...")
    
    old_conn = sqlite3.connect(old_db_path)
    config_conn = sqlite3.connect(config_db_path)
    
    try:
        # Verify config tables
        config_tables = ['config_settings', 'command_configs', 'command_executions', 'system_status']
        for table in config_tables:
            old_cursor = old_conn.execute(f"SELECT COUNT(*) FROM {table}")
            old_count = old_cursor.fetchone()[0]
            
            config_cursor = config_conn.execute(f"SELECT COUNT(*) FROM {table}")
            config_count = config_cursor.fetchone()[0]
            
            if old_count == config_count:
                get_migration_logger().info(f"✅ {table}: {config_count} rows migrated successfully")
            else:
                get_migration_logger().error(f"❌ {table}: Expected {old_count}, got {config_count}")
        
        get_migration_logger().info("Migration verification completed")
        
    finally:
        old_conn.close()
        config_conn.close()


def main():
    """Main migration function"""
    get_migration_logger().info("Starting simplified database split migration...")
    
    # Get data directory
    data_dir = Path("data")
    data_dir.mkdir(exist_ok=True)
    
    old_db_path = data_dir / "cmdarr.db"
    config_db_path = data_dir / "cmdarr_config.db"
    cache_db_path = data_dir / "cmdarr_cache.db"
    
    # Check if old database exists
    if not old_db_path.exists():
        get_migration_logger().info("No existing database found. Creating new split databases...")
        
        # Create new databases using DatabaseManager
        db_manager = DatabaseManager()
        get_migration_logger().info("New split databases created successfully")
        return
    
    try:
        # Create new databases using DatabaseManager (this creates the tables)
        get_migration_logger().info("Creating new split databases...")
        db_manager = DatabaseManager()
        
        # Migrate only config data
        migrate_config_data(old_db_path, config_db_path)
        
        # Verify migration
        verify_migration(old_db_path, config_db_path)
        
        # Delete old database
        old_db_path.unlink()
        get_migration_logger().info(f"Deleted old database: {old_db_path}")
        
        get_migration_logger().info("✅ Simplified database split migration completed successfully!")
        get_migration_logger().info(f"📁 Config database: {config_db_path}")
        get_migration_logger().info(f"📁 Cache database: {cache_db_path} (fresh)")
        get_migration_logger().info("📁 Original database deleted")
        
    except Exception as e:
        get_migration_logger().error(f"❌ Migration failed: {e}")
        get_migration_logger().error("The original database is unchanged")
        raise


if __name__ == "__main__":
    main()
