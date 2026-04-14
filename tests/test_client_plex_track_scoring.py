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
