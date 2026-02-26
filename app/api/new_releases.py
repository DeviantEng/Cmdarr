"""
New Releases API - Discover releases from Lidarr artists on Spotify that are
missing from MusicBrainz, and generate Harmony links for import.

Flow:
1. Get artists from Lidarr (cached)
2. Get Spotify albums for each artist (cached), filter by type
3. Get MB release groups per artist (1 call/artist, cached)
4. Local compare: if Spotify album title matches MB, skip; else show with Harmony link

New: DB-backed pending table, dismiss, recheck, run-batch, scan-artist.
"""

import random
from datetime import datetime, timezone
from typing import List, Optional, Set
from urllib.parse import quote

from fastapi import APIRouter, HTTPException, Query, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from commands.config_adapter import ConfigAdapter
from clients.client_deezer import DeezerClient
from clients.client_lidarr import LidarrClient
from clients.client_musicbrainz import MusicBrainzClient
from clients.client_spotify import SpotifyClient
from database.config_models import NewReleasePending, DismissedArtistAlbum
from database.database import get_config_db, get_database_manager
from utils.logger import get_logger
from utils.text_normalizer import normalize_text

router = APIRouter()
HARMONY_BASE_URL = "https://harmony.pulsewidth.org.uk/release"

ALBUM_TYPES = frozenset({"album", "ep", "single", "other"})


# Substrings that indicate a live recording (checked in normalized album title)
_LIVE_INDICATORS = frozenset({
    "live", "concert", "unplugged", "recorded live", "recorded at",
    "live at", "live from", "live in", "live session", "live album",
})


def _is_live_release(title: str) -> bool:
    """Return True if the album title suggests a live recording."""
    if not title:
        return False
    norm = normalize_text(title)
    norm_lower = norm.lower()
    for indicator in _LIVE_INDICATORS:
        if indicator in norm_lower:
            return True
    return False


def _album_matches_filter(
    album_type: str,
    total_tracks: int,
    selected_types: Set[str],
) -> bool:
    """Check if album matches selected type filter."""
    if not selected_types:
        return True
    if "album" in selected_types and album_type == "album" and total_tracks > 6:
        return True
    if "ep" in selected_types and album_type == "album" and total_tracks <= 6:
        return True
    if "single" in selected_types and album_type == "single":
        return True
    if "other" in selected_types and album_type in ("compilation", "appears_on"):
        return True
    return False


def _artist_names_match(name1: str, name2: str, min_similarity: float = 0.9) -> bool:
    """Check if two artist names refer to the same artist (avoids Emmure vs emmurée collisions)."""
    from difflib import SequenceMatcher
    n1 = normalize_text(name1)
    n2 = normalize_text(name2)
    if not n1 or not n2:
        return False
    if n1 == n2:
        return True
    return SequenceMatcher(None, n1, n2).ratio() >= min_similarity


def _get_new_releases_source_from_db() -> str:
    """Get new_releases_source from CommandConfig (default deezer)."""
    from database.config_models import CommandConfig
    from database.database import get_database_manager
    db = get_database_manager()
    session = db.get_config_session_context()
    try:
        row = session.query(CommandConfig).filter(
            CommandConfig.command_name == "new_releases_discovery"
        ).first()
        if row and row.config_json:
            src = (row.config_json.get("new_releases_source") or "deezer").strip().lower()
            return src if src in ("spotify", "deezer") else "deezer"
    finally:
        session.close()
    return "deezer"


def _title_matches_mb(spotify_title: str, mb_titles: List[str], min_similarity: float = 0.7) -> bool:
    """Check if Spotify album title matches any MB release group (fuzzy)."""
    norm_spotify = normalize_text(spotify_title)
    if not norm_spotify:
        return False
    for mb_title in mb_titles:
        norm_mb = normalize_text(mb_title)
        if not norm_mb:
            continue
        # Exact or containment
        if norm_spotify == norm_mb:
            return True
        if norm_spotify in norm_mb or norm_mb in norm_spotify:
            return True
        # Similarity (catches "Deconstructed" vs "Deconstructed (Live)")
        from difflib import SequenceMatcher
        if SequenceMatcher(None, norm_spotify, norm_mb).ratio() >= min_similarity:
            return True
    return False


@router.get("/new-releases")
async def get_new_releases(
    artist_limit: int = Query(10, ge=1, le=500, description="Max Lidarr artists to scan"),
    album_types: Optional[str] = Query(
        "album",
        description="Comma-separated: album, ep, single, other (default: album)",
    ),
):
    """
    Scan Lidarr artists for releases on Spotify that are missing from MusicBrainz.
    1 call/artist to MB (release groups) - no per-album MB lookups.
    """
    logger = get_logger("cmdarr.api.new_releases")

    config = ConfigAdapter()

    source_provider = _get_new_releases_source_from_db()
    if source_provider == 'spotify':
        if not config.SPOTIFY_CLIENT_ID or not config.SPOTIFY_CLIENT_SECRET:
            raise HTTPException(
                status_code=503,
                detail="Spotify credentials not configured (new_releases_source=spotify).",
            )
    if not config.LIDARR_API_KEY or not config.LIDARR_URL:
        raise HTTPException(
            status_code=503,
            detail="Lidarr not configured.",
        )

    selected = {t.strip().lower() for t in (album_types or "").split(",") if t.strip()}
    selected = selected & ALBUM_TYPES
    if not selected:
        selected = {"album"}

    results: List[dict] = []
    artists_checked = 0
    artists_with_releases = 0
    skipped_in_mb = 0
    skipped_type = 0
    skipped_live = 0

    try:
        async with LidarrClient(config) as lidarr_client:
            artists = await lidarr_client.get_all_artists()
            total_artists = len(artists)
            n = min(artist_limit, len(artists))
            artists_to_scan = random.sample(artists, n)

        logger.info(
            f"Scanning {len(artists_to_scan)} artists (types: {sorted(selected)}, source: {source_provider})"
        )

        musicbrainz_client = MusicBrainzClient(config) if config.MUSICBRAINZ_ENABLED else None
        cache_ttl = getattr(config, 'NEW_RELEASES_CACHE_DAYS', 14)
        client_class = SpotifyClient if source_provider == 'spotify' else DeezerClient
        artist_id_key = 'spotifyArtistId' if source_provider == 'spotify' else 'deezerArtistId'

        async with client_class(config) as release_client:
            for artist in artists_to_scan:
                artist_name = artist.get("artistName", "")
                mbid = artist.get("musicBrainzId", "")

                if not artist_name:
                    continue

                artists_checked += 1

                # Prefer Lidarr's link when available (avoids name collisions like Emmure vs emmurée)
                artist_id = artist.get(artist_id_key)
                if not artist_id:
                    search_result = await release_client.search_artists(artist_name, limit=3)
                    if not search_result.get("success") or not search_result.get("artists"):
                        logger.debug(f"No {source_provider} match for: {artist_name}")
                        continue
                    hit = search_result["artists"][0]
                    artist_id = hit.get("id")
                    if not artist_id:
                        continue
                    # Verify search result matches artist name (reject Emmure→emmurée type collisions)
                    hit_name = hit.get("name", "")
                    if not _artist_names_match(artist_name, hit_name, min_similarity=0.9):
                        logger.warning(
                            f"Skipping '{artist_name}': {source_provider} search returned '{hit_name}' "
                            f"(likely wrong artist). Add {source_provider} link in Lidarr for reliable matching."
                        )
                        continue
                    logger.debug(
                        f"Artist '{artist_name}' has no {source_provider} link in Lidarr; used search fallback"
                    )

                # 1. Get albums (cached)
                albums_result = await release_client.get_artist_albums(
                    artist_id,
                    limit=50,
                    include_groups="album,single,compilation,appears_on",
                    fetch_all=True,
                )
                if not albums_result.get("success") or not albums_result.get("albums"):
                    continue

                # 2. Get MB release groups for this artist (1 call, cached)
                mb_titles = []
                if musicbrainz_client:
                    mb_titles = await musicbrainz_client.get_artist_release_groups(
                        mbid, cache_ttl_days=cache_ttl
                    )
                    if mb_titles is None:
                        # API error (e.g. rate limit) - skip artist, don't add to pending
                        logger.warning(f"Skipping {artist_name}: MusicBrainz fetch failed (rate limit?)")
                        continue

                new_albums = []
                for album in albums_result["albums"]:
                    if album.get("primary_artist_id") != artist_id:
                        skipped_type += 1
                        continue

                    album_type = album.get("album_type", "")
                    total_tracks = album.get("total_tracks", 0)

                    if not _album_matches_filter(album_type, total_tracks, selected):
                        skipped_type += 1
                        continue

                    if _is_live_release(album.get("name", "")):
                        skipped_live += 1
                        continue

                    spotify_url = album.get("spotify_url") or album.get("external_url", "")
                    if not spotify_url:
                        continue

                    # 3. Local compare: is this album in MB?
                    if _title_matches_mb(album.get("name", ""), mb_titles):
                        skipped_in_mb += 1
                        continue

                    harmony_url = f"{HARMONY_BASE_URL}?url={quote(spotify_url, safe='')}"
                    new_albums.append({
                        "name": album.get("name", "Unknown"),
                        "release_date": album.get("release_date", ""),
                        "album_type": album_type,
                        "total_tracks": total_tracks,
                        "spotify_url": spotify_url,
                        "harmony_url": harmony_url,
                    })

                if new_albums:
                    artists_with_releases += 1
                    lidarr_id = artist.get("id")
                    lidarr_base = (config.LIDARR_URL or "").rstrip("/")
                    lidarr_artist_url = f"{lidarr_base}/artist/{lidarr_id}" if lidarr_base and lidarr_id else None
                    results.append({
                        "artist_name": artist_name,
                        "lidarr_mbid": mbid,
                        "spotify_artist_id": artist_id,
                        "lidarr_artist_url": lidarr_artist_url,
                        "albums": new_albums,
                    })

        return {
            "success": True,
            "album_types": sorted(selected),
            "artists_checked": artists_checked,
            "artists_with_releases": artists_with_releases,
            "total_lidarr_artists": total_artists,
            "skipped_in_musicbrainz": skipped_in_mb,
            "skipped_by_type": skipped_type,
            "skipped_live": skipped_live,
            "results": results,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"New releases scan failed: {e}")
        raise HTTPException(status_code=500, detail="New releases scan failed")


# --- DB-backed endpoints ---

def _pending_to_dict(r: NewReleasePending) -> dict:
    """Convert NewReleasePending to API response dict."""
    return {
        "id": r.id,
        "artist_mbid": r.artist_mbid,
        "artist_name": r.artist_name,
        "spotify_artist_id": r.spotify_artist_id,
        "album_title": r.album_title,
        "album_type": r.album_type,
        "release_date": r.release_date,
        "total_tracks": r.total_tracks,
        "spotify_url": r.spotify_url,
        "harmony_url": r.harmony_url,
        "lidarr_artist_id": r.lidarr_artist_id,
        "lidarr_artist_url": r.lidarr_artist_url,
        "musicbrainz_artist_url": f"https://musicbrainz.org/artist/{r.artist_mbid}" if r.artist_mbid else None,
        "added_at": r.added_at.isoformat() if r.added_at else None,
        "source": r.source,
        "status": r.status,
    }


@router.get("/new-releases/pending")
async def get_pending_releases(
    status: Optional[str] = Query("pending", description="Filter: pending, recheck_requested, resolved, dismissed"),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_config_db),
):
    """List pending new releases from DB (paginated)."""
    logger = get_logger("cmdarr.api.new_releases")
    q = db.query(NewReleasePending).filter(NewReleasePending.status == status)
    total = q.count()
    rows = q.order_by(NewReleasePending.added_at.desc()).offset(offset).limit(limit).all()
    return {
        "success": True,
        "total": total,
        "limit": limit,
        "offset": offset,
        "items": [_pending_to_dict(r) for r in rows],
    }


@router.post("/new-releases/clear/{item_id}")
async def clear_release(item_id: int, db: Session = Depends(get_config_db)):
    """Clear a pending release from the list. Will reappear on next scan if still not in MusicBrainz."""
    logger = get_logger("cmdarr.api.new_releases")
    row = db.query(NewReleasePending).filter(NewReleasePending.id == item_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="Item not found")
    db.delete(row)
    db.commit()
    return {"success": True, "message": "Cleared"}


@router.post("/new-releases/clear-all")
async def clear_all_pending(db: Session = Depends(get_config_db)):
    """Clear all pending releases. They will reappear on next scan if still not in MusicBrainz."""
    logger = get_logger("cmdarr.api.new_releases")
    deleted = db.query(NewReleasePending).filter(NewReleasePending.status == "pending").delete()
    db.commit()
    return {"success": True, "message": f"Cleared {deleted} items", "cleared": deleted}


@router.post("/new-releases/ignore/{item_id}")
async def ignore_release(item_id: int, db: Session = Depends(get_config_db)):
    """Ignore a pending release - add to dismissed table. Won't reappear on next scan."""
    logger = get_logger("cmdarr.api.new_releases")
    row = db.query(NewReleasePending).filter(NewReleasePending.id == item_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="Item not found")
    release_date = (row.release_date or "").strip() or None
    existing = db.query(DismissedArtistAlbum).filter(
        DismissedArtistAlbum.artist_mbid == row.artist_mbid,
        DismissedArtistAlbum.album_title == row.album_title,
        DismissedArtistAlbum.release_date == release_date,
    ).first()
    if not existing:
        db.add(DismissedArtistAlbum(
            artist_mbid=row.artist_mbid,
            artist_name=row.artist_name,
            album_title=row.album_title,
            release_date=release_date,
        ))
    row.status = "dismissed"
    row.resolved_at = datetime.now(timezone.utc)
    row.resolved_reason = "manual_ignore"
    db.commit()
    return {"success": True, "message": "Ignored"}


@router.post("/new-releases/dismiss/{item_id}")
async def dismiss_release(item_id: int, db: Session = Depends(get_config_db)):
    """Legacy: same as ignore. Prefer /clear or /ignore."""
    return await ignore_release(item_id, db)


@router.get("/new-releases/dismissed")
async def get_dismissed_releases(
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_config_db),
):
    """List dismissed artist+album combinations (can be restored)."""
    from database.config_models import DismissedArtistAlbum
    q = db.query(DismissedArtistAlbum).order_by(DismissedArtistAlbum.dismissed_at.desc())
    total = q.count()
    rows = q.offset(offset).limit(limit).all()
    return {
        "success": True,
        "total": total,
        "limit": limit,
        "offset": offset,
        "items": [
            {
                "id": r.id,
                "artist_mbid": r.artist_mbid,
                "artist_name": getattr(r, "artist_name", None) or "(unknown)",
                "album_title": r.album_title,
                "release_date": r.release_date,
                "dismissed_at": r.dismissed_at.isoformat() if r.dismissed_at else None,
            }
            for r in rows
        ],
    }


@router.post("/new-releases/restore/{dismissed_id}")
async def restore_dismissed(dismissed_id: int, db: Session = Depends(get_config_db)):
    """Restore a dismissed item - removes from dismissed table so it can reappear on next scan."""
    from database.config_models import DismissedArtistAlbum
    row = db.query(DismissedArtistAlbum).filter(DismissedArtistAlbum.id == dismissed_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="Dismissed item not found")
    db.delete(row)
    db.commit()
    return {"success": True, "message": "Restored - will reappear on next scan"}


@router.post("/new-releases/recheck/{item_id}")
async def recheck_release(item_id: int, db: Session = Depends(get_config_db)):
    """Verify in MusicBrainz; if album found, remove from pending."""
    logger = get_logger("cmdarr.api.new_releases")
    row = db.query(NewReleasePending).filter(NewReleasePending.id == item_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="Item not found")
    config = ConfigAdapter()
    found_in_mb = False
    if config.MUSICBRAINZ_ENABLED and row.artist_mbid and row.album_title:
        async with MusicBrainzClient(config) as mb_client:
            found_in_mb = await mb_client.release_exists_by_artist_and_title(
                row.artist_mbid, row.album_title, cache_ttl_days=0
            )
    if found_in_mb:
        db.delete(row)
        db.commit()
        return {"success": True, "message": "Found in MusicBrainz, removed", "removed": True}
    return {"success": True, "message": "Not found in MusicBrainz", "removed": False}


@router.get("/new-releases/command-status")
async def get_new_releases_command_status(db: Session = Depends(get_config_db)):
    """Get new_releases_discovery command status (enabled, config) for UI."""
    from database.config_models import CommandConfig
    row = db.query(CommandConfig).filter(
        CommandConfig.command_name == "new_releases_discovery"
    ).first()
    if not row:
        return {"enabled": False, "config_json": None}
    return {
        "enabled": row.enabled,
        "config_json": row.config_json,
        "schedule_cron": row.schedule_cron,
    }


@router.post("/new-releases/run-batch")
async def run_batch(db: Session = Depends(get_config_db)):
    """Trigger the next batch scan (same logic as scheduled command)."""
    from database.config_models import CommandConfig
    from services.command_executor import command_executor

    cmd = db.query(CommandConfig).filter(
        CommandConfig.command_name == "new_releases_discovery"
    ).first()
    if not cmd:
        raise HTTPException(status_code=400, detail="New Releases Discovery command not found")
    if not cmd.enabled:
        raise HTTPException(
            status_code=400,
            detail="New Releases Discovery command is disabled. Enable it in Commands first.",
        )
    result = await command_executor.execute_command("new_releases_discovery", triggered_by="api")
    if not result.get("success"):
        raise HTTPException(status_code=400, detail="Batch run failed")
    return {"success": True, "execution_id": result.get("execution_id")}


class ScanArtistRequest(BaseModel):
    artist_mbid: Optional[str] = None
    artist_name: Optional[str] = None
    album_types: Optional[List[str]] = None


@router.post("/new-releases/scan-artist")
async def scan_artist(body: ScanArtistRequest):
    """Manually scan a single artist. Provide artist_mbid (preferred) or artist_name."""
    from services.command_executor import command_executor
    from clients.client_lidarr import LidarrClient

    config = ConfigAdapter()
    if not config.LIDARR_API_KEY or not config.LIDARR_URL:
        raise HTTPException(status_code=503, detail="Lidarr not configured")

    async with LidarrClient(config) as lidarr_client:
        artists = await lidarr_client.get_all_artists()

    artist = None
    if body.artist_mbid:
        artist = next((a for a in artists if a.get("musicBrainzId") == body.artist_mbid), None)
    elif body.artist_name:
        name_lower = (body.artist_name or "").strip().lower()
        artist = next((a for a in artists if (a.get("artistName") or "").lower() == name_lower), None)
        if not artist:
            artist = next((a for a in artists if name_lower in (a.get("artistName") or "").lower()), None)

    if not artist:
        raise HTTPException(status_code=404, detail="Artist not found in Lidarr")

    album_types_str = None
    if body.album_types:
        album_types_str = ",".join(t.strip().lower() for t in body.album_types if t)
    config_override = {"artists": [artist], "source": "manual"}
    if album_types_str:
        config_override["album_types"] = album_types_str
    result = await command_executor.execute_command(
        "new_releases_discovery",
        config_override=config_override,
        triggered_by="api",
    )
    if not result.get("success"):
        raise HTTPException(status_code=400, detail="Scan failed")
    return {"success": True, "execution_id": result.get("execution_id"), "artist_name": artist.get("artistName")}


@router.get("/new-releases/lidarr-artists")
async def lidarr_artists_autocomplete(
    q: str = Query("", min_length=1),
    limit: int = Query(20, ge=1, le=50),
    db: Session = Depends(get_config_db),
):
    """Autocomplete for Lidarr artists (from synced lidarr_artist table)."""
    from database.config_models import LidarrArtist

    q_clean = (q or "").strip()
    if not q_clean:
        return {"success": True, "artists": []}
    pattern = f"%{q_clean}%"
    rows = (
        db.query(LidarrArtist)
        .filter(LidarrArtist.artist_name.ilike(pattern))
        .order_by(LidarrArtist.artist_name)
        .limit(limit)
        .all()
    )
    return {
        "success": True,
        "artists": [
            {
                "artist_mbid": r.artist_mbid,
                "artist_name": r.artist_name,
                "lidarr_id": r.lidarr_id,
                "spotify_artist_id": r.spotify_artist_id,
            }
            for r in rows
        ],
    }


@router.post("/new-releases/sync-lidarr-artists")
async def sync_lidarr_artists(db: Session = Depends(get_config_db)):
    """Sync Lidarr artists into lidarr_artist table for autocomplete."""
    from database.config_models import LidarrArtist

    config = ConfigAdapter()
    if not config.LIDARR_API_KEY or not config.LIDARR_URL:
        raise HTTPException(status_code=503, detail="Lidarr not configured")

    async with LidarrClient(config) as lidarr_client:
        artists = await lidarr_client.get_all_artists()

    now = datetime.now(timezone.utc)
    updated = 0
    for a in artists:
        mbid = a.get("musicBrainzId")
        if not mbid:
            continue
        existing = db.query(LidarrArtist).filter(LidarrArtist.artist_mbid == mbid).first()
        if existing:
            existing.artist_name = a.get("artistName", "")
            existing.lidarr_id = a.get("id")
            existing.spotify_artist_id = a.get("spotifyArtistId")
            existing.last_synced_at = now
            updated += 1
        else:
            db.add(LidarrArtist(
                artist_mbid=mbid,
                artist_name=a.get("artistName", ""),
                lidarr_id=a.get("id"),
                spotify_artist_id=a.get("spotifyArtistId"),
                last_synced_at=now,
            ))
    db.commit()
    return {"success": True, "synced": len(artists), "updated": updated}
