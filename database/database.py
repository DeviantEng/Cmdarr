#!/usr/bin/env python3
"""
Database connection and session management for split databases
"""

import os
from collections.abc import Generator
from pathlib import Path

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import SingletonThreadPool, StaticPool

from .cache_models import CacheBase
from .config_models import ConfigBase
from .library_audit_models import LibraryAuditBase


@event.listens_for(Engine, "connect")
def _enable_sqlite_fk(dbapi_connection, connection_record):
    """Enable foreign key enforcement on every new SQLite connection.

    SQLite defaults foreign keys off, which silently disables our ORM-declared
    `ondelete=CASCADE` rules. Without this listener, deleting a parent row (e.g.
    `concert_event`) leaves orphan `concert_event_source` rows behind, which can
    reattach to unrelated parents once SQLite reuses the freed id. Turning FKs on
    here makes cascades behave as the schema advertises on every connection the
    engine hands out.
    """
    try:
        import sqlite3

        if isinstance(dbapi_connection, sqlite3.Connection):
            cur = dbapi_connection.cursor()
            cur.execute("PRAGMA foreign_keys = ON")
            cur.close()
    except Exception:
        pass


def _get_data_dir() -> str:
    """Return data directory path. Uses project root (where database.py lives), not cwd.
    Ensures same database is used regardless of where the process was started from."""
    project_root = Path(__file__).resolve().parent.parent
    return str(project_root / "data")


class DatabaseManager:
    """Database connection and session management for split databases"""

    def __init__(
        self,
        config_url: str = None,
        cache_url: str = None,
        library_audit_url: str = None,
        *,
        init_library_audit: bool = False,
    ):
        # Set up data directory (project root, not cwd - prevents lost config when run from subdirs)
        data_dir = _get_data_dir()
        os.makedirs(data_dir, exist_ok=True)
        self._data_dir = data_dir
        self._library_audit_url = library_audit_url
        self._engine_kwargs_template = None

        # Default database URLs
        if config_url is None:
            config_url = f"sqlite:///{os.path.join(data_dir, 'cmdarr_config.db')}"
        if cache_url is None:
            cache_url = f"sqlite:///{os.path.join(data_dir, 'cmdarr_cache.db')}"

        # SQLite configuration: SingletonThreadPool gives each thread its own connection,
        # avoiding sqlite3.InterfaceError when scheduler/workers access config concurrently.
        is_sqlite = config_url.startswith("sqlite:///")
        engine_kwargs = {
            "poolclass": SingletonThreadPool if is_sqlite else StaticPool,
            "connect_args": {
                "check_same_thread": False,  # Allow multi-threading
                "timeout": 30,  # Connection timeout
            },
            "echo": False,  # Set to True for SQL debugging
        }

        # Add WAL mode for better concurrency (file-based SQLite only)
        if is_sqlite:
            engine_kwargs["connect_args"]["isolation_level"] = None

        self._engine_kwargs_template = dict(engine_kwargs)
        self._engine_kwargs_template["connect_args"] = dict(engine_kwargs["connect_args"])

        # Create engines for both databases
        self.config_engine = create_engine(config_url, **engine_kwargs)
        self.cache_engine = create_engine(cache_url, **engine_kwargs)

        # Create session makers
        self.ConfigSessionLocal = sessionmaker(
            autocommit=False, autoflush=False, bind=self.config_engine
        )
        self.CacheSessionLocal = sessionmaker(
            autocommit=False, autoflush=False, bind=self.cache_engine
        )

        # Library audit DB is lazy — created on first feature use
        self.library_audit_engine = None
        self.LibraryAuditSessionLocal = None
        if init_library_audit:
            self.ensure_library_audit_db()

        # Create all tables
        self.create_tables()

    def _default_library_audit_url(self) -> str:
        if self._library_audit_url:
            return self._library_audit_url
        return f"sqlite:///{os.path.join(self._data_dir, 'cmdarr_library_audit.db')}"

    def ensure_library_audit_db(self) -> None:
        """Lazily create the library audit engine, sessions, and tables."""
        if self.library_audit_engine is not None:
            return
        url = self._default_library_audit_url()
        engine_kwargs = dict(self._engine_kwargs_template or {})
        engine_kwargs["connect_args"] = dict(
            (self._engine_kwargs_template or {}).get("connect_args") or {}
        )
        if url.startswith("sqlite:///") and "isolation_level" not in engine_kwargs.get(
            "connect_args", {}
        ):
            engine_kwargs.setdefault("connect_args", {})["isolation_level"] = None
            engine_kwargs.setdefault("poolclass", SingletonThreadPool)
        self.library_audit_engine = create_engine(url, **engine_kwargs)
        self.LibraryAuditSessionLocal = sessionmaker(
            autocommit=False, autoflush=False, bind=self.library_audit_engine
        )
        LibraryAuditBase.metadata.create_all(bind=self.library_audit_engine)

    def create_tables(self):
        """Create all database tables in their respective databases"""
        ConfigBase.metadata.create_all(bind=self.config_engine)
        CacheBase.metadata.create_all(bind=self.cache_engine)
        if self.library_audit_engine is not None:
            LibraryAuditBase.metadata.create_all(bind=self.library_audit_engine)

    def get_config_session(self) -> Generator[Session]:
        """Get config database session with proper cleanup"""
        session = self.ConfigSessionLocal()
        try:
            yield session
        finally:
            session.close()

    def get_cache_session(self) -> Generator[Session]:
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

    def get_library_audit_session(self) -> Generator[Session]:
        """Get library audit database session with proper cleanup"""
        self.ensure_library_audit_db()
        session = self.LibraryAuditSessionLocal()
        try:
            yield session
        finally:
            session.close()

    def get_library_audit_session_context(self):
        """Get library audit database session context manager"""
        self.ensure_library_audit_db()
        return self.LibraryAuditSessionLocal()

    def get_library_audit_session_sync(self) -> Session:
        """Get library audit database session for synchronous operations"""
        self.ensure_library_audit_db()
        return self.LibraryAuditSessionLocal()

    # Backward compatibility methods (default to config database)
    def get_session(self) -> Generator[Session]:
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


def get_db() -> Generator[Session]:
    """Dependency for FastAPI to get config database session (backward compatibility)"""
    manager = get_database_manager()
    yield from manager.get_config_session()


def get_config_db() -> Generator[Session]:
    """Dependency for FastAPI to get config database session"""
    manager = get_database_manager()
    yield from manager.get_config_session()


def get_cache_db() -> Generator[Session]:
    """Dependency for FastAPI to get cache database session"""
    manager = get_database_manager()
    yield from manager.get_cache_session()


def get_library_audit_db() -> Generator[Session]:
    """Dependency for FastAPI to get library audit database session.

    Creates the audit DB lazily. Callers that require the feature to be enabled
    should check LIBRARY_AUDIT_ENABLED before using this dependency.
    """
    manager = get_database_manager()
    yield from manager.get_library_audit_session()
