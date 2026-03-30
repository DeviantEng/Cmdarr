"""Unit tests for utils/track_match.py."""

from utils.text_normalizer import normalize_text
from utils.track_match import (
    collaboration_mismatch_penalty,
    normalized_artist_for_source_vs_library,
    primary_artist_segment_raw,
)


def test_primary_artist_segment_raw_splits_ampersand():
    assert primary_artist_segment_raw("Bring Me The Horizon & Draper") == "Bring Me The Horizon"


def test_primary_artist_segment_raw_feat():
    assert primary_artist_segment_raw("Bob feat. Alice") == "Bob"


def test_normalized_artist_uses_primary_when_library_has_collab():
    full_norm = normalize_text("bring me the horizon & draper")
    out = normalized_artist_for_source_vs_library(
        "Bring Me The Horizon",
        "Bring Me The Horizon & Draper",
        full_norm,
    )
    assert out == normalize_text("bring me the horizon")
    assert "draper" not in out


def test_normalized_artist_unchanged_when_source_lists_collab():
    full_norm = normalize_text("bring me the horizon & draper")
    out = normalized_artist_for_source_vs_library(
        "Bring Me The Horizon & Draper",
        "Bring Me The Horizon & Draper",
        full_norm,
    )
    assert out == full_norm
