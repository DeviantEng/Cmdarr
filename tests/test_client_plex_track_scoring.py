"""Unit tests for Plex track match scoring (no API)."""

import logging

import pytest

from clients.client_plex import PlexClient
from utils.track_match import collaboration_mismatch_penalty


def test_collaboration_mismatch_penalty_featured_plex_only():
    assert (
        collaboration_mismatch_penalty(
            "Bring Me the Horizon",
            "Bring Me the Horizon & Draper",
        )
        == 60
    )


def test_collaboration_mismatch_penalty_no_penalty_when_source_lists_collab():
    assert (
        collaboration_mismatch_penalty(
            "Bring Me the Horizon & Draper",
            "Bring Me the Horizon & Draper",
        )
        == 0
    )


def test_collaboration_mismatch_penalty_no_penalty_when_plex_solo():
    assert (
        collaboration_mismatch_penalty(
            "Bring Me the Horizon",
            "Bring Me the Horizon",
        )
        == 0
    )


@pytest.fixture
def plex_client():
    """Bare instance — only scoring helpers are exercised (no __init__ / API)."""
    c = PlexClient.__new__(PlexClient)
    c.logger = logging.getLogger("test.plex_track_scoring")
    c.cache_client = None
    c._record_cache_hit = lambda: None
    c._record_cache_miss = lambda: None
    return c


def test_score_track_match_requires_title_not_artist_only(plex_client: PlexClient):
    """Same artist, wrong song must not reach a winning score when title does not match."""
    wrong_song = {
        "title": "Follow You Home",
        "grandparentTitle": "Nickelback",
        "parentTitle": "Album",
        "guid": "",
    }
    total, artist_s, track_s = plex_client._score_track_match(
        wrong_song, "Bone For The Crows", "Nickelback", None, None
    )
    assert track_s == 0
    assert artist_s >= 50
    # Caller must reject: score can still be high from artist + album, but track_s == 0
    assert total >= 100


def test_score_track_match_bmth_crucify_me_prefers_solo_over_featured(plex_client: PlexClient):
    solo = {
        "title": "Crucify Me",
        "grandparentTitle": "Bring Me The Horizon",
        "parentTitle": "Sempiternal",
        "guid": "",
    }
    featured = {
        "title": "Crucify Me",
        "grandparentTitle": "Bring Me The Horizon & Draper",
        "parentTitle": "Lo-Fi",
        "guid": "",
    }
    s_solo, _, _ = plex_client._score_track_match(
        solo, "Crucify Me", "Bring Me the Horizon", None, None
    )
    s_feat, _, _ = plex_client._score_track_match(
        featured, "Crucify Me", "Bring Me the Horizon", None, None
    )
    assert s_solo > s_feat


def test_score_track_match_rejects_gore_period_vs_gore(plex_client: PlexClient):
    wrong = {
        "title": "Mean Man's Dream",
        "grandparentTitle": "gore",
        "parentTitle": "Album",
        "guid": "",
    }
    total, artist_s, track_s = plex_client._score_track_match(
        wrong, "Mean Man's Dream", "Gore.", None, None
    )
    assert artist_s == 0
    assert track_s >= 50


def test_score_track_match_optimized_gore_period_matches_library(plex_client: PlexClient):
    track = {
        "title": "mean man's dream",
        "artist": "gore.",
        "album": "album",
        "artist_guid": "",
    }
    total, artist_s, track_s = plex_client._score_track_match_optimized(
        track,
        "mean man's dream",
        "gore",
        "album",
        original_track="Mean Man's Dream",
        original_artist="Gore.",
    )
    assert artist_s == 100
    assert track_s == 100
    assert total >= 100


def test_search_for_track_escalating_prefers_exact_over_normalized(plex_client: PlexClient):
    from utils.text_normalizer import normalize_text

    cached = {
        "tracks": [
            {
                "key": "1",
                "title": "pray",
                "artist": "gore.",
                "album": "a",
                "artist_guid": "",
            },
            {
                "key": "2",
                "title": "mean man's dream",
                "artist": "gore",
                "album": "b",
                "artist_guid": "",
            },
        ],
        "artist_index": {normalize_text("gore."): ["1", "2"]},
        "track_index": {normalize_text("pray"): ["1"], normalize_text("mean man's dream"): ["2"]},
        "mbid_index": {},
    }
    plex_client.config = {"LIBRARY_CACHE_PLEX_ENABLED": True}
    ctx = {
        "display_name": "Gore.",
        "library_artist": "gore.",
        "norm": normalize_text("gore."),
        "mbids": ["mbid-1"],
        "in_lidarr": True,
    }
    result = plex_client.search_for_track_escalating("Pray", ctx, cached_data=cached)
    assert result == "1"


def test_search_cached_library_gore_period_not_wrong_gore(plex_client: PlexClient):
    from utils.text_normalizer import normalize_text

    cached = {
        "tracks": [
            {
                "key": "1",
                "title": "mean man's dream",
                "artist": "gore.",
                "album": "a",
                "artist_guid": "",
            },
            {
                "key": "2",
                "title": "other song",
                "artist": "gore",
                "album": "b",
                "artist_guid": "",
            },
        ],
        "artist_index": {"gore": ["1", "2"]},
        "track_index": {
            normalize_text("mean man's dream"): ["1"],
            normalize_text("other song"): ["2"],
        },
        "mbid_index": {},
    }
    plex_client.config = {"LIBRARY_CACHE_PLEX_ENABLED": True}
    result = plex_client.search_cached_library("Mean Man's Dream", "Gore.", cached)
    assert result == "1"
