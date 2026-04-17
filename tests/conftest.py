"""Shared pytest fixtures for cmdarr unit tests."""

from __future__ import annotations

import pytest


@pytest.fixture(autouse=True, scope="session")
def _configure_logger_stub():
    """Satisfy CmdarrLogger.get_logger()'s configured-guard without running the real setup.

    Many modules (e.g. ConfigAdapter, command classes) call get_logger during import or
    construction. Production sets up rotating file handlers; for unit tests we just need
    the guard to pass so logging.getLogger() is reachable.
    """
    from utils.logger import CmdarrLogger

    prior = CmdarrLogger._configured
    CmdarrLogger._configured = True
    try:
        yield
    finally:
        CmdarrLogger._configured = prior
