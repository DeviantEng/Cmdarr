from clients.client_spotify import (
    _normalize_scraper_owner,
    _normalize_scraper_tracks,
    _scraper_playlist_result,
)


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
