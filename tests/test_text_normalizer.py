"""Unit tests for text normalizer"""

from utils.text_normalizer import (
    has_edition_suffix,
    normalize_for_indexing,
    normalize_for_search,
    normalize_text,
    prefer_base_releases,
    strip_edition_suffix,
)


def test_normalize_text_motorhead():
    assert normalize_text("Motörhead") == "motorhead"


def test_normalize_text_curly_apostrophe():
    # \u2019 is right single quotation mark
    assert normalize_text("don\u2019t") == "don't"


def test_normalize_text_left_apostrophe():
    # \u2018 is left single quotation mark
    assert normalize_text("it\u2018s") == "it's"


def test_normalize_text_none():
    assert normalize_text(None) == ""


def test_normalize_text_empty_string():
    assert normalize_text("") == ""


def test_normalize_text_unicode_dashes():
    # \u2013 en-dash, \u2014 em-dash
    assert normalize_text("foo\u2013bar") == "foo-bar"
    assert normalize_text("foo\u2014bar") == "foo-bar"


def test_normalize_text_strips_whitespace():
    assert normalize_text("  hello world  ") == "hello world"


def test_normalize_text_lowercase():
    assert normalize_text("HELLO") == "hello"


def test_normalize_for_search_alias():
    assert normalize_for_search("Motörhead") == "motorhead"


def test_normalize_for_indexing_alias():
    assert normalize_for_indexing("Motörhead") == "motorhead"


def test_strip_edition_suffix_extended():
    assert strip_edition_suffix("Album (Extended)") == "Album"


def test_has_edition_suffix_base():
    assert has_edition_suffix("Album") is False
    assert has_edition_suffix("My Album Title") is False


def test_has_edition_suffix_extended():
    assert has_edition_suffix("Album (Extended)") is True
    assert has_edition_suffix("Album (Deluxe Edition)") is True


def test_prefer_base_releases_single():
    albums = [{"name": "Album", "release_date": "2024-01-01"}]
    assert prefer_base_releases(albums) == albums


def test_prefer_base_releases_base_wins():
    albums = [
        {"name": "Album", "release_date": "2024-01-01", "spotify_url": "https://spotify.com/base"},
        {"name": "Album (Extended)", "release_date": "2024-01-01", "spotify_url": "https://spotify.com/ext"},
    ]
    result = prefer_base_releases(albums)
    assert len(result) == 1
    assert result[0]["name"] == "Album"
    assert result[0]["spotify_url"] == "https://spotify.com/base"


def test_prefer_base_releases_no_base_keeps_first():
    albums = [
        {"name": "Album (Extended)", "release_date": "2024-01-01"},
        {"name": "Album (Deluxe)", "release_date": "2024-01-01"},
    ]
    result = prefer_base_releases(albums)
    assert len(result) == 1
    assert result[0]["name"] == "Album (Extended)"
