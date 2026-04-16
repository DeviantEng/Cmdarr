#!/usr/bin/env python3
"""Artist events: list, geo filter, hide/restore artists, geocode."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated, Any
from urllib.parse import quote

import aiohttp
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from database.config_models import ArtistEvent, ArtistEventHidden, ArtistEventSource
from database.database import get_config_db
from services.config_service import config_service
from utils.event_geo import haversine_miles, parse_float
from utils.logger import get_logger

router = APIRouter()


def _log():
    return get_logger("cmdarr.api.events")


class GeocodeRequest(BaseModel):
    query: str = Field(..., min_length=0, max_length=500)


class HideArtistRequest(BaseModel):
    artist_mbid: str = Field(..., min_length=1, max_length=100)
    artist_name: str | None = None


@router.get("/provider-status")
async def provider_status():
    """Which providers are enabled and configured."""
    bit = config_service.get("ARTIST_EVENTS_BANDSINTOWN_ENABLED", False)
    bit_app = (config_service.get("ARTIST_EVENTS_BANDSINTOWN_APP_ID", "") or "").strip()
    sk = config_service.get("ARTIST_EVENTS_SONGKICK_ENABLED", False)
    sk_key = (config_service.get("ARTIST_EVENTS_SONGKICK_API_KEY", "") or "").strip()
    tm = config_service.get("ARTIST_EVENTS_TICKETMASTER_ENABLED", False)
    tm_key = (config_service.get("ARTIST_EVENTS_TICKETMASTER_API_KEY", "") or "").strip()
    return {
        "success": True,
        "bandsintown": {"enabled": bool(bit and bit_app), "configured": bool(bit_app)},
        "songkick": {"enabled": bool(sk and sk_key), "configured": bool(sk_key)},
        "ticketmaster": {"enabled": bool(tm and tm_key), "configured": bool(tm_key)},
        "any_ready": bool((bit and bit_app) or (sk and sk_key) or (tm and tm_key)),
    }


@router.post("/geocode")
async def geocode_location(req: GeocodeRequest):
    """Resolve US-oriented free text (ZIP, city/state) to lat/lon via Nominatim."""
    q = (req.query or "").strip()
    if not q:
        raise HTTPException(status_code=400, detail="query required")
    ua = (
        f"{config_service.get('CMDARR_USER_AGENT', '')}".strip() or "Cmdarr (artist events geocode)"
    )
    url = "https://nominatim.openstreetmap.org/search"
    params = {"q": q + ", USA", "format": "json", "limit": "1", "countrycodes": "us"}
    try:
        async with aiohttp.ClientSession(headers={"User-Agent": ua}) as session:
            async with session.get(
                url, params=params, timeout=aiohttp.ClientTimeout(total=15)
            ) as resp:
                if resp.status != 200:
                    raise HTTPException(status_code=502, detail="Geocoding service error")
                data = await resp.json()
    except Exception as e:
        _log().warning("Geocode failed: %s", e)
        raise HTTPException(status_code=502, detail="Geocoding failed") from e
    if not data:
        raise HTTPException(status_code=404, detail="Location not found")
    row = data[0]
    lat = float(row["lat"])
    lon = float(row["lon"])
    label = row.get("display_name") or q
    return {
        "success": True,
        "lat": lat,
        "lon": lon,
        "label": label[:500],
    }


@router.get("/upcoming")
async def list_upcoming_events(
    db: Annotated[Session, Depends(get_config_db)],
    max_miles: Annotated[float | None, Query(ge=0)] = None,
    include_hidden: bool = False,
    limit: Annotated[int, Query(ge=1, le=500)] = 200,
):
    """Upcoming artist events; optional distance filter from user location in config."""
    now = datetime.now(UTC)
    lat_s = config_service.get("ARTIST_EVENTS_USER_LAT", "") or ""
    lon_s = config_service.get("ARTIST_EVENTS_USER_LON", "") or ""
    radius = float(config_service.get("ARTIST_EVENTS_RADIUS_MILES", 100) or 100)
    user_lat = parse_float(lat_s.strip() or None)
    user_lon = parse_float(lon_s.strip() or None)
    use_miles = max_miles if max_miles is not None else radius

    hidden_mbids: set[str] = set()
    if not include_hidden:
        hidden_mbids = {r[0] for r in db.query(ArtistEventHidden.artist_mbid).all()}

    q = (
        db.query(ArtistEvent)
        .filter(ArtistEvent.starts_at_utc >= now)
        .order_by(ArtistEvent.starts_at_utc.asc())
        .limit(limit * 3)
    )
    rows = q.all()
    out: list[dict[str, Any]] = []
    for ev in rows:
        if not include_hidden and ev.artist_mbid in hidden_mbids:
            continue
        dist = None
        if user_lat is not None and user_lon is not None:
            if ev.venue_lat is not None and ev.venue_lon is not None:
                dist = haversine_miles(user_lat, user_lon, ev.venue_lat, ev.venue_lon)
                if dist > use_miles:
                    continue
        sources = (
            db.query(ArtistEventSource).filter(ArtistEventSource.concert_event_id == ev.id).all()
        )
        badges = sorted({s.provider for s in sources})
        lastfm = f"https://www.last.fm/music/{quote(ev.artist_name, safe='')}/+events"
        out.append(
            {
                "id": ev.id,
                "artist_mbid": ev.artist_mbid,
                "artist_name": ev.artist_name,
                "venue_name": ev.venue_name,
                "venue_city": ev.venue_city,
                "venue_region": ev.venue_region,
                "venue_country": ev.venue_country,
                "venue_lat": ev.venue_lat,
                "venue_lon": ev.venue_lon,
                "starts_at_utc": ev.starts_at_utc.isoformat() + "Z" if ev.starts_at_utc else None,
                "local_date": ev.local_date,
                "sources": badges,
                "distance_miles": round(dist, 1) if dist is not None else None,
                "last_fm_events_url": lastfm,
            }
        )
        if len(out) >= limit:
            break

    return {
        "success": True,
        "events": out,
        "user_location": {
            "lat": user_lat,
            "lon": user_lon,
            "label": config_service.get("ARTIST_EVENTS_USER_LABEL", "") or "",
            "radius_miles": use_miles,
        },
    }


@router.get("/hidden")
async def list_hidden(
    db: Annotated[Session, Depends(get_config_db)],
    limit: Annotated[int, Query(ge=1, le=500)] = 200,
):
    rows = (
        db.query(ArtistEventHidden).order_by(ArtistEventHidden.hidden_at.desc()).limit(limit).all()
    )
    return {
        "success": True,
        "items": [
            {
                "artist_mbid": r.artist_mbid,
                "artist_name": r.artist_name or "",
                "hidden_at": r.hidden_at.isoformat() + "Z" if r.hidden_at else None,
            }
            for r in rows
        ],
    }


@router.post("/hide")
async def hide_artist(req: HideArtistRequest, db: Annotated[Session, Depends(get_config_db)]):
    existing = (
        db.query(ArtistEventHidden).filter(ArtistEventHidden.artist_mbid == req.artist_mbid).first()
    )
    if existing:
        return {"success": True, "message": "Already hidden"}
    db.add(
        ArtistEventHidden(
            artist_mbid=req.artist_mbid,
            artist_name=(req.artist_name or "")[:500] or None,
        )
    )
    db.commit()
    return {"success": True}


@router.post("/unhide/{artist_mbid}")
async def unhide_artist(artist_mbid: str, db: Annotated[Session, Depends(get_config_db)]):
    row = db.query(ArtistEventHidden).filter(ArtistEventHidden.artist_mbid == artist_mbid).first()
    if not row:
        raise HTTPException(status_code=404, detail="Not hidden")
    db.delete(row)
    db.commit()
    return {"success": True}


@router.post("/unhide-all")
async def unhide_all(db: Annotated[Session, Depends(get_config_db)]):
    n = db.query(ArtistEventHidden).delete()
    db.commit()
    return {"success": True, "removed": n}


@router.get("/settings")
async def get_events_settings():
    """Non-sensitive artist-events settings for UI."""
    return {
        "success": True,
        "bandsintown_enabled": config_service.get("ARTIST_EVENTS_BANDSINTOWN_ENABLED", False),
        "songkick_enabled": config_service.get("ARTIST_EVENTS_SONGKICK_ENABLED", False),
        "ticketmaster_enabled": config_service.get("ARTIST_EVENTS_TICKETMASTER_ENABLED", False),
        "user_lat": config_service.get("ARTIST_EVENTS_USER_LAT", "") or "",
        "user_lon": config_service.get("ARTIST_EVENTS_USER_LON", "") or "",
        "user_label": config_service.get("ARTIST_EVENTS_USER_LABEL", "") or "",
        "radius_miles": float(config_service.get("ARTIST_EVENTS_RADIUS_MILES", 100) or 100),
    }
