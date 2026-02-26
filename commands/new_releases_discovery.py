#!/usr/bin/env python3
"""
New Releases Discovery Command
Scans Lidarr artists for Spotify releases missing from MusicBrainz.
Uses artist_scan_log for round-robin (oldest last_scanned_at first; never-scanned = priority).
Inserts into new_release_pending; skips dismissed artist+album combinations.
"""

import random
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional, Set
from urllib.parse import quote


@asynccontextmanager
async def _optional_musicbrainz(config):
    """Context manager: yields MusicBrainzClient if enabled, else None."""
    if config.MUSICBRAINZ_ENABLED:
        async with MusicBrainzClient(config) as client:
            yield client
    else:
        yield None

from sqlalchemy.orm import Session

from .command_base import BaseCommand
from .config_adapter import ConfigAdapter
from clients.client_deezer import DeezerClient
from clients.client_lidarr import LidarrClient
from clients.client_musicbrainz import MusicBrainzClient
from clients.client_spotify import SpotifyClient
from database.config_models import ArtistScanLog, NewReleasePending, DismissedArtistAlbum
from database.database import get_database_manager
from utils.logger import get_logger
from utils.text_normalizer import normalize_text

HARMONY_BASE_URL = "https://harmony.pulsewidth.org.uk/release"
ALBUM_TYPES = frozenset({"album", "ep", "single", "other"})

_LIVE_INDICATORS = frozenset({
    "live", "concert", "unplugged", "recorded live", "recorded at",
    "live at", "live from", "live in", "live session", "live album",
})


def _is_live_release(title: str) -> bool:
    if not title:
        return False
    norm = normalize_text(title).lower()
    return any(ind in norm for ind in _LIVE_INDICATORS)


def _album_matches_filter(album_type: str, total_tracks: int, selected_types: Set[str]) -> bool:
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
    from difflib import SequenceMatcher
    n1 = normalize_text(name1)
    n2 = normalize_text(name2)
    if not n1 or not n2:
        return False
    if n1 == n2:
        return True
    return SequenceMatcher(None, n1, n2).ratio() >= min_similarity


def _title_matches_mb(spotify_title: str, mb_titles: List[str], min_similarity: float = 0.7) -> bool:
    from difflib import SequenceMatcher
    norm_spotify = normalize_text(spotify_title)
    if not norm_spotify:
        return False
    for mb_title in mb_titles:
        norm_mb = normalize_text(mb_title)
        if not norm_mb:
            continue
        if norm_spotify == norm_mb:
            return True
        if norm_spotify in norm_mb or norm_mb in norm_spotify:
            return True
        if SequenceMatcher(None, norm_spotify, norm_mb).ratio() >= min_similarity:
            return True
    return False


class NewReleasesDiscoveryCommand(BaseCommand):
    """Scan Lidarr artists for new releases, insert into new_release_pending"""

    def __init__(self, config=None):
        super().__init__(config)
        self.config_adapter = ConfigAdapter()
        self.last_run_stats: Dict[str, Any] = {}

    async def execute(self) -> bool:
        """
        Execute the discovery scan.
        Uses config.artists (if set via config_override) for manual single-artist scan;
        otherwise picks from Lidarr using round-robin.
        Uses config.source ('scheduled' or 'manual') from config_override.
        """
        try:
            self.logger.info("Starting new releases discovery...")
            config = self.config_adapter
            artists = getattr(self.config, 'artists', None)
            source = getattr(self.config, 'source', 'scheduled')
            artists_per_run = self._get_artists_per_run()
            override_types = getattr(self.config, 'album_types', None)
            if override_types is not None:
                types_str = override_types if isinstance(override_types, str) else ",".join(override_types)
                selected_types = {t.strip().lower() for t in (types_str or "").split(",") if t.strip()}
                selected_types = selected_types & ALBUM_TYPES or {"album"}
            else:
                selected_types = self._get_album_types()

            source_provider = self._get_new_releases_source()
            if source_provider == 'spotify':
                if not config.SPOTIFY_CLIENT_ID or not config.SPOTIFY_CLIENT_SECRET:
                    self.logger.error("Spotify credentials not configured (new_releases_source=spotify)")
                    return False
            if not config.LIDARR_API_KEY or not config.LIDARR_URL:
                self.logger.error("Lidarr not configured")
                return False

            if not artists:
                artists = await self._pick_artists_to_scan(artists_per_run)
            if not artists:
                self.logger.info("No artists to scan")
                self.last_run_stats = {'artists_scanned': 0, 'new_releases_detected': 0}
                return True

            self.logger.info(f"Scanning {len(artists)} artists (types: {sorted(selected_types)}, source: {source_provider})")

            cache_ttl = getattr(config, 'NEW_RELEASES_CACHE_DAYS', 14)
            lidarr_base = (config.LIDARR_URL or "").rstrip("/")
            db = get_database_manager()
            session = db.get_config_session_context()

            client_class = SpotifyClient if source_provider == 'spotify' else DeezerClient
            artist_id_key = 'spotifyArtistId' if source_provider == 'spotify' else 'deezerArtistId'

            try:
                inserted = 0
                scanned = 0
                async with LidarrClient(config) as lidarr_client:
                    async with client_class(config) as release_client:
                        async with _optional_musicbrainz(config) as musicbrainz_client:
                            for artist in artists:
                                artist_name = artist.get("artistName", "")
                                mbid = artist.get("musicBrainzId", "")
                                lidarr_id = artist.get("id")
                                # Lidarr uses MBID for artist URLs (not numeric ID)
                                lidarr_artist_url = f"{lidarr_base}/artist/{mbid}" if lidarr_base and mbid else None

                                if not artist_name or not mbid:
                                    continue

                                # Try Lidarr links first - validate with fuzzy match
                                artist_id = None
                                lidarr_artist_id = artist.get(artist_id_key)
                                if lidarr_artist_id:
                                    artist_info = await release_client.get_artist(lidarr_artist_id)
                                    if artist_info.get("success") and artist_info.get("name"):
                                        provider_name = artist_info.get("name", "")
                                        if _artist_names_match(artist_name, provider_name, min_similarity=0.9):
                                            artist_id = lidarr_artist_id
                                        else:
                                            self.logger.warning(
                                                f"Lidarr link for '{artist_name}' points to '{provider_name}' - falling back to search"
                                            )

                                # Fallback: search by name if no validated link
                                if not artist_id:
                                    # Short names are unreliable for search - skip unless we have a Lidarr link
                                    norm_name = normalize_text(artist_name)
                                    if len(norm_name) <= 4:
                                        self.logger.debug(
                                            f"Skipping '{artist_name}': name too short for reliable search, add {source_provider} link in Lidarr"
                                        )
                                        self._upsert_scan_log(session, mbid, had_pending=False)
                                        continue
                                    search_result = await release_client.search_artists(artist_name, limit=5)
                                    if not search_result.get("success") or not search_result.get("artists"):
                                        self.logger.debug(f"No {source_provider} match for: {artist_name}")
                                        self._upsert_scan_log(session, mbid, had_pending=False)
                                        continue
                                    # Try each result - use first that passes fuzzy match (avoids wrong first hit)
                                    artist_id = None
                                    for hit in search_result["artists"]:
                                        sid = hit.get("id")
                                        if not sid:
                                            continue
                                        hit_name = hit.get("name", "")
                                        if _artist_names_match(artist_name, hit_name, min_similarity=0.9):
                                            artist_id = sid
                                            break
                                    if not artist_id:
                                        best = search_result["artists"][0].get("name", "?")
                                        self.logger.warning(
                                            f"Skipping '{artist_name}': no search result matched (best: '{best}')"
                                        )
                                        self._upsert_scan_log(session, mbid, had_pending=False)
                                        continue

                                albums_result = await release_client.get_artist_albums(
                                    artist_id,
                                    limit=50,
                                    include_groups="album,single,compilation,appears_on",
                                    fetch_all=True,
                                )
                                if not albums_result.get("success") or not albums_result.get("albums"):
                                    self._upsert_scan_log(session, mbid, had_pending=False)
                                    continue

                                mb_titles = []
                                if musicbrainz_client:
                                    mb_titles = await musicbrainz_client.get_artist_release_groups(
                                        mbid, cache_ttl_days=cache_ttl
                                    )
                                    if mb_titles is None:
                                        # API error (e.g. rate limit) - skip artist, don't add to pending
                                        self.logger.warning(f"Skipping {artist_name}: MusicBrainz fetch failed (rate limit?)")
                                        self._upsert_scan_log(session, mbid, had_pending=False)
                                        continue

                                had_pending = False
                                for album in albums_result["albums"]:
                                    if album.get("primary_artist_id") != artist_id:
                                        continue
                                    album_type = album.get("album_type", "")
                                    total_tracks = album.get("total_tracks", 0)
                                    if not _album_matches_filter(album_type, total_tracks, selected_types):
                                        continue
                                    if _is_live_release(album.get("name", "")):
                                        continue
                                    spotify_url = album.get("spotify_url") or album.get("external_url", "")
                                    if not spotify_url:
                                        continue
                                    if _title_matches_mb(album.get("name", ""), mb_titles):
                                        continue

                                    album_title = album.get("name", "Unknown")
                                    release_date = album.get("release_date", "")

                                    if self._is_dismissed(session, mbid, album_title, release_date):
                                        continue
                                    if self._already_pending(session, mbid, album_title, release_date):
                                        continue

                                    harmony_url = f"{HARMONY_BASE_URL}?url={quote(spotify_url, safe='')}"
                                    rec = NewReleasePending(
                                        artist_mbid=mbid,
                                        artist_name=artist_name,
                                        spotify_artist_id=artist_id,
                                        album_title=album_title,
                                        album_type=album_type,
                                        release_date=release_date,
                                        total_tracks=total_tracks,
                                        spotify_url=spotify_url,
                                        harmony_url=harmony_url,
                                        lidarr_artist_id=lidarr_id,
                                        lidarr_artist_url=lidarr_artist_url,
                                        source=source,
                                        status="pending",
                                    )
                                    session.add(rec)
                                    inserted += 1
                                    had_pending = True

                                self._upsert_scan_log(session, mbid, had_pending=had_pending)
                                scanned += 1

                session.commit()
                self.last_run_stats = {'artists_scanned': scanned, 'new_releases_detected': inserted}
                self.logger.info(f"Discovery complete: scanned {scanned} artists, inserted {inserted} pending releases")
                return True
            finally:
                session.close()

        except Exception as e:
            self.logger.exception(f"New releases discovery failed: {e}")
            return False

    def _get_artists_per_run(self) -> int:
        db = get_database_manager()
        session = db.get_config_session_context()
        try:
            from database.config_models import CommandConfig
            row = session.query(CommandConfig).filter(
                CommandConfig.command_name == "new_releases_discovery"
            ).first()
            if row and row.config_json:
                n = row.config_json.get("artists_per_run", 5)
                return max(1, min(50, int(n)))
        finally:
            session.close()
        return 5

    def _get_album_types(self) -> Set[str]:
        db = get_database_manager()
        session = db.get_config_session_context()
        try:
            from database.config_models import CommandConfig
            row = session.query(CommandConfig).filter(
                CommandConfig.command_name == "new_releases_discovery"
            ).first()
            if row and row.config_json:
                types_str = row.config_json.get("album_types", "album")
                selected = {t.strip().lower() for t in (types_str or "").split(",") if t.strip()}
                return selected & ALBUM_TYPES or {"album"}
        finally:
            session.close()
        return {"album"}

    def _get_new_releases_source(self) -> str:
        """Get new releases source: 'spotify' or 'deezer' (default deezer)."""
        cfg = getattr(self, 'config_json', None) or {}
        src = (cfg.get('new_releases_source') or 'deezer').strip().lower()
        return src if src in ('spotify', 'deezer') else 'deezer'

    async def _pick_artists_to_scan(self, n: int) -> List[Dict[str, Any]]:
        """Pick artists: never-scanned first, then by last_scanned_at ASC; if more than n, random sample."""
        async with LidarrClient(self.config_adapter) as lidarr_client:
            artists = await lidarr_client.get_all_artists()
        if not artists:
            return []

        db = get_database_manager()
        session = db.get_config_session_context()
        try:
            rows = session.query(ArtistScanLog).all()
            log_by_mbid = {r.artist_mbid: r for r in rows}
        finally:
            session.close()

        never_scanned = []
        scanned = []
        for a in artists:
            mbid = a.get("musicBrainzId")
            if not mbid:
                continue
            if mbid not in log_by_mbid:
                never_scanned.append(a)
            else:
                scanned.append((log_by_mbid[mbid].last_scanned_at, a))

        scanned.sort(key=lambda x: x[0])
        candidates = never_scanned + [a for _, a in scanned]
        if len(candidates) <= n:
            return candidates
        return random.sample(candidates, n)

    def _upsert_scan_log(self, session: Session, artist_mbid: str, had_pending: bool) -> None:
        now = datetime.now(timezone.utc)
        existing = session.query(ArtistScanLog).filter(ArtistScanLog.artist_mbid == artist_mbid).first()
        if existing:
            existing.last_scanned_at = now
            existing.had_pending_releases = had_pending
        else:
            session.add(ArtistScanLog(
                artist_mbid=artist_mbid,
                last_scanned_at=now,
                had_pending_releases=had_pending,
            ))

    def _is_dismissed(self, session: Session, artist_mbid: str, album_title: str, release_date: str) -> bool:
        r = (release_date or "").strip() or None
        return session.query(DismissedArtistAlbum).filter(
            DismissedArtistAlbum.artist_mbid == artist_mbid,
            DismissedArtistAlbum.album_title == album_title,
            DismissedArtistAlbum.release_date == r,
        ).first() is not None

    def _already_pending(self, session: Session, artist_mbid: str, album_title: str, release_date: str) -> bool:
        r = (release_date or "").strip() or None
        return session.query(NewReleasePending).filter(
            NewReleasePending.artist_mbid == artist_mbid,
            NewReleasePending.album_title == album_title,
            NewReleasePending.release_date == r,
            NewReleasePending.status.in_(["pending", "recheck_requested"]),
        ).first() is not None

    def get_description(self) -> str:
        return "Scan Lidarr artists for Spotify releases missing from MusicBrainz; insert into New Releases pending table."

    def get_logger_name(self) -> str:
        return "cmdarr.command.new_releases_discovery"
