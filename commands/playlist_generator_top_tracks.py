#!/usr/bin/env python3
"""
Artists Top Tracks Generator - Create playlist from artist list with top X tracks each.
Source: Plex (ratingCount) or Last.fm. Target: Plex or Jellyfin.
"""

from typing import Any

from clients.client_jellyfin import JellyfinClient
from clients.client_lastfm import LastFMClient
from clients.client_plex import PlexClient
from utils.library_cache_manager import get_library_cache_manager
from utils.text_normalizer import normalize_text

from .command_base import BaseCommand


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
        """Validate artists against library cache. Returns (valid, invalid)."""
        if not cached_data or "artist_index" not in cached_data:
            return [], [a.strip() for a in artists if a.strip()]

        artist_index = cached_data.get("artist_index", {})
        valid = []
        invalid = []
        for a in artists:
            name = (a or "").strip()
            if not name:
                continue
            norm = normalize_text(name.lower())
            if norm in artist_index:
                valid.append(name)
            else:
                invalid.append(name)
        return valid, invalid

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
            playlist_name = config.get("playlist_name", "Artists Top Tracks")

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
                        tracks_for_playlist.append({
                            "rating_key": t["key"],
                            "artist": t["artist"],
                            "track": t["title"],
                            "album": t.get("album", ""),
                        })
                    artists_processed += 1
            else:
                # Last.fm: get top tracks, pass to sync_playlist for matching
                async with self.lastfm_client:
                    for artist_name in valid_artists:
                        top_tracks = await self.lastfm_client.get_top_tracks(artist_name, limit=top_x)
                        added = 0
                        for t in top_tracks[:top_x]:
                            track_name = t.get("name", "")
                            if not track_name:
                                continue
                            tracks_for_playlist.append({
                                "artist": artist_name,
                                "track": track_name,
                                "album": t.get("album", ""),
                            })
                            added += 1
                        if added > 0:
                            artists_processed += 1
                        else:
                            artists_skipped += 1

            if not tracks_for_playlist:
                self.logger.warning("No tracks found for playlist")
                return True

            playlist_title = f"[Top Tracks] {playlist_name}"
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

            self.last_run_stats = {
                "artists_processed": artists_processed,
                "artists_skipped": artists_skipped,
                "artists_invalid": len(invalid_artists),
                "tracks_found": found,
                "tracks_total": total,
                "source": source,
                "target": target_name,
            }

            if success:
                self.logger.info(
                    f"Created playlist '{playlist_title}': {found}/{total} tracks from {artists_processed} artists"
                )
            return success

        except Exception as e:
            self.logger.error(f"Error in top tracks generator: {e}")
            raise
