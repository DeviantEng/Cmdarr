#!/usr/bin/env python3
"""
Database connection and session management for split databases
"""

import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import StaticPool
from typing import Generator
from .config_models import ConfigBase
from .cache_models import CacheBase


class DatabaseManager:
    """Database connection and session management for split databases"""
    
    def __init__(self, config_url: str = None, cache_url: str = None):
        # Set up data directory
        data_dir = os.path.join(os.getcwd(), 'data')
        os.makedirs(data_dir, exist_ok=True)
        
        # Default database URLs
        if config_url is None:
            config_url = f"sqlite:///{os.path.join(data_dir, 'cmdarr_config.db')}"
        if cache_url is None:
            cache_url = f"sqlite:///{os.path.join(data_dir, 'cmdarr_cache.db')}"
        
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
        if config_url.startswith('sqlite:///'):
            engine_kwargs['connect_args']['isolation_level'] = None
        
        # Create engines for both databases
        self.config_engine = create_engine(config_url, **engine_kwargs)
        self.cache_engine = create_engine(cache_url, **engine_kwargs)
        
        # Create session makers
        self.ConfigSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=self.config_engine)
        self.CacheSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=self.cache_engine)
        
        # Create all tables
        self.create_tables()
    
    def create_tables(self):
        """Create all database tables in their respective databases"""
        ConfigBase.metadata.create_all(bind=self.config_engine)
        CacheBase.metadata.create_all(bind=self.cache_engine)
    
    def get_config_session(self) -> Generator[Session, None, None]:
        """Get config database session with proper cleanup"""
        session = self.ConfigSessionLocal()
        try:
            yield session
        finally:
            session.close()
    
    def get_cache_session(self) -> Generator[Session, None, None]:
        """Get cache database session with proper cleanup"""
        session = self.CacheSessionLocal()
        try:
            yield session
        finally:
            session.close()
    
    def get_config_session_context(self):
        """Get config database session context manager"""
        return self.ConfigSessionLocal()
    
    def get_cache_session_context(self):
        """Get cache database session context manager"""
        return self.CacheSessionLocal()
    
    def get_config_session_sync(self) -> Session:
        """Get config database session for synchronous operations"""
        return self.ConfigSessionLocal()
    
    def get_cache_session_sync(self) -> Session:
        """Get cache database session for synchronous operations"""
        return self.CacheSessionLocal()
    
    # Backward compatibility methods (default to config database)
    def get_session(self) -> Generator[Session, None, None]:
        """Get config database session (backward compatibility)"""
        yield from self.get_config_session()
    
    def get_session_context(self):
        """Get config database session context manager (backward compatibility)"""
        return self.get_config_session_context()
    
    def get_session_sync(self) -> Session:
        """Get config database session for synchronous operations (backward compatibility)"""
        return self.get_config_session_sync()


# Global database manager instance
db_manager = None


def get_database_manager() -> DatabaseManager:
    """Get or create database manager instance"""
    global db_manager
    if db_manager is None:
        db_manager = DatabaseManager()
    return db_manager


def get_db() -> Generator[Session, None, None]:
    """Dependency for FastAPI to get config database session (backward compatibility)"""
    manager = get_database_manager()
    yield from manager.get_config_session()

def get_config_db() -> Generator[Session, None, None]:
    """Dependency for FastAPI to get config database session"""
    manager = get_database_manager()
    yield from manager.get_config_session()

def get_cache_db() -> Generator[Session, None, None]:
    """Dependency for FastAPI to get cache database session"""
    manager = get_database_manager()
    yield from manager.get_cache_session()
