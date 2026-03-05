#!/usr/bin/env python3
"""
Artist Essentials Generator - Create playlist from artist list with top X tracks per artist.
Source: Plex (ratingCount) or Last.fm. Target: Plex or Jellyfin.
"""

from difflib import SequenceMatcher
from typing import Any

from clients.client_jellyfin import JellyfinClient
from clients.client_lastfm import LastFMClient
from clients.client_plex import PlexClient
from utils.library_cache_manager import get_library_cache_manager
from utils.text_normalizer import normalize_text

from .command_base import BaseCommand

PLAYLIST_TITLE_PREFIX = "[Cmdarr] Artist Essentials"
SEP = " · "
MAX_ARTIST_LEN = 40


def _build_auto_playlist_suffix(artist_names: list[str]) -> str:
    """Build suffix from artist names: 1-3 artists show all, 4+ show first 2 + N More."""
    names = [n.strip()[:MAX_ARTIST_LEN] for n in artist_names if (n or "").strip()]
    if not names:
        return "Mix"
    if len(names) <= 3:
        return SEP.join(names)
    return f"{names[0]}{SEP}{names[1]} + {len(names) - 2} More"


class PlaylistGeneratorTopTracksCommand(BaseCommand):
    """Generate playlist from list of artists, each contributing top X tracks."""

    def __init__(self, config=None):
        self.config_json = {}
        super().__init__(config)
        self.plex_client = PlexClient(self.config)
        self.lastfm_client = LastFMClient(self.config)
        self.library_cache_manager = get_library_cache_manager(self.config)
        self.last_run_stats = {}

    def get_description(self) -> str:
        return "Generate playlist from artist list with top X tracks per artist (Plex or Last.fm source)."

    def get_logger_name(self) -> str:
        name = self.config_json.get("command_name", "top_tracks")
        return f"playlist_generator.{name}"

    def _get_target_client(self) -> tuple[PlexClient | JellyfinClient, str]:
        target = (self.config_json or {}).get("target", "plex")
        target = str(target).lower()
        if target == "jellyfin":
            return JellyfinClient(self.config), "Jellyfin"
        return self.plex_client, "Plex"

    def _validate_artists(
        self, artists: list[str], cached_data: dict[str, Any] | None
    ) -> tuple[list[str], list[str]]:
        """Validate artists against library cache. Returns (valid, invalid).
        Uses exact match first, then fuzzy match (ratio >= 0.88) for typos.
        """
        if not cached_data or "artist_index" not in cached_data:
            return [], [a.strip() for a in artists if a.strip()]

        artist_index = cached_data.get("artist_index", {})
        index_keys = list(artist_index.keys())
        valid = []
        invalid = []
        fuzzy_threshold = 0.88

        for a in artists:
            name = (a or "").strip()
            if not name:
                continue
            norm = normalize_text(name.lower())
            if norm in artist_index:
                valid.append(norm)
                continue
            # Fuzzy match: find best match among keys sharing first char
            first_char = norm[0] if norm else ""
            candidates = [k for k in index_keys if k and k[0] == first_char]
            if not candidates and index_keys:
                candidates = index_keys  # Fallback: search all if no first-char match
            best_ratio = 0.0
            best_key = None
            for key in candidates:
                r = SequenceMatcher(None, norm, key).ratio()
                if r > best_ratio:
                    best_ratio = r
                    best_key = key
            if best_key and best_ratio >= fuzzy_threshold:
                valid.append(best_key)
            else:
                invalid.append(name)
        return valid, invalid

    def _delete_playlist_by_name(
        self, target_client: PlexClient | JellyfinClient, playlist_title: str
    ) -> None:
        """Delete a playlist by name from Plex or Jellyfin."""
        try:
            pl = target_client.find_playlist_by_name(playlist_title)
            if not pl:
                return
            if isinstance(target_client, PlexClient):
                rk = pl.get("ratingKey")
                if rk:
                    target_client.delete_playlist(rk)
                    self.logger.info(f"Deleted old playlist '{playlist_title}' (name changed)")
            else:
                pid = pl.get("Id")
                if pid:
                    target_client.delete_playlist(pid)
                    self.logger.info(f"Deleted old playlist '{playlist_title}' (name changed)")
        except Exception as e:
            self.logger.warning(f"Could not delete old playlist '{playlist_title}': {e}")

    def _persist_after_success(self, playlist_title: str) -> None:
        """Persist last_playlist_title and update display_name to match playlist."""
        try:
            from database.config_models import CommandConfig
            from database.database import get_database_manager

            cmd_name = self.config_json.get("command_name", "")
            if not cmd_name or not cmd_name.startswith("top_tracks_"):
                return
            db = get_database_manager()
            session = db.get_config_session_sync()
            try:
                cmd = (
                    session.query(CommandConfig)
                    .filter(CommandConfig.command_name == cmd_name)
                    .first()
                )
                if cmd:
                    cfg = dict(cmd.config_json or {})
                    cfg["last_playlist_title"] = playlist_title
                    cmd.config_json = cfg
                    cmd.display_name = playlist_title
                    session.commit()
            finally:
                session.close()
        except Exception as e:
            self.logger.warning(f"Could not persist after success: {e}")

    async def execute(self) -> bool:
        try:
            config = self.config_json or {}
            artists_raw = config.get("artists", [])
            if isinstance(artists_raw, str):
                artists_raw = [a.strip() for a in artists_raw.split("\n") if a.strip()]
            top_x = int(config.get("top_x", 5))
            top_x = max(1, min(20, top_x))
            source = str(config.get("source", "plex")).lower()
            target_client, target_name = self._get_target_client()
            library_key = config.get("target_library_key")

            if not library_key and hasattr(target_client, "get_resolved_library_key"):
                library_key = target_client.get_resolved_library_key()

            if not library_key:
                self.logger.error("No target library configured")
                return False

            # Jellyfin target: source must be Last.fm
            if target_name == "Jellyfin" and source == "plex":
                source = "lastfm"
                self.logger.info("Jellyfin target: using Last.fm source")

            # Get library cache for validation and matching
            cached_data = None
            if self.library_cache_manager:
                cached_data = self.library_cache_manager.get_library_cache(
                    target_name.lower(), library_key
                )

            valid_artists, invalid_artists = self._validate_artists(artists_raw, cached_data)
            if invalid_artists:
                self.logger.warning(f"Artists not in library: {invalid_artists}")

            if not valid_artists:
                self.logger.error("No valid artists found in library")
                return False

            # Ordered display names from user list (for auto-naming)
            valid_norms = set(valid_artists)
            ordered_display_names = [
                a.strip()
                for a in artists_raw
                if (a or "").strip() and normalize_text((a or "").strip().lower()) in valid_norms
            ]

            use_custom = config.get("use_custom_playlist_name", False)
            custom_name = (config.get("custom_playlist_name") or "").strip()
            if use_custom and custom_name:
                suffix = custom_name
            else:
                suffix = _build_auto_playlist_suffix(ordered_display_names)
            playlist_title = f"{PLAYLIST_TITLE_PREFIX}: {suffix}"
            last_playlist_title = config.get("last_playlist_title")
            if last_playlist_title and last_playlist_title != playlist_title:
                self._delete_playlist_by_name(target_client, last_playlist_title)

            tracks_for_playlist: list[dict[str, Any]] = []
            artists_processed = 0
            artists_skipped = 0

            if source == "plex":
                # Plex: get popular tracks via ratingCount
                for artist_name in valid_artists:
                    norm = normalize_text(artist_name.lower())
                    track_keys = (cached_data or {}).get("artist_index", {}).get(norm, [])
                    if not track_keys:
                        artists_skipped += 1
                        continue
                    first_track_key = track_keys[0]
                    artist_rk = self.plex_client.get_artist_rating_key_from_track(first_track_key)
                    if not artist_rk:
                        artists_skipped += 1
                        continue
                    popular = self.plex_client.get_artist_popular_tracks(
                        library_key, artist_rk, limit=top_x
                    )
                    for t in popular[:top_x]:
                        tracks_for_playlist.append(
                            {
                                "rating_key": t["key"],
                                "artist": t["artist"],
                                "track": t["title"],
                                "album": t.get("album", ""),
                            }
                        )
                    artists_processed += 1
            else:
                # Last.fm: get top tracks, pass to sync_playlist for matching
                async with self.lastfm_client:
                    for artist_name in valid_artists:
                        top_tracks = await self.lastfm_client.get_top_tracks(
                            artist_name, limit=top_x
                        )
                        added = 0
                        for t in top_tracks[:top_x]:
                            track_name = t.get("name", "")
                            if not track_name:
                                continue
                            tracks_for_playlist.append(
                                {
                                    "artist": artist_name,
                                    "track": track_name,
                                    "album": t.get("album", ""),
                                }
                            )
                            added += 1
                        if added > 0:
                            artists_processed += 1
                        else:
                            artists_skipped += 1

            if not tracks_for_playlist:
                self.logger.warning("No tracks found for playlist")
                return True
            summary = f"Top {top_x} tracks per artist. Artists: {', '.join(valid_artists[:5])}{'...' if len(valid_artists) > 5 else ''}"

            if hasattr(target_client, "_cached_library"):
                target_client._cached_library = cached_data

            result = target_client.sync_playlist(
                title=playlist_title,
                tracks=tracks_for_playlist,
                summary=summary,
                library_cache_manager=self.library_cache_manager,
                library_key=library_key,
            )

            success = result.get("success", False)
            found = result.get("found_tracks", 0)
            total = result.get("total_tracks", 0)

            artists_total = len(valid_artists) + len(invalid_artists)
            self.last_run_stats = {
                "artists_processed": artists_processed,
                "artists_skipped": artists_skipped,
                "artists_invalid": len(invalid_artists),
                "artists_total": artists_total,
                "invalid_artists": invalid_artists[:10],
                "tracks_found": found,
                "tracks_total": total,
                "source": source,
                "target": target_name,
            }

            if success:
                self.logger.info(
                    f"Created playlist '{playlist_title}': {found}/{total} tracks from {artists_processed} artists"
                )
                self._persist_after_success(playlist_title)
            return success

        except Exception as e:
            self.logger.error(f"Error in top tracks generator: {e}")
            raise
