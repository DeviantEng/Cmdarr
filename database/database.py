#!/usr/bin/env python3
"""
Database connection and session management
"""

import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import StaticPool
from typing import Generator
from .models import Base


class DatabaseManager:
    """Database connection and session management"""
    
    def __init__(self, database_url: str = None):
        if database_url is None:
            # Default to SQLite in data directory
            data_dir = os.path.join(os.getcwd(), 'data')
            os.makedirs(data_dir, exist_ok=True)
            database_url = f"sqlite:///{os.path.join(data_dir, 'cmdarr.db')}"
        
        # SQLite configuration for better performance
        engine_kwargs = {
            'poolclass': StaticPool,
            'connect_args': {
                'check_same_thread': False,  # Allow multi-threading
                'timeout': 30,  # Connection timeout
            },
            'echo': False,  # Set to True for SQL debugging
        }
        
        # Add WAL mode for better concurrency
        if database_url.startswith('sqlite:///'):
            engine_kwargs['connect_args']['isolation_level'] = None
        
        self.engine = create_engine(database_url, **engine_kwargs)
        self.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=self.engine)
        
        # Create all tables
        self.create_tables()
    
    def create_tables(self):
        """Create all database tables"""
        Base.metadata.create_all(bind=self.engine)
    
    def get_session(self) -> Generator[Session, None, None]:
        """Get database session with proper cleanup"""
        session = self.SessionLocal()
        try:
            yield session
        finally:
            session.close()
    
    def get_session_context(self):
        """Get database session context manager"""
        return self.SessionLocal()
    
    def get_session_sync(self) -> Session:
        """Get database session for synchronous operations"""
        return self.SessionLocal()


# Global database manager instance
db_manager = None


def get_database_manager() -> DatabaseManager:
    """Get or create database manager instance"""
    global db_manager
    if db_manager is None:
        db_manager = DatabaseManager()
    return db_manager


def get_db() -> Generator[Session, None, None]:
    """Dependency for FastAPI to get database session"""
    manager = get_database_manager()
    yield from manager.get_session()
