"""Unit tests for Last.fm Discovery session service."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from services.lastfm_discovery_service import LastfmDiscoveryService


@pytest.mark.asyncio
async def test_start_session_requires_mbid():
    svc = LastfmDiscoveryService()
    with pytest.raises(ValueError, match="At least one seed"):
        await svc.start_session([{"mbid": "", "name": "Nobody"}])


@pytest.mark.asyncio
async def test_start_session_rejects_overlapping():
    svc = LastfmDiscoveryService()

    async def slow_run(_self, session):
        session.status = "running"
        await asyncio.sleep(10)

    with patch.object(LastfmDiscoveryService, "_run_session", new=slow_run):
        s1 = await svc.start_session([{"mbid": "mbid-1", "name": "A"}])
        assert s1.status == "running"
        with pytest.raises(RuntimeError, match="already running"):
            await svc.start_session([{"mbid": "mbid-2", "name": "B"}])
        if s1.task and not s1.task.done():
            s1.task.cancel()
            with pytest.raises(asyncio.CancelledError):
                await s1.task


@pytest.mark.asyncio
async def test_session_discovers_and_filters():
    svc = LastfmDiscoveryService()

    lidarr = AsyncMock()
    lidarr.__aenter__.return_value = lidarr
    lidarr.__aexit__.return_value = None
    lidarr.get_all_artists = AsyncMock(
        return_value=[
            {"musicBrainzId": "seed-mbid", "artistName": "Seed Artist"},
            {"musicBrainzId": "owned-mbid", "artistName": "Already Owned"},
        ]
    )
    lidarr.get_import_list_exclusions = AsyncMock(return_value=set())

    lastfm = AsyncMock()
    lastfm.__aenter__.return_value = lastfm
    lastfm.__aexit__.return_value = None
    lastfm.get_similar_artists = AsyncMock(
        return_value=(
            [
                {
                    "mbid": "owned-mbid",
                    "name": "Already Owned",
                    "match": "0.99",
                    "url": "",
                },
                {
                    "mbid": "new-mbid",
                    "name": "New Discovery",
                    "match": "0.88",
                    "url": "https://last.fm/music/New+Discovery",
                },
                {
                    "mbid": "new-mbid-2",
                    "name": "Also New",
                    "match": "0.70",
                    "url": "",
                },
            ],
            [],
        )
    )

    with (
        patch("services.lastfm_discovery_service.ConfigAdapter") as cfg_cls,
        patch("services.lastfm_discovery_service.LidarrClient", return_value=lidarr),
        patch("services.lastfm_discovery_service.LastFMClient", return_value=lastfm),
    ):
        cfg_cls.return_value = MagicMock()
        session = await svc.start_session([{"mbid": "seed-mbid", "name": "Seed Artist"}])
        assert session.task is not None
        await session.task

    assert session.status == "completed"
    lidarr.get_all_artists.assert_awaited()
    assert lidarr.get_all_artists.await_args.kwargs.get("force_refresh") is True
    mbids = {r.mbid for r in session.results.values()}
    assert "new-mbid" in mbids
    assert "new-mbid-2" in mbids
    assert "owned-mbid" not in mbids
    assert "seed-mbid" not in mbids


@pytest.mark.asyncio
async def test_affinity_bumps_seed_count():
    svc = LastfmDiscoveryService()

    lidarr = AsyncMock()
    lidarr.__aenter__.return_value = lidarr
    lidarr.__aexit__.return_value = None
    lidarr.get_all_artists = AsyncMock(return_value=[])
    lidarr.get_import_list_exclusions = AsyncMock(return_value=set())

    lastfm = AsyncMock()
    lastfm.__aenter__.return_value = lastfm
    lastfm.__aexit__.return_value = None

    async def similar_side_effect(mbid=None, artist_name=None, limit=None, **_kwargs):
        return (
            [
                {
                    "mbid": "shared-mbid",
                    "name": "Shared Artist",
                    "match": "0.5" if mbid == "seed-a" else "0.9",
                    "url": "",
                }
            ],
            [],
        )

    lastfm.get_similar_artists = AsyncMock(side_effect=similar_side_effect)

    with (
        patch("services.lastfm_discovery_service.ConfigAdapter") as cfg_cls,
        patch("services.lastfm_discovery_service.LidarrClient", return_value=lidarr),
        patch("services.lastfm_discovery_service.LastFMClient", return_value=lastfm),
    ):
        cfg_cls.return_value = MagicMock()
        session = await svc.start_session(
            [
                {"mbid": "seed-a", "name": "Artist A"},
                {"mbid": "seed-b", "name": "Artist B"},
            ]
        )
        await session.task

    assert session.status == "completed"
    shared = session.results["shared-mbid"]
    assert shared.seed_count == 2
    assert set(shared.seed_names) == {"Artist A", "Artist B"}
    assert shared.match_score == 0.9


@pytest.mark.asyncio
async def test_stop_during_one_shot():
    svc = LastfmDiscoveryService()

    lidarr = AsyncMock()
    lidarr.__aenter__.return_value = lidarr
    lidarr.__aexit__.return_value = None
    lidarr.get_all_artists = AsyncMock(return_value=[])
    lidarr.get_import_list_exclusions = AsyncMock(return_value=set())

    lastfm = AsyncMock()
    lastfm.__aenter__.return_value = lastfm
    lastfm.__aexit__.return_value = None

    async def slow_similar(**_kwargs):
        await asyncio.sleep(0.2)
        return (
            [{"mbid": "new-mbid", "name": "New", "match": "0.5", "url": ""}],
            [],
        )

    lastfm.get_similar_artists = AsyncMock(side_effect=slow_similar)

    with (
        patch("services.lastfm_discovery_service.ConfigAdapter") as cfg_cls,
        patch("services.lastfm_discovery_service.LidarrClient", return_value=lidarr),
        patch("services.lastfm_discovery_service.LastFMClient", return_value=lastfm),
    ):
        cfg_cls.return_value = MagicMock()
        session = await svc.start_session(
            [
                {"mbid": "seed-a", "name": "Artist A"},
                {"mbid": "seed-b", "name": "Artist B"},
            ]
        )
        await asyncio.sleep(0.05)
        await svc.stop_session(session.session_id)
        await session.task

    assert session.status == "stopped"
