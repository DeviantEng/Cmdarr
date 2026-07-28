"""Tests for Last.fm / Plex lookup ordering and validation helpers."""

from utils.text_normalizer import normalize_text
from utils.track_match import lastfm_query_plan, lastfm_tracks_match_artist, plex_search_variants


def test_lastfm_query_plan_mbid_then_exact_then_normalized():
    plan = lastfm_query_plan("Gore.", "gore.", normalize_text("gore."), ["mbid-1"])
    labels = [label for _, _, label in plan]
    assert labels[0] == "mbid"
    assert "exact" in labels
    assert labels.index("mbid") < labels.index("exact")


def test_lastfm_query_plan_skips_redundant_normalized_when_exact_covers_norm():
    norm = normalize_text("landmvrks")
    plan = lastfm_query_plan("LANDMVRKS", "landmvrks", norm, [])
    labels = [label for _, _, label in plan]
    assert labels == ["exact"]
    assert "normalized" not in labels


def test_plex_search_variants_order():
    ctx = {
        "display_name": "Gore.",
        "library_artist": "gore.",
        "norm": normalize_text("gore."),
        "mbids": ["mbid-1"],
        "in_lidarr": True,
    }
    variants = plex_search_variants(ctx)
    labels = [label for _, _, label in variants]
    assert labels[0].startswith("mbid")
    assert "exact" in labels
    assert labels.index("mbid_exact") < labels.index("exact")


def test_lastfm_tracks_match_artist_rejects_wrong_gore():
    tracks = [{"name": "Mean Man's Dream", "artist": "gore"}]
    assert not lastfm_tracks_match_artist(tracks, "Gore.", "gore.")
    tracks_ok = [{"name": "Pray", "artist": "gore."}]
    assert lastfm_tracks_match_artist(tracks_ok, "Gore.", "gore.")
