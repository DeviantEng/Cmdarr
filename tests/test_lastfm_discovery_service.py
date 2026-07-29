"""Unit tests for Last.fm Discovery session service."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from services.lastfm_discovery_service import LastfmDiscoveryService


def _patch_clients(lidarr, lastfm, deezer_cls, cfg_cls):
    cfg_cls.return_value = MagicMock(LASTFM_FETCH_CONCURRENCY=2)
    deezer = AsyncMock()
    deezer.__aenter__.return_value = deezer
    deezer.__aexit__.return_value = None
    deezer.search_artists = AsyncMock(return_value={"artists": []})
    deezer_cls.return_value = deezer


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

    async def _artist_info(mbid=None, artist_name=None, **_kwargs):
        if mbid == "new-mbid":
            return {"listeners": "12500", "playcount": "890000"}
        if mbid == "new-mbid-2":
            return {"listeners": "42", "playcount": "100"}
        return {"listeners": "0", "playcount": "0"}

    lastfm.get_artist_info = AsyncMock(side_effect=_artist_info)

    with (
        patch("services.lastfm_discovery_service.ConfigAdapter") as cfg_cls,
        patch("services.lastfm_discovery_service.LidarrClient", return_value=lidarr),
        patch("services.lastfm_discovery_service.LastFMClient", return_value=lastfm),
        patch("services.lastfm_discovery_service.DeezerClient") as deezer_cls,
    ):
        _patch_clients(lidarr, lastfm, deezer_cls, cfg_cls)
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
    assert session.results["new-mbid"].listeners == 12500
    assert session.results["new-mbid"].playcount == 890000
    assert session.results["new-mbid-2"].listeners == 42
    # Higher match ranks first
    assert session.candidate_order[0] == "new-mbid"
    assert session.visible_count == 2
    assert session.has_more is False
    payload = session.to_dict()
    assert [r["mbid"] for r in payload["results"]] == ["new-mbid", "new-mbid-2"]
    lastfm.get_artist_info.assert_awaited()


@pytest.mark.asyncio
async def test_affinity_bumps_seed_count_and_ranks_shared_first():
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
        if mbid == "seed-a":
            return (
                [
                    {
                        "mbid": "shared-mbid",
                        "name": "Shared Artist",
                        "match": "0.5",
                        "url": "",
                    },
                    {
                        "mbid": "solo-mbid",
                        "name": "Solo High",
                        "match": "0.99",
                        "url": "",
                    },
                ],
                [],
            )
        return (
            [
                {
                    "mbid": "shared-mbid",
                    "name": "Shared Artist",
                    "match": "0.9",
                    "url": "",
                }
            ],
            [],
        )

    lastfm.get_similar_artists = AsyncMock(side_effect=similar_side_effect)
    lastfm.get_artist_info = AsyncMock(return_value={"listeners": "1000", "playcount": "5000"})

    with (
        patch("services.lastfm_discovery_service.ConfigAdapter") as cfg_cls,
        patch("services.lastfm_discovery_service.LidarrClient", return_value=lidarr),
        patch("services.lastfm_discovery_service.LastFMClient", return_value=lastfm),
        patch("services.lastfm_discovery_service.DeezerClient") as deezer_cls,
    ):
        _patch_clients(lidarr, lastfm, deezer_cls, cfg_cls)
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
    assert shared.listeners == 1000
    assert shared.playcount == 5000
    # Multi-seed consensus outranks a single-seed higher match
    assert session.candidate_order[0] == "shared-mbid"
    assert session.candidate_order[1] == "solo-mbid"


@pytest.mark.asyncio
async def test_min_match_score_filters_weak_hits():
    svc = LastfmDiscoveryService()

    lidarr = AsyncMock()
    lidarr.__aenter__.return_value = lidarr
    lidarr.__aexit__.return_value = None
    lidarr.get_all_artists = AsyncMock(return_value=[])
    lidarr.get_import_list_exclusions = AsyncMock(return_value=set())

    lastfm = AsyncMock()
    lastfm.__aenter__.return_value = lastfm
    lastfm.__aexit__.return_value = None
    lastfm.get_similar_artists = AsyncMock(
        return_value=(
            [
                {"mbid": "strong", "name": "Strong", "match": "0.9", "url": ""},
                {"mbid": "weak", "name": "Weak", "match": "0.2", "url": ""},
            ],
            [],
        )
    )
    lastfm.get_artist_info = AsyncMock(return_value={"listeners": "1", "playcount": "1"})

    with (
        patch("services.lastfm_discovery_service.ConfigAdapter") as cfg_cls,
        patch("services.lastfm_discovery_service.LidarrClient", return_value=lidarr),
        patch("services.lastfm_discovery_service.LastFMClient", return_value=lastfm),
        patch("services.lastfm_discovery_service.DeezerClient") as deezer_cls,
    ):
        _patch_clients(lidarr, lastfm, deezer_cls, cfg_cls)
        session = await svc.start_session(
            [{"mbid": "seed", "name": "Seed"}],
            min_match_score=0.5,
        )
        await session.task

    assert session.status == "completed"
    assert set(session.results) == {"strong"}
    assert session.candidate_order == ["strong"]
    assert session.min_match_score == 0.5


@pytest.mark.asyncio
async def test_progressive_batch_enrichment_and_load_more():
    svc = LastfmDiscoveryService()

    lidarr = AsyncMock()
    lidarr.__aenter__.return_value = lidarr
    lidarr.__aexit__.return_value = None
    lidarr.get_all_artists = AsyncMock(return_value=[])
    lidarr.get_import_list_exclusions = AsyncMock(return_value=set())

    similar = [
        {"mbid": f"mbid-{i}", "name": f"Artist {i}", "match": str(0.9 - i * 0.01), "url": ""}
        for i in range(5)
    ]

    lastfm = AsyncMock()
    lastfm.__aenter__.return_value = lastfm
    lastfm.__aexit__.return_value = None
    lastfm.get_similar_artists = AsyncMock(return_value=(similar, []))
    lastfm.get_artist_info = AsyncMock(return_value={"listeners": "10", "playcount": "20"})

    with (
        patch("services.lastfm_discovery_service.ConfigAdapter") as cfg_cls,
        patch("services.lastfm_discovery_service.LidarrClient", return_value=lidarr),
        patch("services.lastfm_discovery_service.LastFMClient", return_value=lastfm),
        patch("services.lastfm_discovery_service.DeezerClient") as deezer_cls,
    ):
        _patch_clients(lidarr, lastfm, deezer_cls, cfg_cls)
        session = await svc.start_session(
            [{"mbid": "seed", "name": "Seed"}],
            batch_size=2,
        )
        await session.task

        assert session.status == "completed"
        assert len(session.candidate_order) == 5
        assert session.visible_count == 2
        assert session.has_more is True
        payload = session.to_dict()
        assert len(payload["results"]) == 2
        assert payload["result_count"] == 5
        assert payload["has_more"] is True
        # Only first batch enriched initially
        assert lastfm.get_artist_info.await_count == 2

        session2 = await svc.load_more(session.session_id)
        assert session2.visible_count == 4
        assert session2.has_more is True
        assert lastfm.get_artist_info.await_count == 4

        session3 = await svc.load_more(session.session_id)
        assert session3.visible_count == 5
        assert session3.has_more is False
        assert lastfm.get_artist_info.await_count == 5

        with pytest.raises(RuntimeError, match="No more"):
            await svc.load_more(session.session_id)


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
    lastfm.get_artist_info = AsyncMock(return_value={"listeners": "1", "playcount": "1"})

    with (
        patch("services.lastfm_discovery_service.ConfigAdapter") as cfg_cls,
        patch("services.lastfm_discovery_service.LidarrClient", return_value=lidarr),
        patch("services.lastfm_discovery_service.LastFMClient", return_value=lastfm),
        patch("services.lastfm_discovery_service.DeezerClient") as deezer_cls,
    ):
        _patch_clients(lidarr, lastfm, deezer_cls, cfg_cls)
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
