"""Tests for Spotify playlist ID classification."""

from utils.spotify_playlist_detector import SpotifyPlaylistDetector


def test_is_user_generated_playlist():
    assert SpotifyPlaylistDetector.is_user_generated_playlist("37i9dQZF1EP6YuccBxUcC1") is True
    assert SpotifyPlaylistDetector.is_user_generated_playlist("public-playlist-id") is False


def test_get_playlist_info_known_and_generated():
    daylist = SpotifyPlaylistDetector.get_playlist_info("37i9dQZF1EP6YuccBxUcC1")
    assert daylist["name"] == "Daylist"
    assert daylist["type"] == "spotify_generated"

    generated = SpotifyPlaylistDetector.get_playlist_info("37i9dQZF1Eunknown000000")
    assert generated["type"] == "spotify_generated"
    assert generated["requires_listening_history"] is True

    public = SpotifyPlaylistDetector.get_playlist_info("spotify:playlist:abc123")
    assert public["type"] == "public"
    assert public["requires_listening_history"] is False


def test_requires_user_auth():
    assert SpotifyPlaylistDetector.requires_user_auth("37i9dQZF1EP6YuccBxUcC1") is True
    assert SpotifyPlaylistDetector.requires_user_auth("abc") is False
