#!/usr/bin/env python3
"""
Mood-Based Playlist Generator - Create playlist from selected Plex moods.
Strategy C: union tracks per mood, score by multi-mood match count, weighted random sample with freshness.
"""

import random
from collections import defaultdict
from datetime import datetime
from typing import Any

from clients.client_plex import PlexClient
from utils.library_cache_manager import get_library_cache_manager

from .command_base import BaseCommand

PLAYLIST_TITLE_PREFIX = "[Cmdarr] Mood"
SEP = " · "
MAX_MOOD_LEN = 40


def _build_auto_playlist_suffix(mood_names: list[str]) -> str:
    """Build suffix from mood names: 1-3 moods show all, 4+ show first 2 + N More."""
    names = [n.strip()[:MAX_MOOD_LEN] for n in mood_names if (n or "").strip()]
    if not names:
        return "Mix"
    if len(names) <= 3:
        return SEP.join(names)
    return f"{names[0]}{SEP}{names[1]} + {len(names) - 2} More"


class PlaylistGeneratorMoodCommand(BaseCommand):
    """Generate playlist from selected moods with multi-mood scoring and freshness."""

    def __init__(self, config=None):
        self.config_json = {}
        super().__init__(config)
        self.plex_client = PlexClient(self.config)
        self.library_cache_manager = get_library_cache_manager(self.config)

    def get_description(self) -> str:
        return "Generate playlist from selected Plex moods with freshness (exclude last run, date-seeded sampling)."

    def get_logger_name(self) -> str:
        name = self.config_json.get("command_name", "mood_playlist")
        return f"playlist_generator.{name}"

    def _persist_last_run_track_ids(self, track_ids: list[str]) -> None:
        """Persist last_run_track_ids to database for next run exclusion."""
        try:
            from database.config_models import CommandConfig
            from database.database import get_database_manager

            cmd_name = self.config_json.get("command_name", "")
            if not cmd_name or not cmd_name.startswith("mood_playlist_"):
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
                    cfg["last_run_track_ids"] = track_ids
                    cmd.config_json = cfg
                    session.commit()
            finally:
                session.close()
        except Exception as e:
            self.logger.warning(f"Could not persist last_run_track_ids: {e}")

    def _persist_after_success(self, playlist_title: str) -> None:
        """Persist last_playlist_title and update display_name to match playlist."""
        try:
            from database.config_models import CommandConfig
            from database.database import get_database_manager

            cmd_name = self.config_json.get("command_name", "")
            if not cmd_name or not cmd_name.startswith("mood_playlist_"):
                return
            db = get_database_manager()
            session = db.get_config_session_sync()
            try:
                cmd = session.query(CommandConfig).filter(CommandConfig.command_name == cmd_name).first()
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

    def _delete_playlist_by_name(self, playlist_title: str) -> None:
        """Delete a playlist by name from Plex (mood playlists are Plex-only)."""
        try:
            pl = self.plex_client.find_playlist_by_name(playlist_title)
            if pl and pl.get("ratingKey"):
                self.plex_client.delete_playlist(pl["ratingKey"])
                self.logger.info(f"Deleted old playlist '{playlist_title}' (name changed)")
        except Exception as e:
            self.logger.warning(f"Could not delete old playlist '{playlist_title}': {e}")

    async def execute(self) -> bool:
        try:
            config = self.config_json or {}
            moods_raw = config.get("moods", [])
            if isinstance(moods_raw, str):
                moods_raw = [m.strip() for m in moods_raw.split(",") if m.strip()]
            moods = [m for m in moods_raw if m]

            if not moods:
                self.logger.error("No moods configured")
                return False

            use_custom = config.get("use_custom_playlist_name", False)
            custom_name = (config.get("custom_playlist_name") or "").strip()
            # Backward compat: old configs used playlist_name for custom names
            if not custom_name and config.get("playlist_name") and config.get("playlist_name") != "Mood Playlist":
                custom_name = (config.get("playlist_name") or "").strip()
                use_custom = bool(custom_name)
            if use_custom and custom_name:
                suffix = custom_name
            else:
                suffix = _build_auto_playlist_suffix(moods)
            max_tracks = int(config.get("max_tracks", 50))
            max_tracks = max(1, min(200, max_tracks))
            exclude_last_run = config.get("exclude_last_run", True)

            library_key = config.get("target_library_key")
            if not library_key and hasattr(self.plex_client, "get_resolved_library_key"):
                library_key = self.plex_client.get_resolved_library_key()
            if not library_key:
                self.logger.error("No target library configured")
                return False

            # 1. Fetch tracks per mood, union and count mood matches per track
            limit_by_year = config.get("limit_by_year", False) or config.get("min_year_enabled", False)
            min_year = config.get("min_year")
            max_year = config.get("max_year")
            if limit_by_year:
                try:
                    min_year = int(min_year) if min_year is not None else None
                    if min_year is not None:
                        min_year = max(1800, min(2100, min_year))
                except (TypeError, ValueError):
                    min_year = None
                try:
                    max_year = int(max_year) if max_year is not None else None
                    if max_year is not None:
                        max_year = max(1800, min(2100, max_year))
                except (TypeError, ValueError):
                    max_year = None
            else:
                min_year = max_year = None

            track_to_data: dict[str, dict[str, Any]] = {}
            track_to_mood_count: dict[str, int] = defaultdict(int)

            for mood in moods:
                tracks = self.plex_client.get_tracks_by_mood(
                    library_key, mood, limit=500, offset=0
                )
                for t in tracks:
                    key = str(t["key"])
                    track_year = t.get("year")
                    if limit_by_year and (min_year is not None or max_year is not None):
                        if track_year is None:
                            continue
                        if min_year is not None and track_year < min_year:
                            continue
                        if max_year is not None and track_year > max_year:
                            continue
                    track_to_mood_count[key] += 1
                    if key not in track_to_data:
                        track_to_data[key] = {
                            "rating_key": key,
                            "artist": t["artist"],
                            "track": t["title"],
                            "album": t.get("album", ""),
                        }

            pool = list(track_to_data.values())
            if not pool:
                self.logger.warning("No tracks found for selected moods")
                return True

            # 2. Exclude last run
            last_run_ids = set(config.get("last_run_track_ids") or []) if exclude_last_run else set()
            pool = [t for t in pool if t["rating_key"] not in last_run_ids]

            if not pool:
                self.logger.info("Pool exhausted after excluding last run; resetting exclusion")
                pool = list(track_to_data.values())
                last_run_ids = set()

            # 3. Weighted random sample: weight = mood_match_count (min 1)
            seed_str = datetime.now().date().isoformat()
            rng = random.Random(seed_str)
            weights = [max(1, track_to_mood_count.get(t["rating_key"], 1)) for t in pool]
            total_weight = sum(weights)
            if total_weight <= 0:
                total_weight = 1
            probs = [w / total_weight for w in weights]
            sample_size = min(max_tracks, len(pool))
            sampled = rng.choices(pool, weights=probs, k=sample_size)
            # Dedupe while preserving order
            seen = set()
            sampled_deduped = []
            for t in sampled:
                k = t["rating_key"]
                if k not in seen:
                    seen.add(k)
                    sampled_deduped.append(t)

            # 4. Create playlist
            playlist_title = f"{PLAYLIST_TITLE_PREFIX}: {suffix}"
            last_playlist_title = config.get("last_playlist_title")
            if last_playlist_title and last_playlist_title != playlist_title:
                self._delete_playlist_by_name(last_playlist_title)
            summary = f"Moods: {', '.join(moods[:5])}{'...' if len(moods) > 5 else ''}"

            result = self.plex_client.sync_playlist(
                title=playlist_title,
                tracks=sampled_deduped,
                summary=summary,
                library_key=library_key,
            )

            success = result.get("success", False)
            if success:
                self._persist_last_run_track_ids([t["rating_key"] for t in sampled_deduped])
                self._persist_after_success(playlist_title)
                self.logger.info(
                    f"Created playlist '{playlist_title}': {len(sampled_deduped)} tracks from {len(moods)} moods"
                )
            return success

        except Exception as e:
            self.logger.error(f"Error in mood playlist generator: {e}")
            raise
