"""Tests for Lidarr artist cache upsert."""

from datetime import UTC, datetime
from unittest.mock import MagicMock

from utils.lidarr_artist_sync import upsert_lidarr_artists_from_payload


def test_upsert_lidarr_artists_from_payload_insert_and_update():
    session = MagicMock()
    existing = MagicMock()
    session.query.return_value.filter.return_value.first.side_effect = [None, existing]

    now = datetime(2026, 3, 13, tzinfo=UTC)
    inserted, updated = upsert_lidarr_artists_from_payload(
        session,
        [
            {
                "musicBrainzId": "mbid-new",
                "artistName": "New Artist",
                "id": 10,
                "spotifyArtistId": "sp1",
                "deezerArtistId": "dz1",
            },
            {
                "musicBrainzId": "mbid-old",
                "artistName": "Updated Artist",
                "id": 11,
            },
            {"artistName": "No MBID"},
        ],
        now=now,
    )

    assert inserted == 1
    assert updated == 1
    session.add.assert_called_once()
    assert existing.artist_name == "Updated Artist"
    assert existing.last_synced_at == now
