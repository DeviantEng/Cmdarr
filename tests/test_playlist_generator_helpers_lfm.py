"""Tests for Last.fm similar playlist merge helpers (no network)."""

from commands.playlist_generator_helpers import (
    build_lfm_similar_artist_pool,
    merge_similar_round_robin,
)


def test_merge_similar_round_robin_interleaves_and_dedupes():
    a = [
        {"name": "One", "match": "0.9"},
        {"name": "Three", "match": "0.8"},
    ]
    b = [
        {"name": "Two", "match": "0.85"},
        {"name": "One", "match": "0.7"},
    ]
    out = merge_similar_round_robin([a, b], max_artists=10)
    names = [r["name"] for r in out]
    assert names == ["One", "Two", "Three"]


def test_merge_similar_round_robin_respects_cap():
    a = [{"name": f"A{i}", "match": "0.5"} for i in range(5)]
    b = [{"name": f"B{i}", "match": "0.5"} for i in range(5)]
    out = merge_similar_round_robin([a, b], max_artists=3)
    assert len(out) == 3
    assert out[0]["name"] == "A0"
    assert out[1]["name"] == "B0"
    assert out[2]["name"] == "A1"


def test_build_lfm_similar_artist_pool_include_seeds_and_round_robin():
    seeds = ["SeedA", "SeedB"]
    per = [
        [{"name": "X1", "match": "0.9"}, {"name": "X2", "match": "0.8"}],
        [{"name": "Y1", "match": "0.85"}],
    ]
    out = build_lfm_similar_artist_pool(seeds, per, include_seeds=True, max_artists=10)
    names = [r["name"] for r in out]
    assert names[0] == "SeedA"
    assert names[1] == "SeedB"
    assert "X1" in names and "Y1" in names


def test_build_lfm_similar_artist_pool_seeds_only_when_max_small():
    seeds = ["A", "B", "C"]
    per = [[{"name": "Z", "match": "1"}]]
    out = build_lfm_similar_artist_pool(seeds, per, include_seeds=True, max_artists=2)
    assert [r["name"] for r in out] == ["A", "B"]
