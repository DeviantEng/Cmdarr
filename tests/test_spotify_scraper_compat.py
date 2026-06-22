"""Tests for scraper album normalization helpers."""

from clients.client_spotify import (
    _normalize_scraper_album,
    _normalize_scraper_discography_release,
    _normalize_scraper_owner,
    _normalize_scraper_tracks,
    _parse_scraper_discography_date,
    _scraper_album_type_in_groups,
    _scraper_playlist_result,
    _spotify_discography_album_type,
)


def test_parse_scraper_discography_date_day_precision():
    release_date, precision = _parse_scraper_discography_date(
        {"isoString": "2024-03-15T00:00:00Z", "precision": "DAY", "year": 2024}
    )
    assert release_date == "2024-03-15"
    assert precision == "day"


def test_normalize_scraper_discography_release_maps_nrd_fields():
    album = _normalize_scraper_discography_release(
        {
            "id": "abc123",
            "name": "Test Album",
            "type": "EP",
            "date": {"isoString": "2024-03-15T00:00:00Z", "precision": "DAY", "year": 2024},
            "tracks": {"totalCount": 5},
            "sharingInfo": {"shareUrl": "https://open.spotify.com/album/abc123"},
        },
        "artist1",
    )
    assert album is not None
    assert album["id"] == "abc123"
    assert album["album_type"] == "ep"
    assert album["total_tracks"] == 5
    assert album["primary_artist_id"] == "artist1"
    assert album["spotify_url"] == "https://open.spotify.com/album/abc123"


def test_spotify_discography_album_type_mapping():
    assert _spotify_discography_album_type("SINGLE") == "single"
    assert _spotify_discography_album_type("ALBUM") == "album"


def test_scraper_album_type_in_groups_includes_ep_with_album_group():
    groups = "album,single,compilation,appears_on"
    assert _scraper_album_type_in_groups("ep", groups) is True
    assert _scraper_album_type_in_groups("podcast", groups) is False


def test_normalize_scraper_album_maps_nrd_fields():
    album = _normalize_scraper_album(
        {
            "id": "abc123",
            "name": "Test Album",
            "release_date": "2024-03-15",
            "album_type": "album",
            "total_tracks": 10,
            "share_url": "https://open.spotify.com/album/abc123",
            "artists": [{"id": "artist1", "name": "Artist One"}],
        },
        fallback_artist_id="fallback",
    )
    assert album["id"] == "abc123"
    assert album["name"] == "Test Album"
    assert album["release_date"] == "2024-03-15"
    assert album["album_type"] == "album"
    assert album["total_tracks"] == 10
    assert album["primary_artist_id"] == "artist1"
    assert album["spotify_url"] == "https://open.spotify.com/album/abc123"
    assert album["external_url"] == album["spotify_url"]


def test_normalize_scraper_album_builds_url_when_share_missing():
    album = _normalize_scraper_album({"id": "xyz", "name": "No URL"}, fallback_artist_id="a1")
    assert album["spotify_url"] == "https://open.spotify.com/album/xyz"
    assert album["primary_artist_id"] == "a1"


def test_scraper_album_type_in_groups():
    groups = "album,single,compilation,appears_on"
    assert _scraper_album_type_in_groups("album", groups) is True
    assert _scraper_album_type_in_groups("single", groups) is True
    assert _scraper_album_type_in_groups("podcast", groups) is False


def test_normalize_scraper_tracks_v2_shape():
    tracks = _normalize_scraper_tracks(
        [
            {
                "name": "Song A",
                "artists": [{"name": "Artist One"}],
                "album": {"name": "Album A"},
            }
        ]
    )
    assert tracks == [{"artist": "artist one", "track": "song a", "album": "album a"}]


def test_normalize_scraper_tracks_v3_shape():
    tracks = _normalize_scraper_tracks(
        [
            {
                "track": {
                    "name": "Song B",
                    "artists": [{"name": "Artist Two"}],
                    "album": {"name": "Album B"},
                },
                "added_at": "2026-01-01T00:00:00+00:00",
            }
        ]
    )
    assert tracks == [{"artist": "artist two", "track": "song b", "album": "album b"}]


def test_normalize_scraper_owner_accepts_v2_and_v3_fields():
    assert _normalize_scraper_owner({"display_name": "Alice", "id": "alice"}) == "Alice"
    assert _normalize_scraper_owner({"name": "Spotify", "uri": "spotify:user:spotify"}) == "Spotify"


def test_scraper_playlist_result_uses_total_tracks_when_present():
    result = _scraper_playlist_result(
        {
            "name": "Test Playlist",
            "description": "desc",
            "owner": {"name": "Owner"},
            "total_tracks": 120,
            "tracks": [
                {"name": "Song", "artists": [{"name": "Artist"}], "album": {"name": "Album"}},
            ],
        }
    )
    assert result["success"] is True
    assert result["track_count"] == 1
    assert result["total_tracks"] == 120
    assert result["owner"] == "Owner"
