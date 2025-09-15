#!/usr/bin/env python3
"""
Database migration script for Cmdarr
Handles schema changes and data migrations
"""

import sys
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

try:
    from database.migration_framework import run_migrations
except ImportError:
    # Fallback to simple migration if framework is not available
    import sqlite3
    import logging
    
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger('cmdarr.migrate')
    
    def run_migrations():
        """Fallback migration function"""
        db_path = Path("data/cmdarr.db")
        
        if not db_path.exists():
            logger.info("Database does not exist, skipping migrations")
            return
        
        logger.info("Running fallback database migrations...")
        
        try:
            conn = sqlite3.connect(str(db_path))
            cursor = conn.cursor()
            
            # Create migrations table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS migrations (
                    id INTEGER PRIMARY KEY,
                    migration_name TEXT UNIQUE NOT NULL,
                    applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Migration 1: Add status column to command_executions
            migration_name = "add_status_column_to_command_executions"
            cursor.execute("SELECT COUNT(*) FROM migrations WHERE migration_name = ?", (migration_name,))
            if cursor.fetchone()[0] == 0:
                try:
                    # Check if column already exists
                    cursor.execute("PRAGMA table_info(command_executions)")
                    columns = [row[1] for row in cursor.fetchall()]
                    
                    if 'status' not in columns:
                        cursor.execute("ALTER TABLE command_executions ADD COLUMN status VARCHAR(20) DEFAULT 'running';")
                        logger.info("Added status column to command_executions table")
                    else:
                        logger.info("Status column already exists")
                    
                    cursor.execute("INSERT INTO migrations (migration_name) VALUES (?)", (migration_name,))
                    
                except sqlite3.OperationalError as e:
                    if "duplicate column name" in str(e):
                        logger.info("Status column already exists, marking migration as applied")
                        cursor.execute("INSERT INTO migrations (migration_name) VALUES (?)", (migration_name,))
                    else:
                        raise
            else:
                logger.info("Migration 'add_status_column_to_command_executions' already applied")
            
            # Update existing records to have correct status
            try:
                cursor.execute("PRAGMA table_info(command_executions)")
                columns = [row[1] for row in cursor.fetchall()]
                if 'status' in columns:
                    cursor.execute("UPDATE command_executions SET status = 'completed' WHERE completed_at IS NOT NULL AND success = 1 AND (status IS NULL OR status = 'running');")
                    cursor.execute("UPDATE command_executions SET status = 'failed' WHERE completed_at IS NOT NULL AND success = 0 AND (status IS NULL OR status = 'running');")
                    logger.info("Updated existing execution records with correct status")
            except sqlite3.Error as e:
                logger.warning(f"Failed to update existing records: {e}")
            
            conn.commit()
            logger.info("Database migrations completed successfully")
            
        except Exception as e:
            logger.error(f"Migration failed: {e}")
            raise
        finally:
            conn.close()


if __name__ == "__main__":
    run_migrations()
