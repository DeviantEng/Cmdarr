"""Tests for playlist artist resolution helpers."""

from commands.playlist_generator_helpers import (
    ResolvedArtist,
    resolve_artist_track_keys,
    resolve_validated_artists,
)
from utils.text_normalizer import normalize_text


def _cache_with_gore_artists() -> dict:
    tracks = [
        {
            "key": "1",
            "artist": "gore.",
            "title": "mean man's dream",
            "album": "a",
            "artist_guid": "",
        },
        {"key": "2", "artist": "gore", "title": "other song", "album": "b", "artist_guid": ""},
    ]
    norm = normalize_text("gore.")
    return {
        "tracks": tracks,
        "artist_index": {norm: ["1", "2"]},
        "track_index": {},
        "mbid_index": {},
    }


def test_resolve_validated_artists_picks_library_gore_period():
    cached = _cache_with_gore_artists()
    lidarr_pairs = [("Gore.", "f5d4e4ae-90b8-4b30-aa74-a9bf36170bd4")]
    resolved, invalid = resolve_validated_artists(["Gore."], cached, lidarr_pairs=lidarr_pairs)
    assert invalid == []
    assert len(resolved) == 1
    assert resolved[0].display_name == "Gore."
    assert resolved[0].mbids == ["f5d4e4ae-90b8-4b30-aa74-a9bf36170bd4"]
    assert resolved[0].library_artist == "gore."


def test_resolve_artist_track_keys_filters_wrong_gore():
    cached = _cache_with_gore_artists()
    resolved = ResolvedArtist(
        display_name="Gore.",
        norm=normalize_text("gore."),
        mbids=["f5d4e4ae-90b8-4b30-aa74-a9bf36170bd4"],
        library_artist="gore.",
    )
    keys = resolve_artist_track_keys(cached, resolved)
    assert keys == ["1"]
