"""Unit tests for playlist URL parser"""

from utils.playlist_parser import (
    get_example_url,
    get_supported_sources,
    parse_playlist_url,
)


def test_parse_spotify_url_valid():
    result = parse_playlist_url("https://open.spotify.com/playlist/4NDXWHwYWjFmgVPkNy4YlF")
    assert result["valid"] is True
    assert result["source"] == "spotify"
    assert result["playlist_id"] == "4NDXWHwYWjFmgVPkNy4YlF"


def test_parse_spotify_url_with_query():
    result = parse_playlist_url("https://open.spotify.com/playlist/abc123?si=xyz")
    assert result["valid"] is True
    assert result["source"] == "spotify"
    assert result["playlist_id"] == "abc123"


def test_parse_deezer_url_valid():
    result = parse_playlist_url("https://www.deezer.com/en/playlist/1479458365")
    assert result["valid"] is True
    assert result["source"] == "deezer"
    assert result["playlist_id"] == "1479458365"


def test_parse_invalid_url():
    result = parse_playlist_url("https://example.com/not-a-playlist")
    assert result["valid"] is False
    assert result["source"] == "unknown"


def test_parse_playlist_url_none():
    result = parse_playlist_url(None)
    assert result["valid"] is False
    assert result["source"] == "unknown"
    assert result["playlist_id"] is None
    assert "error" in result


def test_parse_playlist_url_empty_string():
    result = parse_playlist_url("")
    assert result["valid"] is False
    assert result["source"] == "unknown"
    assert result["playlist_id"] is None


def test_parse_playlist_url_whitespace_only():
    result = parse_playlist_url("   ")
    assert result["valid"] is False
    assert result["source"] == "unknown"


def test_get_supported_sources():
    sources = get_supported_sources()
    assert sources == ["spotify", "deezer"]


def test_get_example_url_spotify():
    url = get_example_url("spotify")
    assert url is not None
    assert "open.spotify.com" in url
    assert "playlist" in url


def test_get_example_url_deezer():
    url = get_example_url("deezer")
    assert url is not None
    assert "deezer.com" in url
    assert "playlist" in url


def test_get_example_url_unknown():
    assert get_example_url("unknown") is None


def test_parse_playlist_url_exceeds_max_length():
    long_url = "https://open.spotify.com/playlist/" + "x" * 2100
    result = parse_playlist_url(long_url)
    assert result["valid"] is False
    assert result["source"] == "unknown"
    assert "length" in result.get("error", "").lower()
