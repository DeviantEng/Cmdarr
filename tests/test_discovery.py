"""Unit tests for discovery utilities"""

import random
from unittest.mock import MagicMock

from utils.discovery import DiscoveryUtils


def _make_utils():
    return DiscoveryUtils(config=MagicMock(), lidarr_client=MagicMock())


def test_filter_artist_candidate_already_in_lidarr_mbid():
    utils = _make_utils()
    existing_mbids = {"mbid-123"}
    existing_names = set()
    excluded_mbids = set()
    should_include, reason = utils.filter_artist_candidate(
        "mbid-123", "Artist Name", existing_mbids, existing_names, excluded_mbids
    )
    assert should_include is False
    assert reason == "already_in_lidarr_mbid"


def test_filter_artist_candidate_already_in_lidarr_name():
    utils = _make_utils()
    existing_mbids = set()
    existing_names = {"artist name"}
    excluded_mbids = set()
    should_include, reason = utils.filter_artist_candidate(
        "mbid-456", "Artist Name", existing_mbids, existing_names, excluded_mbids
    )
    assert should_include is False
    assert reason == "already_in_lidarr_name"


def test_filter_artist_candidate_in_exclusions():
    utils = _make_utils()
    existing_mbids = set()
    existing_names = set()
    excluded_mbids = {"mbid-789"}
    should_include, reason = utils.filter_artist_candidate(
        "mbid-789", "New Artist", existing_mbids, existing_names, excluded_mbids
    )
    assert should_include is False
    assert reason == "in_exclusions"


def test_filter_artist_candidate_valid():
    utils = _make_utils()
    existing_mbids = set()
    existing_names = set()
    excluded_mbids = set()
    should_include, reason = utils.filter_artist_candidate(
        "mbid-new", "New Artist", existing_mbids, existing_names, excluded_mbids
    )
    assert should_include is True
    assert reason == "valid"


def test_apply_random_sampling_limit_zero():
    utils = _make_utils()
    candidates = [{"id": 1}, {"id": 2}, {"id": 3}]
    sampled, limited_count, applied = utils.apply_random_sampling(candidates, 0, "test")
    assert sampled == candidates
    assert limited_count == 0
    assert applied is False


def test_apply_random_sampling_candidates_under_limit():
    utils = _make_utils()
    candidates = [{"id": 1}, {"id": 2}]
    sampled, limited_count, applied = utils.apply_random_sampling(candidates, 5, "test")
    assert sampled == candidates
    assert limited_count == 0
    assert applied is False


def test_apply_random_sampling_applies_shuffle_and_slice():
    utils = _make_utils()
    random.seed(42)
    candidates = [{"id": i} for i in range(10)]
    sampled, limited_count, applied = utils.apply_random_sampling(candidates, 3, "test")
    assert len(sampled) == 3
    assert limited_count == 7
    assert applied is True
    assert all(c in candidates for c in sampled)


def test_deduplicate_by_mbid_keeps_highest_score():
    utils = _make_utils()
    artists = [
        {"MusicBrainzId": "mbid-1", "ArtistName": "A", "match": "0.5"},
        {"MusicBrainzId": "mbid-1", "ArtistName": "A", "match": "0.9"},
        {"MusicBrainzId": "mbid-1", "ArtistName": "A", "match": "0.9"},
    ]
    result = utils.deduplicate_by_mbid(artists, "match")
    assert len(result) == 1
    assert result[0]["match"] == "0.9"


def test_deduplicate_by_mbid_multiple_artists():
    utils = _make_utils()
    artists = [
        {"MusicBrainzId": "mbid-1", "ArtistName": "A", "match": "0.5"},
        {"MusicBrainzId": "mbid-2", "ArtistName": "B", "match": "0.8"},
    ]
    result = utils.deduplicate_by_mbid(artists, "match")
    assert len(result) == 2


def test_create_artist_entry():
    utils = _make_utils()
    entry = utils.create_artist_entry("mbid-1", "Artist Name", "source")
    assert entry["MusicBrainzId"] == "mbid-1"
    assert entry["ArtistName"] == "Artist Name"
    assert entry["source"] == "source"


def test_create_artist_entry_with_kwargs():
    utils = _make_utils()
    entry = utils.create_artist_entry(
        "mbid-1", "Artist Name", "source", track_title="Song", extra=None
    )
    assert entry["track_title"] == "Song"
    assert "extra" not in entry
