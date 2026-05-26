"""Tests for commands.setlistfm_parse — setlist.fm JSON → ordered titles."""

from __future__ import annotations

from datetime import date

import pytest

from commands.setlistfm_parse import (
    STUB_TRACK_THRESHOLD,
    TARGET_SUBSTANTIAL_SETLISTS,
    choose_repr_setlist_for_playlist,
    dedupe_by_event_key,
    event_within_lookback_days,
    extract_ordered_songs_from_setlist,
    finalize_candidate_pool_after_scan,
    first_non_empty_setlist,
    mbids_from_artist_search,
    pick_best_setlist_for_block,
    pick_setlist_for_block,
)


def _song(name: str, *, tape: bool = False) -> dict:
    d: dict = {"name": name}
    if tape:
        d["tape"] = True
    return d


def test_extract_ordered_songs_empty_and_missing_sets():
    assert extract_ordered_songs_from_setlist({}) == []
    assert extract_ordered_songs_from_setlist({"sets": None}) == []
    assert extract_ordered_songs_from_setlist({"sets": {}}) == []
    assert extract_ordered_songs_from_setlist({"sets": {"set": None}}) == []


def test_extract_ordered_songs_single_set_list_of_songs():
    sl = {
        "sets": {
            "set": {
                "song": [
                    _song("  Opener  "),
                    _song(""),
                    _song("   "),
                    _song("Main", tape=True),
                    _song("Closer"),
                ]
            }
        }
    }
    assert extract_ordered_songs_from_setlist(sl) == ["Opener", "Closer"]


def test_extract_ordered_songs_wraps_singleton_set_as_list():
    sl = {
        "sets": {
            "set": {
                "@name": "Main",
                "song": _song("Solo Dict"),
            }
        }
    }
    assert extract_ordered_songs_from_setlist(sl) == ["Solo Dict"]


def test_extract_ordered_songs_multiple_sets_preserves_order():
    sl = {
        "sets": {
            "set": [
                {"song": [_song("A"), _song("B")]},
                {"song": _song("C")},
                {"song": []},
                {"song": [_song("D")]},
            ]
        }
    }
    assert extract_ordered_songs_from_setlist(sl) == ["A", "B", "C", "D"]


def test_extract_ordered_songs_skips_non_dict_segments():
    sl = {"sets": {"set": [{"song": ["not-a-dict", _song("OK"), None, {}]}]}}
    assert extract_ordered_songs_from_setlist(sl) == ["OK"]


def test_first_non_empty_setlist_none_when_missing_or_empty_page():
    assert first_non_empty_setlist({}) is None
    assert first_non_empty_setlist({"setlist": []}) is None


def test_first_non_empty_setlist_prefers_first_with_songs():
    empty = {"id": "1", "sets": {"set": {"song": _song("", tape=False)}}}
    nonempty = {"id": "2", "sets": {"set": {"song": _song("Track One")}}}
    page = {"setlist": [empty, nonempty]}
    assert first_non_empty_setlist(page) == nonempty


def test_first_non_empty_setlist_single_dict_setlist_wrap():
    sl = {"id": "x", "sets": {"set": {"song": _song("Only")}}}
    page = {"setlist": sl}
    assert first_non_empty_setlist(page) == sl


def test_pick_setlist_prefer_non_empty_skips_first_if_empty():
    first = {"id": "a", "sets": {"set": {}}}
    second = {"id": "b", "sets": {"set": {"song": _song("Hit")}}}
    page = {"setlist": [first, second]}
    chosen = pick_setlist_for_block(page, prefer_non_empty=True)
    assert chosen == second


def test_pick_setlist_prefer_non_empty_fallback_to_first():
    empty = {"id": "only", "sets": {"set": {"song": []}}}
    page = {"setlist": [empty]}
    assert pick_setlist_for_block(page, prefer_non_empty=True) == empty


def test_pick_setlist_when_prefer_disabled_returns_first_even_if_later_nonempty():
    first = {"id": "a", "sets": {"set": {}}}
    second = {"id": "b", "sets": {"set": {"song": _song("Hit")}}}
    page = {"setlist": [first, second]}
    assert pick_setlist_for_block(page, prefer_non_empty=False) == first


def test_pick_setlist_returns_none_when_no_entries():
    assert pick_setlist_for_block({}, prefer_non_empty=True) is None
    assert pick_setlist_for_block({"setlist": None}, prefer_non_empty=False) is None


@pytest.mark.parametrize(
    "raw_setlist_field,expected_titles",
    [
        pytest.param([{"sets": {"set": {"song": _song("Listed")}}}], ["Listed"], id="list"),
        pytest.param({"sets": {"set": {"song": _song("Single")}}}, ["Single"], id="dict"),
    ],
)
def test_setlist_page_accepts_dict_or_list_setlist(raw_setlist_field, expected_titles):
    page = {"setlist": raw_setlist_field}
    picked = first_non_empty_setlist(page)
    assert picked is not None
    assert extract_ordered_songs_from_setlist(picked) == expected_titles


def _sl_with_date(event_date: str, n_songs: int) -> dict:
    return {
        "eventDate": event_date,
        "sets": {"set": {"song": [_song(f"T{i}") for i in range(n_songs)]}},
    }


def test_pick_best_prefers_newer_event_date():
    older = _sl_with_date("15-04-2026", 6)
    newer = _sl_with_date("01-05-2026", 12)
    page = {"setlist": [older, newer]}
    assert pick_best_setlist_for_block(page) == newer


def test_pick_best_same_day_prefers_longer_setlist():
    shorter = _sl_with_date("01-05-2026", 6)
    longer = _sl_with_date("01-05-2026", 12)
    page = {"setlist": [shorter, longer]}
    assert pick_best_setlist_for_block(page) == longer


def test_pick_best_orders_independent_of_list_order():
    newer = _sl_with_date("01-05-2026", 12)
    older = _sl_with_date("15-04-2026", 6)
    page = {"setlist": [newer, older]}
    assert pick_best_setlist_for_block(page) == newer


def test_pick_best_returns_none_when_no_songs():
    page = {"setlist": [{"eventDate": "01-05-2026", "sets": {"set": {}}}]}
    assert pick_best_setlist_for_block(page) is None


def test_event_within_lookback():
    today = date(2026, 7, 1)
    ok = {"eventDate": "01-05-2026", "sets": {"set": {"song": [_song("A")]}}}
    old = {"eventDate": "01-05-2024", "sets": {"set": {"song": [_song("A")]}}}
    future = {"eventDate": "01-06-2030", "sets": {"set": {"song": [_song("A")]}}}
    assert event_within_lookback_days(ok, today=today)
    assert not event_within_lookback_days(old, today=today)
    assert not event_within_lookback_days(future, today=today)


def test_event_within_lookback_accepts_iso_event_date():
    today = date(2026, 7, 1)
    ok = {"eventDate": "2026-05-01", "sets": {"set": {"song": [_song("A")]}}}
    assert event_within_lookback_days(ok, today=today)


def test_pick_best_prefers_newer_event_date_iso_format():
    older = _sl_with_date("2026-04-15", 6)
    newer = _sl_with_date("2026-05-01", 12)
    page = {"setlist": [older, newer]}
    assert pick_best_setlist_for_block(page) == newer


def test_pick_best_iso_vs_dd_mm_orders_by_calendar_day():
    iso_newer = _sl_with_date("2026-06-01", 8)
    dd_mm = _sl_with_date("15-05-2026", 20)
    page = {"setlist": [dd_mm, iso_newer]}
    assert pick_best_setlist_for_block(page) == iso_newer


def test_finalize_prefers_stub_full_pool_empty():
    substantial: list = []
    stub = [_sl_with_date("02-06-2026", 3), _sl_with_date("01-06-2026", 3)]
    pool = finalize_candidate_pool_after_scan(substantial, stub)
    assert pool[0]["eventDate"] == "02-06-2026"


def test_choose_repr_median_prefers_near_typical_depth():
    p10 = _sl_with_date("01-01-2026", 10)
    p12 = _sl_with_date("02-01-2026", 12)
    p14 = _sl_with_date("03-01-2026", 14)
    # median 12; 12 wins over 10 distance 2 vs 14 distance 2 then longer ordinal — same dist pick longer
    assert choose_repr_setlist_for_playlist([p10, p12, p14]) == p12


def test_dedupe_by_event_id_keeps_single():
    a = dict(_sl_with_date("01-05-2026", 4), **{"id": "abc"})
    b = dict(_sl_with_date("01-05-2026", 4), **{"id": "abc"})
    assert len(dedupe_by_event_key([a, b])) == 1


def test_stub_threshold_constant_aligned_with_resolver():
    assert STUB_TRACK_THRESHOLD == 3
    assert TARGET_SUBSTANTIAL_SETLISTS == 5


def test_mbids_from_artist_search_collects_duplicate_names_in_order():
    data = {
        "artist": [
            {"name": "The Home Team", "mbid": "canadian-wrong-era"},
            {"name": "The Home Team", "mbid": "seattle-good"},
            {"name": "The Home Team feat. Guest", "mbid": "should-not-match"},
        ]
    }
    assert mbids_from_artist_search(data, "The Home Team") == [
        "canadian-wrong-era",
        "seattle-good",
    ]


def test_mbids_from_artist_search_exact_match_is_case_insensitive():
    data = {"artist": [{"name": " Muse ", "mbid": "m-id"}]}
    assert mbids_from_artist_search(data, " muse") == ["m-id"]


def test_mbids_from_artist_search_dedupes_mbid():
    data = {
        "artist": [
            {"name": "Dup", "mbid": "same"},
            {"name": "Dup", "mbid": "same"},
        ]
    }
    assert mbids_from_artist_search(data, "Dup") == ["same"]


def test_mbids_from_artist_search_falls_back_to_first_row_when_no_exact_name_match():
    data = {"artist": [{"name": "The Home Team & Broadside", "mbid": "collab"}, {"mbid": ""}]}
    assert mbids_from_artist_search(data, "The Home Team") == ["collab"]
