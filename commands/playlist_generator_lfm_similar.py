#!/usr/bin/env python3
"""
Last.fm Similar Artists playlist — expand seed artists via Last.fm similar, top tracks per artist, sync to Plex/Jellyfin.
"""

from typing import Any

from clients.client_jellyfin import JellyfinClient
from clients.client_lastfm import LastFMClient
from clients.client_plex import PlexClient
from utils.library_cache_manager import get_library_cache_manager
from utils.text_normalizer import normalize_text

from .command_base import BaseCommand
from .playlist_generator_helpers import (
    build_lfm_similar_artist_pool,
    compute_lfm_similar_playlist_title,
    validate_artists_against_cache,
)


class PlaylistGeneratorLfmSimilarCommand(BaseCommand):
    """Build a playlist from Last.fm similar artists + top tracks per library-matched artist."""

    def __init__(self, config=None):
        self.config_json = {}
        super().__init__(config)
        self.plex_client = PlexClient(self.config)
        self.lastfm_client = LastFMClient(self.config)
        self.library_cache_manager = get_library_cache_manager(self.config)
        self.last_run_stats: dict[str, Any] = {}

    def get_description(self) -> str:
        return (
            "Generate playlist from seed artists expanded via Last.fm similar artists "
            "(top tracks per artist, Plex or Jellyfin target)."
        )

    def get_logger_name(self) -> str:
        name = self.config_json.get("command_name", "lfm_similar")
        return f"playlist_generator.{name}"

    def _get_target_client(self) -> tuple[PlexClient | JellyfinClient, str]:
        target = (self.config_json or {}).get("target", "plex")
        target = str(target).lower()
        if target == "jellyfin":
            return JellyfinClient(self.config), "Jellyfin"
        return self.plex_client, "Plex"

    def _delete_playlist_by_name(
        self, target_client: PlexClient | JellyfinClient, playlist_title: str
    ) -> None:
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
        try:
            from database.config_models import CommandConfig
            from database.database import get_database_manager

            cmd_name = self.config_json.get("command_name", "")
            if not cmd_name or not cmd_name.startswith("lfm_similar_"):
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
            seeds_raw = config.get("seed_artists")
            if seeds_raw is None:
                seeds_raw = config.get("artists", [])
            if isinstance(seeds_raw, str):
                seeds_raw = [s.strip() for s in seeds_raw.split("\n") if s.strip()]
            seeds = [s for s in seeds_raw if (s or "").strip()]
            if not seeds:
                self.logger.error("No seed artists configured")
                return False

            similar_per_seed = int(config.get("similar_per_seed", 5))
            similar_per_seed = max(1, min(50, similar_per_seed))
            max_artists = int(config.get("max_artists", 25))
            max_artists = max(1, min(200, max_artists))
            include_seeds = bool(config.get("include_seeds", True))
            top_x = int(config.get("top_x", 5))
            top_x = max(1, min(20, top_x))

            target_client, target_name = self._get_target_client()
            library_key = None
            if hasattr(target_client, "get_resolved_library_key"):
                library_key = target_client.get_resolved_library_key()
            if not library_key:
                self.logger.error(
                    "No target library found. Configure PLEX_LIBRARY_NAME or JELLYFIN_LIBRARY_NAME, "
                    "or ensure a music library exists."
                )
                return False

            cached_data = None
            if self.library_cache_manager:
                cached_data = self.library_cache_manager.get_library_cache(
                    target_name.lower(), library_key
                )

            per_seed_similar: list[list[dict[str, Any]]] = []
            async with self.lastfm_client:
                for seed in seeds:
                    seed = seed.strip()
                    if not seed:
                        continue
                    info = await self.lastfm_client.get_artist_info(artist_name=seed)
                    query_name = seed
                    mbid = None
                    if info:
                        if (info.get("name") or "").strip():
                            query_name = info["name"].strip()
                        if (info.get("mbid") or "").strip():
                            mbid = info["mbid"].strip()
                    similar_rows, _skipped = await self.lastfm_client.get_similar_artists(
                        mbid=mbid,
                        artist_name=query_name,
                        limit=similar_per_seed,
                        include_similar_without_mbid=True,
                    )
                    per_seed_similar.append(similar_rows)

                pool = build_lfm_similar_artist_pool(
                    seeds, per_seed_similar, include_seeds, max_artists
                )

            pool_names = [(row.get("name") or "").strip() for row in pool]
            pool_names = [n for n in pool_names if n]

            valid_artists, invalid_artists = validate_artists_against_cache(pool_names, cached_data)
            if invalid_artists:
                self.logger.warning(f"Artists not in library: {invalid_artists}")

            if not valid_artists:
                self.logger.error("No artists in pool matched the library")
                return False

            valid_norms = set(valid_artists)
            ordered_display_names = [
                n for n in pool_names if normalize_text(n.lower()) in valid_norms
            ]
            seen_o: set[str] = set()
            ordered_unique: list[str] = []
            for n in ordered_display_names:
                k = normalize_text(n.lower())
                if k in seen_o:
                    continue
                seen_o.add(k)
                ordered_unique.append(n)

            playlist_title = compute_lfm_similar_playlist_title(config)
            last_playlist_title = config.get("last_playlist_title")
            if last_playlist_title and last_playlist_title != playlist_title:
                self._delete_playlist_by_name(target_client, last_playlist_title)

            tracks_for_playlist: list[dict[str, Any]] = []
            artists_processed = 0
            artists_skipped = 0

            async with self.lastfm_client:
                for artist_name in ordered_unique:
                    norm = normalize_text(artist_name.lower())
                    top_tracks = await self.lastfm_client.get_top_tracks(artist_name, limit=top_x)
                    added = 0
                    for t in top_tracks[:top_x]:
                        track_name = t.get("name", "")
                        if not track_name:
                            continue
                        tracks_for_playlist.append(
                            {
                                "artist": norm,
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

            summary = (
                f"Last.fm similar + top {top_x} per artist. "
                f"Pool: {len(pool_names)} names, {len(valid_artists)} in library."
            )

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
                "artists_in_pool": len(pool_names),
                "artists_valid": len(valid_artists),
                "artists_total": len(ordered_unique) + len(invalid_artists),
                "invalid_artists": invalid_artists[:10],
                "tracks_found": found,
                "tracks_total": total,
                "source": "lastfm",
                "target": target_name,
                "seeds_count": len(seeds),
            }

            if success:
                self.logger.info(
                    f"Created playlist '{playlist_title}': {found}/{total} tracks from "
                    f"{artists_processed} artists"
                )
                self._persist_after_success(playlist_title)
            return success

        except Exception as e:
            self.logger.error(f"Error in Last.fm similar playlist generator: {e}")
            raise
