"""Ensure command config updates do not delete playlists on the target."""

from __future__ import annotations

from unittest.mock import patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.commands import CommandUpdateRequest, update_command
from database.config_models import CommandConfig, ConfigBase


@pytest.fixture()
def db_session():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    ConfigBase.metadata.create_all(engine)
    TestSession = sessionmaker(bind=engine)
    db = TestSession()
    try:
        db.add(
            CommandConfig(
                command_name="top_tracks_00001",
                display_name="[Cmdarr] Artist Essentials: A · B",
                enabled=True,
                config_json={
                    "artists": ["Dead Air Divine", "LANDMVRKS"],
                    "top_x": 5,
                    "source": "lastfm",
                    "target": "plex",
                    "last_playlist_title": "[Cmdarr] Artist Essentials: Dead Air Divine · LANDMVRKS",
                    "last_playlist_id": "585934",
                },
            )
        )
        db.commit()
        yield db
    finally:
        db.close()
        engine.dispose()


@pytest.mark.asyncio
async def test_update_command_does_not_delete_playlist_when_source_changes(db_session):
    with patch(
        "services.command_cleanup.CommandCleanupService._delete_playlist_if_exists"
    ) as delete_mock:
        request = CommandUpdateRequest(
            config_json={
                "artists": ["Dead Air Divine", "LANDMVRKS"],
                "top_x": 5,
                "source": "plex",
                "target": "plex",
                "last_playlist_title": "[Cmdarr] Artist Essentials: Dead Air Divine · LANDMVRKS",
                "last_playlist_id": "585934",
            }
        )
        await update_command("top_tracks_00001", request, db_session)

        delete_mock.assert_not_called()
        updated = (
            db_session.query(CommandConfig)
            .filter(CommandConfig.command_name == "top_tracks_00001")
            .one()
        )
        assert updated.config_json["source"] == "plex"
        assert updated.config_json["last_playlist_id"] == "585934"
        assert updated.config_json["last_playlist_title"].startswith("[Cmdarr] Artist Essentials")
