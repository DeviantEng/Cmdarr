"""Unit tests for text normalizer"""

from utils.text_normalizer import (
    normalize_for_indexing,
    normalize_for_search,
    normalize_text,
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
