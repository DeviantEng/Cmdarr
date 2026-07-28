"""Unit tests for singleton command families."""

from __future__ import annotations

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from database.config_models import CommandConfig, ConfigBase
from utils.command_singleton import (
    SINGLETON_MESSAGE,
    availability_for_create,
    require_singleton_available,
    singleton_occupied,
)


@pytest.fixture()
def session():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    ConfigBase.metadata.create_all(engine)
    TestSession = sessionmaker(bind=engine)
    s = TestSession()
    try:
        yield s
    finally:
        s.close()
        engine.dispose()


def test_availability_empty(session):
    avail = availability_for_create(session)
    assert avail["lidarr_update_all"]["available"] is True
    assert avail["lidarr_wanted_search"]["available"] is True
    assert avail["daylist"]["available"] is True
    assert avail["local_discovery"]["available"] is True


def test_require_blocks_second_lidarr_update_all(session):
    session.add(
        CommandConfig(
            command_name="lidarr_update_all_00001",
            display_name="Lidarr Maintenance - Artist Refresh",
            enabled=True,
            singleton_group="lidarr_update_all",
        )
    )
    session.commit()

    assert singleton_occupied(session, "lidarr_update_all") is True
    with pytest.raises(HTTPException) as exc:
        require_singleton_available(session, "lidarr_update_all")
    assert exc.value.status_code == 409
    assert exc.value.detail == SINGLETON_MESSAGE

    avail = availability_for_create(session)
    assert avail["lidarr_update_all"]["available"] is False
    assert avail["lidarr_wanted_search"]["available"] is True


def test_legacy_prefix_counts_without_singleton_group(session):
    session.add(
        CommandConfig(
            command_name="daylist_00001",
            display_name="[Cmdarr] [User] Daylist",
            enabled=True,
            singleton_group=None,
        )
    )
    session.commit()
    assert singleton_occupied(session, "daylist") is True
    assert availability_for_create(session)["daylist"]["available"] is False


def test_soft_deleted_does_not_block(session):
    from datetime import UTC, datetime

    session.add(
        CommandConfig(
            command_name="local_discovery_00001",
            display_name="LD",
            enabled=False,
            singleton_group="local_discovery",
            deleted_at=datetime.now(UTC).replace(tzinfo=None),
        )
    )
    session.commit()
    assert singleton_occupied(session, "local_discovery") is False
    require_singleton_available(session, "local_discovery")
