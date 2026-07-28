"""Tests for playlist artist resolution helpers."""

import pytest

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


def test_resolve_validated_artists_dedupes_duplicate_norms():
    plot_norm = normalize_text("the plot in you")
    cached = {
        "tracks": [
            {"key": "1", "artist": "gore.", "title": "a", "album": "", "artist_guid": ""},
            {"key": "2", "artist": "the plot in you", "title": "b", "album": "", "artist_guid": ""},
        ],
        "artist_index": {normalize_text("gore."): ["1"], plot_norm: ["2"]},
        "track_index": {},
        "mbid_index": {},
    }
    lidarr_pairs = [("Gore.", "f5d4e4ae-90b8-4b30-aa74-a9bf36170bd4")]
    resolved, invalid = resolve_validated_artists(
        ["The Plot In You", "The Plot in You", "Gore."],
        cached,
        lidarr_pairs=lidarr_pairs,
    )
    assert invalid == []
    assert len(resolved) == 2
    assert resolved[0].display_name == "The Plot In You"
    assert resolved[1].display_name == "Gore."


@pytest.mark.asyncio
async def test_fetch_top_tracks_for_artist_tries_mbid_then_exact_name():
    from commands.playlist_generator_helpers import fetch_top_tracks_for_artist

    class FakeLastFM:
        calls: list[tuple[str | None, str | None]] = []

        async def get_top_tracks(self, artist_name, limit=10, *, mbid=None):
            FakeLastFM.calls.append((artist_name, mbid))
            if mbid:
                return []
            if artist_name == "Gore.":
                return [{"name": "Pray", "artist": "gore."}]
            return []

    resolved = ResolvedArtist(
        display_name="Gore.",
        norm=normalize_text("gore."),
        mbids=["f5d4e4ae-90b8-4b30-aa74-a9bf36170bd4"],
        library_artist="gore.",
    )
    logger = __import__("logging").getLogger("test.fetch")
    FakeLastFM.calls = []
    rows, source = await fetch_top_tracks_for_artist(
        resolved,
        lastfm_client=FakeLastFM(),
        plex_client=None,
        library_key=None,
        cached_data=_cache_with_gore_artists(),
        limit=5,
        logger=logger,
    )
    assert source == "lastfm_exact"
    assert len(rows) == 1
    assert rows[0]["track"] == "Pray"
    assert "match_context" in rows[0]
    assert FakeLastFM.calls[0][1] == "f5d4e4ae-90b8-4b30-aa74-a9bf36170bd4"
    assert FakeLastFM.calls[1] == ("Gore.", None)


@pytest.mark.asyncio
async def test_fetch_top_tracks_for_artist_plex_fallback():
    from commands.playlist_generator_helpers import fetch_top_tracks_for_artist

    class FakeLastFM:
        async def get_top_tracks(self, artist_name, limit=10, *, mbid=None):
            return []

    class FakePlex:
        def search_for_track_escalating(
            self, track_name, match_context, cached_data=None, album_name=""
        ):
            return None

        def get_artist_rating_key_from_track(self, track_key):
            return "artist-1"

        def get_artist_popular_tracks(self, library_key, artist_rk, limit=10):
            return [
                {
                    "key": "99",
                    "title": "Mean Man's Dream",
                    "artist": "gore.",
                    "album": "Album",
                }
            ]

    resolved = ResolvedArtist(
        display_name="Gore.",
        norm=normalize_text("gore."),
        mbids=["f5d4e4ae-90b8-4b30-aa74-a9bf36170bd4"],
        library_artist="gore.",
    )
    logger = __import__("logging").getLogger("test.fetch")
    rows, source = await fetch_top_tracks_for_artist(
        resolved,
        lastfm_client=FakeLastFM(),
        plex_client=FakePlex(),
        library_key="7",
        cached_data=_cache_with_gore_artists(),
        limit=5,
        logger=logger,
    )
    assert source == "plex"
    assert len(rows) == 1
    assert rows[0]["rating_key"] == "99"
    assert rows[0]["track"] == "Mean Man's Dream"


@pytest.mark.asyncio
async def test_fetch_top_tracks_for_artist_attaches_rating_keys_from_lastfm():
    from commands.playlist_generator_helpers import fetch_top_tracks_for_artist

    class FakeLastFM:
        async def get_top_tracks(self, artist_name, limit=10, *, mbid=None):
            if mbid:
                return []
            if artist_name == "Gore.":
                return [
                    {"name": "Pray", "artist": "gore.", "album": "A"},
                    {"name": "Wrath", "artist": "gore.", "album": "A"},
                ]
            return []

    class FakePlex:
        def __init__(self):
            self.search_calls = 0

        def search_for_track_escalating(
            self, track_name, match_context, cached_data=None, album_name=""
        ):
            self.search_calls += 1
            return {"Pray": "101", "Wrath": "102"}.get(track_name)

    resolved = ResolvedArtist(
        display_name="Gore.",
        norm=normalize_text("gore."),
        mbids=["f5d4e4ae-90b8-4b30-aa74-a9bf36170bd4"],
        library_artist="gore.",
    )
    plex = FakePlex()
    logger = __import__("logging").getLogger("test.fetch")
    rows, source = await fetch_top_tracks_for_artist(
        resolved,
        lastfm_client=FakeLastFM(),
        plex_client=plex,
        library_key="7",
        cached_data=_cache_with_gore_artists(),
        limit=5,
        logger=logger,
    )
    assert source == "lastfm_exact"
    assert len(rows) == 2
    assert rows[0]["rating_key"] == "101"
    assert rows[1]["rating_key"] == "102"
    assert plex.search_calls == 2


@pytest.mark.asyncio
async def test_fetch_top_tracks_for_artists_parallel_preserves_order():
    from commands.playlist_generator_helpers import fetch_top_tracks_for_artists_parallel

    class FakeLastFM:
        async def get_top_tracks(self, artist_name, limit=10, *, mbid=None):
            return [{"name": f"Track-{artist_name}", "artist": artist_name}]

    resolved_a = ResolvedArtist(
        display_name="A",
        norm=normalize_text("a"),
        mbids=[],
        library_artist="a",
    )
    resolved_b = ResolvedArtist(
        display_name="B",
        norm=normalize_text("b"),
        mbids=[],
        library_artist="b",
    )
    logger = __import__("logging").getLogger("test.parallel")
    results = await fetch_top_tracks_for_artists_parallel(
        [resolved_a, resolved_b],
        lastfm_client=FakeLastFM(),
        plex_client=None,
        library_key=None,
        cached_data=None,
        limit=1,
        logger=logger,
        concurrency=2,
    )
    assert len(results) == 2
    assert results[0][0][0]["track"] == "Track-A"
    assert results[1][0][0]["track"] == "Track-B"
