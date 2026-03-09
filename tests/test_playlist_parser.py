"""Unit tests for playlist URL parser"""
import pytest
from utils.playlist_parser import parse_playlist_url


def test_parse_spotify_url_valid():
    result = parse_playlist_url(
        "https://open.spotify.com/playlist/4NDXWHwYWjFmgVPkNy4YlF"
    )
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
