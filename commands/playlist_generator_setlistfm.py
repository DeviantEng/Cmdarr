#!/usr/bin/env python3
"""Setlist.fm–based playlist generator — ordered artist blocks from recent setlists."""

from __future__ import annotations

from datetime import date
from typing import Any

from clients.client_jellyfin import JellyfinClient
from clients.client_plex import PlexClient
from clients.client_setlistfm import SetlistFmClient
from commands.setlistfm_parse import (
    MAX_ARTIST_SETLIST_PAGES,
    SHOW_LOOKBACK_DAYS,
    STUB_TRACK_THRESHOLD,
    TARGET_SUBSTANTIAL_SETLISTS,
    choose_repr_setlist_for_playlist,
    dedupe_by_event_key,
    event_within_lookback_days,
    extract_ordered_songs_from_setlist,
    finalize_candidate_pool_after_scan,
    setlists_from_api_page,
    track_count_nonempty,
)
from utils.library_cache_manager import get_library_cache_manager
from utils.text_normalizer import normalize_text

from .command_base import BaseCommand
from .playlist_generator_helpers import (
    compute_setlistfm_playlist_title,
    validate_artists_against_cache,
)


def _mbid_from_search(data: dict[str, Any] | None) -> str | None:
    if not data:
        return None
    artists = data.get("artist")
    if isinstance(artists, dict):
        artists = [artists]
    if not artists:
        return None
    first = artists[0]
    if not isinstance(first, dict):
        return None
    mbid = (first.get("mbid") or "").strip()
    return mbid or None


class PlaylistGeneratorSetlistfmCommand(BaseCommand):
    """Build a playlist from setlist.fm data: one ordered block per configured artist."""

    def __init__(self, config=None):
        self.config_json = {}
        super().__init__(config)
        self.plex_client = PlexClient(self.config)
        self.library_cache_manager = get_library_cache_manager(self.config)
        self.last_run_stats: dict[str, Any] = {}

    def get_description(self) -> str:
        return "Generate playlist from setlist.fm recent setlists per artist (ordered blocks)."

    def get_logger_name(self) -> str:
        name = self.config_json.get("command_name", "setlistfm")
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
            if not cmd_name or not cmd_name.startswith("setlistfm_"):
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

    async def _resolve_songs_for_artist(
        self,
        client: SetlistFmClient,
        search_name: str,
        max_tracks: int,
    ) -> list[str]:
        """Fetch one setlist-derived ordered song list: recent-year pool, median-depth pick."""
        search = await client.search_artists(search_name, page=1)
        mbid = _mbid_from_search(search)
        if not mbid:
            self.logger.warning(f"setlist.fm: no MBID for artist search '{search_name}'")
            return []

        today = date.today()
        substantial: list[dict[str, Any]] = []
        stub: list[dict[str, Any]] = []

        for page in range(1, MAX_ARTIST_SETLIST_PAGES + 1):
            page_data = await client.get_artist_setlists(mbid, page=page)
            if not page_data:
                continue
            for sl in setlists_from_api_page(page_data):
                if track_count_nonempty(sl) == 0:
                    continue
                if not event_within_lookback_days(sl, today=today, days=SHOW_LOOKBACK_DAYS):
                    continue
                n = track_count_nonempty(sl)
                if n <= STUB_TRACK_THRESHOLD:
                    stub.append(sl)
                else:
                    substantial.append(sl)
            if len(dedupe_by_event_key(substantial)) >= TARGET_SUBSTANTIAL_SETLISTS:
                break

        pool = finalize_candidate_pool_after_scan(substantial, stub)
        chosen = choose_repr_setlist_for_playlist(pool)
        if chosen:
            titles = extract_ordered_songs_from_setlist(chosen)
            if titles:
                return titles[:max_tracks]
        self.logger.warning(
            f"setlist.fm: no suitable recent setlist for '{search_name}' (mbid={mbid})"
        )
        return []

    async def execute(self) -> bool:
        try:
            config = self.config_json or {}
            api_key = getattr(self.config, "SETLIST_FM_API_KEY", "") or ""
            if not api_key.strip():
                self.logger.error("SETLIST_FM_API_KEY is not configured (Config → setlist.fm)")
                return False

            artists_raw = config.get("artists", [])
            if isinstance(artists_raw, str):
                artists_raw = [a.strip() for a in artists_raw.split("\n") if a.strip()]
            ordered_lines = [a.strip() for a in artists_raw if (a or "").strip()]
            if not ordered_lines:
                self.logger.error("No artists configured")
                return False

            max_tracks = int(config.get("max_tracks_per_artist", 25))
            max_tracks = max(3, min(30, max_tracks))

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

            valid_norms, invalid_artists = validate_artists_against_cache(
                ordered_lines, cached_data
            )
            if invalid_artists:
                self.logger.warning(f"Artists not in library (skipped): {invalid_artists}")

            valid_set = set(valid_norms)
            ordered_valid_lines: list[tuple[str, str]] = []
            for line in ordered_lines:
                norm = normalize_text(line.lower())
                if norm in valid_set:
                    ordered_valid_lines.append((line, norm))

            if not ordered_valid_lines:
                self.logger.error("No listed artists matched the library cache")
                return False

            playlist_title = compute_setlistfm_playlist_title(config)
            last_playlist_title = config.get("last_playlist_title")
            if last_playlist_title and last_playlist_title != playlist_title:
                self._delete_playlist_by_name(target_client, last_playlist_title)

            tracks_for_playlist: list[dict[str, Any]] = []
            artists_processed = 0
            artists_empty = 0

            async with SetlistFmClient(self.config) as sclient:
                for display_name, norm in ordered_valid_lines:
                    songs = await self._resolve_songs_for_artist(
                        sclient,
                        display_name,
                        max_tracks=max_tracks,
                    )
                    if not songs:
                        artists_empty += 1
                        continue
                    for track_name in songs:
                        if not (track_name or "").strip():
                            continue
                        tracks_for_playlist.append(
                            {
                                "artist": norm,
                                "track": track_name.strip(),
                                "album": "",
                            }
                        )
                    artists_processed += 1

            if not tracks_for_playlist:
                self.logger.warning("No tracks resolved for playlist (setlist.fm or library match)")
                self.last_run_stats = {
                    "artists_processed": artists_processed,
                    "artists_empty": artists_empty,
                    "invalid_artists": invalid_artists,
                    "tracks_found": 0,
                    "tracks_total": 0,
                    "source": "setlistfm",
                    "target": target_name,
                }
                return True

            summary = (
                f"Setlist.fm blocks ({max_tracks} tracks max per artist). "
                f"{artists_processed} artist(s) with data."
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
                "artists_empty": artists_empty,
                "artists_listed": len(ordered_lines),
                "invalid_artists": invalid_artists[:10],
                "tracks_found": found,
                "tracks_total": total,
                "source": "setlistfm",
                "target": target_name,
            }

            if success:
                self.logger.info(
                    f"Created playlist '{playlist_title}': {found}/{total} tracks from "
                    f"{artists_processed} artists"
                )
                self._persist_after_success(playlist_title)
            return success

        except Exception as e:
            self.logger.error(f"Error in Setlist.fm playlist generator: {e}")
            raise
