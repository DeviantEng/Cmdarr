"""Similarr: interactive Last.fm similar-artist discovery API."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from clients.client_lastfm import LastFMClient
from clients.client_lidarr import LidarrClient
from clients.client_plex import PlexClient
from commands.config_adapter import ConfigAdapter
from database.config_models import LidarrArtist
from database.database import get_config_db
from services.similarr_service import similarr_service
from utils.lidarr_artist_sync import upsert_lidarr_artists_from_payload
from utils.similarr_plex import rank_plex_top_artists
from utils.timezone import get_scheduler_timezone

router = APIRouter()


class StartSessionRequest(BaseModel):
    seeds: list[dict[str, str]] = Field(
        ...,
        min_length=1,
        description="Seed artists as {mbid, name}",
    )


class AddArtistRequest(BaseModel):
    mbid: str = Field(..., min_length=1, max_length=100)
    artist_name: str = Field(..., min_length=1, max_length=500)
    search_for_missing_albums: bool = True
    quality_profile_id: int | None = Field(default=None, ge=1)
    metadata_profile_id: int | None = Field(default=None, ge=1)


@router.get("/artists")
async def list_cached_artists(
    q: Annotated[str, Query()] = "",
    limit: Annotated[int, Query(ge=1, le=10000)] = 5000,
    db: Session = Depends(get_config_db),
):
    """List cached Lidarr artists for Similarr seed selection (search optional)."""
    query = db.query(LidarrArtist)
    q_clean = (q or "").strip()
    if q_clean:
        query = query.filter(LidarrArtist.artist_name.ilike(f"%{q_clean}%"))
    rows = query.order_by(LidarrArtist.artist_name).limit(limit).all()
    return {
        "success": True,
        "artists": [
            {
                "artist_mbid": r.artist_mbid,
                "artist_name": r.artist_name,
                "lidarr_id": r.lidarr_id,
            }
            for r in rows
        ],
        "count": len(rows),
    }


@router.post("/sync-artists")
async def sync_artists(db: Annotated[Session, Depends(get_config_db)]):
    """Refresh lidarr_artist cache from Lidarr."""
    config = ConfigAdapter()
    if not config.LIDARR_API_KEY or not config.LIDARR_URL:
        raise HTTPException(status_code=503, detail="Lidarr not configured")

    async with LidarrClient(config) as lidarr_client:
        artists = await lidarr_client.get_all_artists()

    now = datetime.now(UTC)
    inserted, updated = upsert_lidarr_artists_from_payload(db, artists, now=now)
    db.commit()
    return {
        "success": True,
        "synced": len(artists),
        "inserted": inserted,
        "updated": updated,
    }


@router.get("/plex-top-artists")
async def plex_top_artists(
    account_id: Annotated[str, Query(min_length=1)],
    lookback_days: Annotated[int, Query(ge=7, le=365)] = 90,
    limit: Annotated[int, Query(ge=1, le=50)] = 20,
    db: Session = Depends(get_config_db),
):
    """Rank Plex top-listened artists and map matched names to Lidarr MBIDs."""
    config = ConfigAdapter()
    if not config.get("PLEX_CLIENT_ENABLED", False):
        raise HTTPException(status_code=503, detail="Plex client is not enabled")

    plex = PlexClient(config)
    library_key = plex.get_resolved_library_key()
    if not library_key:
        raise HTTPException(status_code=503, detail="Plex music library not configured")

    tz = get_scheduler_timezone()
    now = datetime.now(tz)
    history_start = now - timedelta(days=lookback_days)

    try:
        history_raw = plex.get_play_history(
            library_key=library_key,
            account_id=account_id,
            mindate=history_start,
            maxresults=3000,
        )
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Failed to fetch Plex history: {e}") from e

    ranked = rank_plex_top_artists(
        history_raw,
        lookback_days=lookback_days,
        limit=limit,
        now=now,
    )

    name_to_row: dict[str, LidarrArtist] = {}
    for row in db.query(LidarrArtist).all():
        key = (row.artist_name or "").strip().lower()
        if key and key not in name_to_row:
            name_to_row[key] = row

    artists: list[dict[str, Any]] = []
    unmatched: list[dict[str, Any]] = []
    for name, play_count in ranked:
        cached = name_to_row.get(name.lower())
        if cached and cached.artist_mbid:
            artists.append(
                {
                    "artist_name": cached.artist_name or name,
                    "play_count": play_count,
                    "artist_mbid": cached.artist_mbid,
                    "lidarr_id": cached.lidarr_id,
                }
            )
        else:
            unmatched.append({"artist_name": name, "play_count": play_count})

    return {
        "success": True,
        "account_id": str(account_id),
        "lookback_days": lookback_days,
        "artists": artists,
        "unmatched": unmatched,
        "count": len(artists),
    }


@router.post("/sessions")
async def start_session(body: StartSessionRequest):
    """Start an interactive similar-artist search session."""
    config = ConfigAdapter()
    if not (config.LASTFM_API_KEY or "").strip():
        raise HTTPException(status_code=503, detail="Last.fm API key not configured")

    seeds: list[dict[str, str]] = []
    for raw in body.seeds:
        mbid = (raw.get("mbid") or raw.get("artist_mbid") or "").strip()
        name = (raw.get("name") or raw.get("artist_name") or "").strip()
        if mbid:
            seeds.append({"mbid": mbid, "name": name})

    try:
        session = await similarr_service.start_session(seeds)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except RuntimeError as e:
        raise HTTPException(status_code=409, detail=str(e)) from e

    return {"success": True, **session.to_dict()}


@router.get("/sessions/{session_id}")
async def get_session(session_id: str):
    session = similarr_service.get_session(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")
    return {"success": True, **session.to_dict()}


@router.get("/sessions")
async def get_active_session():
    """Return the current process session if any."""
    session = similarr_service.get_session()
    if session is None:
        return {"success": True, "session": None}
    return {"success": True, "session": session.to_dict()}


@router.post("/sessions/{session_id}/stop")
async def stop_session(session_id: str):
    try:
        session = await similarr_service.stop_session(session_id)
    except KeyError as e:
        raise HTTPException(status_code=404, detail="Session not found") from e
    return {"success": True, **session.to_dict()}


@router.get("/bio")
async def get_artist_bio(
    mbid: Annotated[str, Query()] = "",
    name: Annotated[str, Query()] = "",
):
    """Fetch Last.fm bio/stats for an artist."""
    mbid_clean = (mbid or "").strip()
    name_clean = (name or "").strip()
    if not mbid_clean and not name_clean:
        raise HTTPException(status_code=400, detail="mbid or name is required")

    config = ConfigAdapter()
    if not (config.LASTFM_API_KEY or "").strip():
        raise HTTPException(status_code=503, detail="Last.fm API key not configured")

    async with LastFMClient(config) as lastfm:
        info = await lastfm.get_artist_info(
            mbid=mbid_clean or None,
            artist_name=name_clean or None,
            prefer_bio=True,
        )

    if not info:
        raise HTTPException(status_code=404, detail="Artist not found on Last.fm")

    return {"success": True, "artist": info}


@router.get("/lidarr-profiles")
async def get_lidarr_profiles():
    """Return Lidarr quality and metadata profiles for Similarr add options."""
    config = ConfigAdapter()
    if not config.LIDARR_API_KEY or not config.LIDARR_URL:
        raise HTTPException(status_code=503, detail="Lidarr not configured")

    async with LidarrClient(config) as lidarr:
        quality = await lidarr.get_quality_profiles()
        metadata = await lidarr.get_metadata_profiles()

    def _compact(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        for row in rows or []:
            pid = row.get("id")
            name = (row.get("name") or "").strip()
            if pid is None or not name:
                continue
            out.append({"id": int(pid), "name": name})
        return out

    return {
        "success": True,
        "quality_profiles": _compact(quality),
        "metadata_profiles": _compact(metadata),
    }


@router.post("/add")
async def add_artist_to_lidarr(body: AddArtistRequest):
    """Add an artist to Lidarr (optionally start missing-album search)."""
    config = ConfigAdapter()
    if not config.LIDARR_API_KEY or not config.LIDARR_URL:
        raise HTTPException(status_code=503, detail="Lidarr not configured")

    async with LidarrClient(config) as lidarr:
        result: dict[str, Any] = await lidarr.add_artist(
            mbid=body.mbid.strip(),
            artist_name=body.artist_name.strip(),
            quality_profile_id=body.quality_profile_id,
            metadata_profile_id=body.metadata_profile_id,
            search_for_missing_albums=body.search_for_missing_albums,
        )

    if not result.get("success"):
        err = result.get("error") or "Failed to add artist"
        status = 409 if err == "Artist already exists" else 502
        raise HTTPException(status_code=status, detail=err)

    return {
        "success": True,
        "message": result.get("message"),
        "artist": result.get("artist"),
    }
