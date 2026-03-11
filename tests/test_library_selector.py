"""Unit tests for library selector utility"""

from utils.library_selector import _first_by_lowest_key, _resolve_from_libraries


def test_first_by_lowest_key_numeric():
    libraries = [{"key": "2", "title": "B"}, {"key": "1", "title": "A"}]
    result = _first_by_lowest_key(libraries)
    assert result["key"] == "1"
    assert result["title"] == "A"


def test_first_by_lowest_key_empty():
    assert _first_by_lowest_key([]) is None


def test_first_by_lowest_key_single():
    libraries = [{"key": "5", "title": "Music"}]
    result = _first_by_lowest_key(libraries)
    assert result["key"] == "5"


def test_resolve_from_libraries_empty():
    assert _resolve_from_libraries([], None, None) is None


def test_resolve_from_libraries_single():
    libraries = [{"key": "1", "title": "Music", "type": "artist"}]
    result = _resolve_from_libraries(libraries, None, None)
    assert result["key"] == "1"
    assert result["title"] == "Music"


def test_resolve_from_libraries_prefer_music():
    libraries = [
        {"key": "2", "title": "Other"},
        {"key": "1", "title": "Music"},
    ]
    result = _resolve_from_libraries(libraries, None, None)
    assert result["title"] == "Music"


def test_resolve_from_libraries_name_override():
    libraries = [
        {"key": "1", "title": "Music"},
        {"key": "2", "title": "Custom"},
    ]
    result = _resolve_from_libraries(libraries, "Custom", None)
    assert result["title"] == "Custom"
    assert result["key"] == "2"


def test_resolve_from_libraries_name_override_not_found_falls_back():
    libraries = [
        {"key": "1", "title": "Music"},
        {"key": "2", "title": "Other"},
    ]
    result = _resolve_from_libraries(libraries, "Missing", None)
    assert result is not None
    assert result["key"] == "1"
