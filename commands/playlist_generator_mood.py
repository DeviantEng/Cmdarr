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

PLAYLIST_TITLE_PREFIX = "[Cmdarr Mood]"


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

            playlist_name = config.get("playlist_name", "Mood Playlist")
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
            track_to_data: dict[str, dict[str, Any]] = {}
            track_to_mood_count: dict[str, int] = defaultdict(int)

            for mood in moods:
                tracks = self.plex_client.get_tracks_by_mood(
                    library_key, mood, limit=500, offset=0
                )
                for t in tracks:
                    key = str(t["key"])
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
            playlist_title = f"{PLAYLIST_TITLE_PREFIX} {playlist_name}"
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
                self.logger.info(
                    f"Created playlist '{playlist_title}': {len(sampled_deduped)} tracks from {len(moods)} moods"
                )
            return success

        except Exception as e:
            self.logger.error(f"Error in mood playlist generator: {e}")
            raise
