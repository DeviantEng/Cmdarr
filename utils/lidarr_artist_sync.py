"""Populate `lidarr_artist` from Lidarr API payloads (shared by API and commands)."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy.orm import Session

from database.config_models import LidarrArtist


def upsert_lidarr_artists_from_payload(
    session: Session,
    artists: list[dict[str, Any]],
    *,
    now: datetime | None = None,
) -> tuple[int, int]:
    """Upsert rows from `LidarrClient.get_all_artists()` results.

    Returns:
        (inserted, updated) counts for rows with a MusicBrainz id.
    """
    if now is None:
        now = datetime.now(UTC)
    inserted = 0
    updated = 0
    for a in artists:
        mbid = a.get("musicBrainzId")
        if not mbid:
            continue
        existing = session.query(LidarrArtist).filter(LidarrArtist.artist_mbid == mbid).first()
        if existing:
            existing.artist_name = a.get("artistName", "")
            existing.lidarr_id = a.get("id")
            existing.spotify_artist_id = a.get("spotifyArtistId")
            existing.last_synced_at = now
            updated += 1
        else:
            session.add(
                LidarrArtist(
                    artist_mbid=mbid,
                    artist_name=a.get("artistName", ""),
                    lidarr_id=a.get("id"),
                    spotify_artist_id=a.get("spotifyArtistId"),
                    last_synced_at=now,
                )
            )
            inserted += 1
    return inserted, updated
