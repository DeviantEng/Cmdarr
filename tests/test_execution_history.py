"""Tests for command execution history filtering and retention."""

from __future__ import annotations

from datetime import datetime, timedelta
from unittest.mock import patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.api.status import (
    _execution_summary,
    _filtered_executions_query,
    parse_execution_since,
)
from database.config_models import CommandConfig, CommandExecution, ConfigBase


@pytest.fixture()
def session():
    engine = create_engine("sqlite://")
    ConfigBase.metadata.create_all(engine)
    TestSession = sessionmaker(bind=engine)
    db = TestSession()
    try:
        db.add(
            CommandConfig(
                command_name="test_cmd",
                display_name="Test Command",
                enabled=True,
            )
        )
        now = datetime.utcnow()
        rows = [
            CommandExecution(
                command_name="test_cmd",
                started_at=now - timedelta(days=1),
                completed_at=now - timedelta(days=1),
                success=True,
                status="completed",
                duration=10.0,
                triggered_by="scheduler",
            ),
            CommandExecution(
                command_name="test_cmd",
                started_at=now - timedelta(days=5),
                completed_at=now - timedelta(days=5),
                success=False,
                status="failed",
                duration=20.0,
                triggered_by="manual",
            ),
            CommandExecution(
                command_name="other_cmd",
                started_at=now - timedelta(days=2),
                completed_at=None,
                success=None,
                status="running",
                duration=None,
                triggered_by="api",
            ),
            CommandExecution(
                command_name="test_cmd",
                started_at=now - timedelta(days=40),
                completed_at=now - timedelta(days=40),
                success=True,
                status="completed",
                duration=30.0,
                triggered_by="scheduler",
            ),
        ]
        db.add_all(rows)
        db.commit()
        yield db
    finally:
        db.close()
        engine.dispose()


def test_execution_summary_respects_since_and_command(session):
    since = datetime.utcnow() - timedelta(days=10)
    summary = _execution_summary(session, since, "test_cmd")
    assert summary["total_count"] == 2
    assert summary["success_count"] == 1
    assert summary["failure_count"] == 1
    assert summary["running_count"] == 0
    assert summary["avg_duration_seconds"] == 15.0


def test_filtered_executions_query_command_filter(session):
    since = datetime.utcnow() - timedelta(days=10)
    query = _filtered_executions_query(session, since, "other_cmd")
    assert query.count() == 1


@pytest.mark.asyncio
async def test_cleanup_old_executions_skips_when_retention_zero(session):
    from services.command_cleanup import CommandCleanupService

    service = CommandCleanupService()
    with patch("services.config_service.config_service") as mock_cfg:
        mock_cfg.get_int.return_value = 0
        await service.cleanup_old_executions()
    assert session.query(CommandExecution).count() == 4


def test_parse_execution_since_tokens():
    cutoff = parse_execution_since("7d")
    assert cutoff is not None
    assert (datetime.utcnow() - cutoff).days == pytest.approx(7, abs=1)


def test_parse_execution_since_all_returns_none():
    assert parse_execution_since("all") is None
    assert parse_execution_since(None) is None


@pytest.mark.asyncio
async def test_cleanup_old_executions_deletes_by_age(session):
    from services.command_cleanup import CommandCleanupService

    service = CommandCleanupService()
    with patch("database.database.get_database_manager") as mock_get_mgr:
        mock_get_mgr.return_value.get_session_sync.return_value = session
        with patch("services.config_service.config_service") as mock_cfg:
            mock_cfg.get_int.return_value = 30
            await service.cleanup_old_executions()
    remaining = session.query(CommandExecution).all()
    assert len(remaining) == 3
    assert all((datetime.utcnow() - r.started_at).days <= 30 for r in remaining)
