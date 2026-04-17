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

from database.config_models import (
    ArtistConcertHiddenEvent,
    ArtistEvent,
    ArtistEventHidden,
    ArtistEventRefresh,
    ArtistEventSource,
)
from database.database import get_config_db
from services.config_service import config_service
from utils.event_geo import haversine_miles, lat_lon_deg_bounds_for_radius_miles, parse_float
from utils.logger import get_logger

router = APIRouter()


def _log():
    return get_logger("cmdarr.api.events")


class GeocodeRequest(BaseModel):
    query: str = Field(..., min_length=0, max_length=500)


class HideArtistRequest(BaseModel):
    artist_mbid: str = Field(..., min_length=1, max_length=100)
    artist_name: str | None = None


class HideEventRequest(BaseModel):
    event_id: int = Field(..., ge=1)


class SetInterestedRequest(BaseModel):
    interested: bool = True


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
    interested_only: bool = False,
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
    hidden_event_ids: set[int] = set()
    if not include_hidden:
        hidden_mbids = {r[0] for r in db.query(ArtistEventHidden.artist_mbid).all()}
        hidden_event_ids = {r[0] for r in db.query(ArtistConcertHiddenEvent.event_id).all()}

    # When the user has a saved location, filter by radius. Do NOT apply a small SQL LIMIT before
    # distance filtering — that only loads the earliest N events globally and yields few in-range rows.
    use_geo_filter = user_lat is not None and user_lon is not None
    base = db.query(ArtistEvent).filter(ArtistEvent.starts_at_utc >= now)
    if interested_only:
        base = base.filter(ArtistEvent.user_interested.is_(True))
    if use_geo_filter:
        lat_min, lat_max, lon_min, lon_max = lat_lon_deg_bounds_for_radius_miles(
            user_lat, user_lon, use_miles
        )
        q = (
            base.filter(ArtistEvent.venue_lat.isnot(None))
            .filter(ArtistEvent.venue_lon.isnot(None))
            .filter(ArtistEvent.venue_lat >= lat_min, ArtistEvent.venue_lat <= lat_max)
            .filter(ArtistEvent.venue_lon >= lon_min, ArtistEvent.venue_lon <= lon_max)
            .order_by(ArtistEvent.starts_at_utc.asc())
            .limit(10000)
        )
        rows = q.all()
    else:
        q = base.order_by(ArtistEvent.starts_at_utc.asc()).limit(limit * 3)
        rows = q.all()

    out: list[dict[str, Any]] = []
    for ev in rows:
        if not include_hidden and ev.artist_mbid in hidden_mbids:
            continue
        if not include_hidden and ev.id in hidden_event_ids:
            continue
        dist = None
        if use_geo_filter:
            if ev.venue_lat is None or ev.venue_lon is None:
                continue
            dist = haversine_miles(user_lat, user_lon, ev.venue_lat, ev.venue_lon)
            if dist > use_miles:
                continue
        sources = (
            db.query(ArtistEventSource)
            .filter(ArtistEventSource.concert_event_id == ev.id)
            .order_by(ArtistEventSource.provider.asc())
            .all()
        )
        badges = sorted({s.provider for s in sources})
        source_links = [{"provider": s.provider, "url": s.source_url} for s in sources]
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
                "source_links": source_links,
                "interested": bool(getattr(ev, "user_interested", False)),
                "distance_miles": round(dist) if dist is not None else None,
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


@router.post("/invalidate-cache")
async def invalidate_events_cache(db: Annotated[Session, Depends(get_config_db)]):
    """
    Delete all stored concert rows (and per-source links) and clear per-artist refresh
    schedule so every Lidarr artist is due for the next artist_events_refresh run.
    Artist-level and single-event hides are preserved; stored events are removed so the
    Artist Events page is empty until the next refresh repopulates.
    """
    try:
        n_events = db.query(ArtistEvent).delete(synchronize_session=False)
        n_refresh = db.query(ArtistEventRefresh).delete(synchronize_session=False)
        db.commit()
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e)) from e
    _log().info(
        "Invalidated artist events cache: %s concert_event rows, %s artist_concert_refresh rows",
        n_events,
        n_refresh,
    )
    return {
        "success": True,
        "deleted_event_rows": n_events,
        "reset_refresh_rows": n_refresh,
    }


@router.patch("/{event_id}/interested")
async def set_event_interested(
    event_id: int,
    req: SetInterestedRequest,
    db: Annotated[Session, Depends(get_config_db)],
):
    """Mark a canonical event as interested (or clear) for filtering on the Artist Events page."""
    ev = db.query(ArtistEvent).filter(ArtistEvent.id == event_id).first()
    if not ev:
        raise HTTPException(status_code=404, detail="Event not found")
    ev.user_interested = req.interested
    db.commit()
    return {"success": True, "interested": req.interested}


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


@router.get("/hidden-events")
async def list_hidden_events(
    db: Annotated[Session, Depends(get_config_db)],
    limit: Annotated[int, Query(ge=1, le=500)] = 200,
):
    """Single-event hides with joined row details for the UI."""
    q = (
        db.query(ArtistConcertHiddenEvent, ArtistEvent)
        .join(ArtistEvent, ArtistEvent.id == ArtistConcertHiddenEvent.event_id)
        .order_by(ArtistConcertHiddenEvent.hidden_at.desc())
        .limit(limit)
    )
    rows = q.all()
    return {
        "success": True,
        "items": [
            {
                "event_id": ev.id,
                "artist_mbid": ev.artist_mbid,
                "artist_name": ev.artist_name,
                "venue_name": ev.venue_name,
                "venue_city": ev.venue_city,
                "local_date": ev.local_date,
                "hidden_at": h.hidden_at.isoformat() + "Z" if h.hidden_at else None,
            }
            for h, ev in rows
        ],
    }


@router.post("/hide-event")
async def hide_single_event(req: HideEventRequest, db: Annotated[Session, Depends(get_config_db)]):
    ev = db.query(ArtistEvent).filter(ArtistEvent.id == req.event_id).first()
    if not ev:
        raise HTTPException(status_code=404, detail="Event not found")
    existing = (
        db.query(ArtistConcertHiddenEvent)
        .filter(ArtistConcertHiddenEvent.event_id == req.event_id)
        .first()
    )
    if existing:
        return {"success": True, "message": "Already hidden"}
    db.add(ArtistConcertHiddenEvent(event_id=req.event_id))
    db.commit()
    return {"success": True}


@router.post("/unhide-event/{event_id}")
async def unhide_single_event(event_id: int, db: Annotated[Session, Depends(get_config_db)]):
    row = (
        db.query(ArtistConcertHiddenEvent)
        .filter(ArtistConcertHiddenEvent.event_id == event_id)
        .first()
    )
    if not row:
        raise HTTPException(status_code=404, detail="Not hidden")
    db.delete(row)
    db.commit()
    return {"success": True}


@router.post("/unhide-all-events")
async def unhide_all_events(db: Annotated[Session, Depends(get_config_db)]):
    n = db.query(ArtistConcertHiddenEvent).delete()
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
