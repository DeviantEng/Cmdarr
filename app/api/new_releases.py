"""
New Releases API - Discover releases from Lidarr artists on Spotify that are
missing from MusicBrainz, and generate Harmony links for import.

Flow:
1. Get artists from Lidarr (cached)
2. Get Spotify albums for each artist (cached), filter by type
3. Get MB release groups per artist (1 call/artist, cached)
4. Local compare: if Spotify album title matches MB, skip; else show with Harmony link
"""

import random
from typing import List, Optional, Set
from urllib.parse import quote

from fastapi import APIRouter, HTTPException, Query

from commands.config_adapter import ConfigAdapter
from clients.client_lidarr import LidarrClient
from clients.client_musicbrainz import MusicBrainzClient
from clients.client_spotify import SpotifyClient
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

    if not config.SPOTIFY_CLIENT_ID or not config.SPOTIFY_CLIENT_SECRET:
        raise HTTPException(
            status_code=503,
            detail="Spotify credentials not configured.",
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
            f"Scanning {len(artists_to_scan)} artists (types: {sorted(selected)})"
        )

        musicbrainz_client = MusicBrainzClient(config) if config.MUSICBRAINZ_ENABLED else None
        cache_ttl = getattr(config, 'NEW_RELEASES_CACHE_DAYS', 14)

        async with SpotifyClient(config) as spotify_client:
            for artist in artists_to_scan:
                artist_name = artist.get("artistName", "")
                mbid = artist.get("musicBrainzId", "")

                if not artist_name:
                    continue

                artists_checked += 1

                # Prefer Lidarr's Spotify link when available (avoids name collisions like Emmure vs emmurée)
                artist_id = artist.get("spotifyArtistId")
                if not artist_id:
                    search_result = await spotify_client.search_artists(artist_name, limit=3)
                    if not search_result.get("success") or not search_result.get("artists"):
                        logger.debug(f"No Spotify match for: {artist_name}")
                        continue
                    spotify_artist = search_result["artists"][0]
                    artist_id = spotify_artist.get("id")
                    if not artist_id:
                        continue
                    # Verify search result matches artist name (reject Emmure→emmurée type collisions)
                    spotify_name = spotify_artist.get("name", "")
                    if not _artist_names_match(artist_name, spotify_name, min_similarity=0.9):
                        logger.warning(
                            f"Skipping '{artist_name}': Spotify search returned '{spotify_name}' "
                            "(likely wrong artist). Add Spotify link in Lidarr for reliable matching."
                        )
                        continue
                    logger.debug(
                        f"Artist '{artist_name}' has no Spotify link in Lidarr; used search fallback"
                    )

                # 1. Get Spotify albums (cached)
                albums_result = await spotify_client.get_artist_albums(
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
        raise HTTPException(status_code=500, detail=str(e))
