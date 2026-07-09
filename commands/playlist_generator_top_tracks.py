#!/usr/bin/env python3
"""
Artist Essentials Generator - Create playlist from artist list with top X tracks per artist.
Source: Plex (ratingCount) or Last.fm. Target: Plex or Jellyfin.
"""

from typing import Any

from clients.client_jellyfin import JellyfinClient
from clients.client_lastfm import LastFMClient
from clients.client_plex import PlexClient
from utils.library_cache_manager import get_library_cache_manager

from .command_base import BaseCommand
from .playlist_generator_helpers import (
    compute_top_tracks_playlist_title,
    delete_playlist_on_target,
    fetch_top_tracks_for_artists_parallel,
    persist_playlist_identity,
    resolve_artist_track_keys,
    resolve_validated_artists,
)


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
            # Always use resolved library (PLEX/JELLYFIN_LIBRARY_NAME / Music / first) - never stored
            # target_library_key, which may point to wrong library
            library_key = None
            if hasattr(target_client, "get_resolved_library_key"):
                library_key = target_client.get_resolved_library_key()
            if not library_key:
                self.logger.error(
                    "No target library found. Configure PLEX_LIBRARY_NAME or JELLYFIN_LIBRARY_NAME, "
                    "or ensure a music library exists."
                )
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

            resolved_artists, invalid_artists = resolve_validated_artists(artists_raw, cached_data)
            if invalid_artists:
                self.logger.warning(f"Artists not in library: {invalid_artists}")

            if not resolved_artists:
                self.logger.error("No valid artists found in library")
                return False

            ordered_display_names = [r.display_name for r in resolved_artists]

            playlist_title = compute_top_tracks_playlist_title(ordered_display_names, config)
            last_playlist_title = config.get("last_playlist_title")
            last_playlist_id = config.get("last_playlist_id")
            title_changed = last_playlist_title and last_playlist_title != playlist_title
            if title_changed:
                delete_playlist_on_target(
                    target_client,
                    playlist_id=str(last_playlist_id) if last_playlist_id else None,
                    playlist_title=last_playlist_title,
                    logger=self.logger,
                )

            tracks_for_playlist: list[dict[str, Any]] = []
            artists_processed = 0
            artists_skipped = 0
            skipped_artists: list[str] = []

            if source == "plex":
                # Plex: get popular tracks via ratingCount
                for resolved in resolved_artists:
                    track_keys = resolve_artist_track_keys(cached_data, resolved)
                    if not track_keys:
                        artists_skipped += 1
                        skipped_artists.append(resolved.display_name)
                        self.logger.warning(
                            "No library tracks found for '%s'", resolved.display_name
                        )
                        continue
                    first_track_key = track_keys[0]
                    artist_rk = self.plex_client.get_artist_rating_key_from_track(first_track_key)
                    if not artist_rk:
                        artists_skipped += 1
                        skipped_artists.append(resolved.display_name)
                        self.logger.warning(
                            "Could not resolve Plex artist for '%s'", resolved.display_name
                        )
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
                # Last.fm with Plex library fallback when chart data is missing
                async with self.lastfm_client:
                    results = await fetch_top_tracks_for_artists_parallel(
                        resolved_artists,
                        lastfm_client=self.lastfm_client,
                        plex_client=self.plex_client,
                        library_key=library_key,
                        cached_data=cached_data,
                        limit=top_x,
                        logger=self.logger,
                        concurrency=self.config.LASTFM_FETCH_CONCURRENCY,
                    )
                    for resolved, (rows, _source) in zip(resolved_artists, results, strict=True):
                        if rows:
                            tracks_for_playlist.extend(rows)
                            artists_processed += 1
                        else:
                            artists_skipped += 1
                            skipped_artists.append(resolved.display_name)

            if not tracks_for_playlist:
                self.logger.warning("No tracks found for playlist")
                return True
            summary = (
                f"Top {top_x} tracks per artist. Artists: "
                f"{', '.join(ordered_display_names[:5])}"
                f"{'...' if len(ordered_display_names) > 5 else ''}"
            )

            if hasattr(target_client, "_cached_library"):
                target_client._cached_library = cached_data

            result = target_client.sync_playlist(
                title=playlist_title,
                tracks=tracks_for_playlist,
                summary=summary,
                library_cache_manager=self.library_cache_manager,
                library_key=library_key,
                existing_playlist_id=None if title_changed else last_playlist_id,
            )

            success = result.get("success", False)
            found = result.get("found_tracks", 0)
            total = result.get("total_tracks", 0)
            artist_match_stats = result.get("artist_match_stats") or {}
            matching_failures = [
                s["display_name"]
                for s in artist_match_stats.values()
                if s.get("in_lidarr") and s.get("expected", 0) > 0 and s.get("matched", 0) == 0
            ]

            artists_total = len(resolved_artists) + len(invalid_artists)
            self.last_run_stats = {
                "artists_processed": artists_processed,
                "artists_skipped": artists_skipped,
                "skipped_artists": skipped_artists[:20],
                "matching_failures": matching_failures[:20],
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
                persist_playlist_identity(
                    self.config_json.get("command_name", ""),
                    "top_tracks_",
                    playlist_title,
                    result.get("playlist_id"),
                    self.logger,
                )
            return success

        except Exception as e:
            self.logger.error(f"Error in top tracks generator: {e}")
            raise
