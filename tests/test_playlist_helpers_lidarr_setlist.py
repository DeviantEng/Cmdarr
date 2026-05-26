"""Pure helpers for Lidarr-backed Setlist.fm MBID resolution (no DB/network)."""

from commands.playlist_generator_helpers import index_lidarr_artist_mbids_by_norm
from utils.text_normalizer import normalize_text


def test_index_lidarr_dedupes_same_mbid():
    d = index_lidarr_artist_mbids_by_norm(
        [
            ("The Home Team", "mbid-a"),
            ("The Home Team", "mbid-a"),
            ("Another", "mbid-b"),
        ]
    )
    assert d[normalize_text("The Home Team")] == ["mbid-a"]
    assert d[normalize_text("Another")] == ["mbid-b"]


def test_index_lidarr_multiple_mbids_same_norm_sorted():
    d = index_lidarr_artist_mbids_by_norm(
        [
            ("Dup", "z-last"),
            ("Dup", "a-first"),
        ]
    )
    assert d[normalize_text("Dup")] == ["a-first", "z-last"]


def test_index_lidarr_skips_blank():
    assert index_lidarr_artist_mbids_by_norm([("", "x"), ("y", "")]) == {}
