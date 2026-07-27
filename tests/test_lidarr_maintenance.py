"""Unit tests for Lidarr maintenance helpers."""

from utils.lidarr_maintenance import (
    album_matches_types,
    extract_album_ids_from_history,
    extract_album_ids_from_queue,
    map_lidarr_album_type,
    normalize_album_types,
    normalize_wanted_record,
    resolve_sort,
)


def test_normalize_album_types_defaults_and_filters():
    assert normalize_album_types(None) == {"album"}
    assert normalize_album_types("") == {"album"}
    assert normalize_album_types("album,ep,bogus") == {"album", "ep"}
    assert normalize_album_types(["Single", "OTHER"]) == {"single", "other"}


def test_map_lidarr_album_type():
    assert map_lidarr_album_type("Album") == "album"
    assert map_lidarr_album_type("EP") == "ep"
    assert map_lidarr_album_type("Single") == "single"
    assert map_lidarr_album_type("Broadcast") == "other"
    assert map_lidarr_album_type(None) == "other"


def test_album_matches_types():
    assert album_matches_types("Album", {"album"})
    assert not album_matches_types("EP", {"album"})
    assert album_matches_types("Remix", {"other"})


def test_resolve_sort():
    assert resolve_sort("oldest_release_date") == ("releaseDate", "ascending")
    assert resolve_sort("newest_release_date") == ("releaseDate", "descending")
    assert resolve_sort("unknown") == ("releaseDate", "ascending")


def test_extract_album_ids_from_queue_and_history():
    queue = [{"albumId": 1}, {"album": {"id": 2}}, {"albumId": "3"}]
    assert extract_album_ids_from_queue(queue) == {1, 2, 3}
    history = [{"albumId": 9}, {"album": {"id": 10}}]
    assert extract_album_ids_from_history(history) == {9, 10}


def test_normalize_wanted_record():
    rec = {
        "id": 42,
        "title": "Test Album",
        "albumType": "EP",
        "foreignAlbumId": "mbid-1",
        "releaseDate": "2020-01-01",
        "artistId": 7,
        "artist": {"artistName": "Artist", "foreignArtistId": "mbid-a"},
    }
    out = normalize_wanted_record(rec)
    assert out["lidarr_album_id"] == 42
    assert out["album_type"] == "ep"
    assert out["artist_name"] == "Artist"
    assert out["album_title"] == "Test Album"
