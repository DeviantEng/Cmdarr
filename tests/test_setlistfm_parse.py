"""Tests for commands.setlistfm_parse — setlist.fm JSON → ordered titles."""

from __future__ import annotations

import pytest

from commands.setlistfm_parse import (
    extract_ordered_songs_from_setlist,
    first_non_empty_setlist,
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
