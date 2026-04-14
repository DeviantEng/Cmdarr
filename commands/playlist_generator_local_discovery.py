#!/usr/bin/env python3
"""
Local Discovery Playlist Generator - Top artists + sonically similar + lesser-played.
Automated "Sonic Adventure" style playlist. Plex only.
"""

import random
import secrets
from collections import Counter
from datetime import datetime, timedelta
from typing import Any

from clients.client_plex import PlexClient
from utils.library_cache_manager import get_library_cache_manager

from .command_base import BaseCommand

PLAYLIST_TITLE_PREFIX = "[Cmdarr] Local Discovery"


def _parse_viewed_at(item: dict, tz=None) -> datetime | None:
    """Parse viewedAt from history item (unix timestamp)."""
    v = item.get("viewedAt")
    if v is None:
        return None
    try:
        ts = int(v)
        if tz:
            return datetime.fromtimestamp(ts, tz=tz)
        return datetime.fromtimestamp(ts)
    except ValueError, TypeError:
        return None


class PlaylistGeneratorLocalDiscoveryCommand(BaseCommand):
    """Generate playlist from top played artists + sonically similar + freshness."""

    def __init__(self, config=None):
        self.config_json = {}
        super().__init__(config)
        self.plex_client = PlexClient(self.config)
        self.library_cache_manager = get_library_cache_manager(self.config)

    def get_description(self) -> str:
        return (
            "Automated local discovery: top artists + sonically similar + lesser-played. "
            "Randomized each run. Plex only."
        )

    def get_logger_name(self) -> str:
        return "playlist_generator.local_discovery"

    def _ensure_display_name(self, expected: str) -> None:
        """Ensure command display_name matches playlist name for consistency."""
        try:
            from database.config_models import CommandConfig
            from database.database import get_database_manager

            cmd_name = (self.config_json or {}).get("command_name", "")
            if not cmd_name:
                return
            db = get_database_manager()
            session = db.get_config_session_sync()
            try:
                cmd = (
                    session.query(CommandConfig)
                    .filter(CommandConfig.command_name == cmd_name)
                    .first()
                )
                if cmd and cmd.display_name != expected:
                    cmd.display_name = expected
                    session.commit()
            finally:
                session.close()
        except Exception as e:
            self.logger.warning(f"Could not update display_name: {e}")

    async def execute(self) -> bool:
        try:
            config = self.config_json or {}
            account_id = config.get("plex_history_account_id")
            if not account_id:
                self.logger.error("plex_history_account_id is required")
                return False

            accounts = self.plex_client.get_accounts()
            account_name = next(
                (a["name"] for a in accounts if a["id"] == str(account_id)),
                str(account_id),
            )
            self.logger.info(f"Starting Local Discovery command for user: {account_name}")

            user_token = self.plex_client.get_token_for_user(str(account_id))
            if not user_token:
                self.logger.error(
                    f"Could not resolve token for user {account_id}. "
                    "User must be admin or in shared_servers."
                )
                return False

            # Always use resolved library (PLEX_LIBRARY_NAME / Music / first) - never use stored
            # target_library_key, which may point to wrong library (e.g. Audiobooks when Music desired)
            library_key = None
            resolved_lib = None
            if hasattr(self.plex_client, "get_resolved_library"):
                resolved_lib = self.plex_client.get_resolved_library()
                library_key = resolved_lib["key"] if resolved_lib else None
            if not library_key:
                self.logger.error(
                    "No Plex music library found. Configure PLEX_LIBRARY_NAME or ensure a music library exists."
                )
                return False
            self.logger.info(f"Using library: {resolved_lib.get('title', '?')} (key={library_key})")

            lookback_days = int(config.get("lookback_days", 90))
            exclude_played_days = int(config.get("exclude_played_days", 3))
            top_artists_count = int(config.get("top_artists_count", 10))
            artist_pool_size = int(config.get("artist_pool_size", 20))
            max_tracks = int(config.get("max_tracks", 50))
            sonic_limit = int(config.get("sonic_similar_limit", 15))
            sonic_distance = float(config.get("sonic_similarity_distance", 0.25))

            top_artists_count = max(1, min(20, top_artists_count))
            artist_pool_size = max(top_artists_count, min(50, artist_pool_size))
            max_tracks = max(1, min(200, max_tracks))

            from utils.timezone import get_scheduler_timezone

            tz = get_scheduler_timezone()
            now = datetime.now(tz)
            history_start = now - timedelta(days=lookback_days)
            exclude_start = now - timedelta(days=exclude_played_days)

            # 1. Fetch play history
            history_raw = self.plex_client.get_play_history(
                library_key=library_key,
                account_id=account_id,
                mindate=history_start,
                maxresults=3000,
            )

            # Filter type=track, build excluded set (played in last N days)
            history_items = []
            excluded_keys = set()
            for h in history_raw:
                if str(h.get("type", "")) != "track":
                    continue
                viewed = _parse_viewed_at(h, tz)
                if viewed and viewed >= exclude_start:
                    excluded_keys.add(str(h.get("ratingKey")))
                if (
                    viewed
                    and viewed >= history_start
                    and str(h.get("ratingKey")) not in excluded_keys
                ):
                    history_items.append(h)

            if not history_items:
                self.logger.warning("No play history in lookback window")
                return True

            # 2. Aggregate by artist, rank, take pool, random sample
            artist_plays: Counter[str] = Counter()
            artist_tracks: dict[str, list[dict]] = {}
            for h in history_items:
                artist = (h.get("grandparentTitle") or "").strip()
                if not artist:
                    continue
                artist_plays[artist] += 1
                if artist not in artist_tracks:
                    artist_tracks[artist] = []
                artist_tracks[artist].append(h)

            ranked = [a for a, _ in artist_plays.most_common(artist_pool_size)]
            if not ranked:
                self.logger.warning("No artists in history")
                return True

            rng = random.Random(secrets.randbits(64))
            chosen_artists = rng.sample(ranked, min(top_artists_count, len(ranked)))

            # 3. For each artist: pick random seed tracks from their history
            seed_tracks: list[dict] = []
            for artist in chosen_artists:
                tracks = artist_tracks.get(artist, [])
                eligible = [t for t in tracks if str(t.get("ratingKey")) not in excluded_keys]
                if not eligible:
                    continue
                n = min(3, len(eligible))
                picks = rng.sample(eligible, n)
                seed_tracks.extend(picks)

            if not seed_tracks:
                self.logger.warning("No eligible seed tracks after exclusions")
                return True

            # 4. Get sonically similar for each seed
            similar_tracks: list[dict] = []
            seen_rk: set[str] = set()
            for t in seed_tracks:
                rk = t.get("ratingKey")
                if not rk:
                    continue
                sims = self.plex_client.get_sonically_similar(
                    str(rk),
                    limit=sonic_limit,
                    max_distance=sonic_distance,
                    library_key=library_key,
                )
                for s in sims:
                    sk = str(s.get("ratingKey", ""))
                    if sk and sk not in excluded_keys and sk not in seen_rk:
                        seen_rk.add(sk)
                        similar_tracks.append(s)

            # 5. Combine: historical ratio from seed_tracks, rest from similar
            historical_ratio = float(config.get("historical_ratio", 0.3))
            historical_ratio = max(0.0, min(1.0, historical_ratio))
            n_historical = int(max_tracks * historical_ratio)
            n_similar = max_tracks - n_historical

            # Dedupe seed_tracks by ratingKey
            seed_deduped: list[dict] = []
            seed_seen: set[str] = set()
            for t in seed_tracks:
                k = str(t.get("ratingKey", ""))
                if k and k not in seed_seen and k not in excluded_keys:
                    seed_seen.add(k)
                    seed_deduped.append(t)

            historical_pool = [
                t for t in seed_deduped if str(t.get("ratingKey")) not in excluded_keys
            ]
            historical_sample = (
                rng.sample(historical_pool, min(n_historical, len(historical_pool)))
                if historical_pool
                else []
            )

            similar_pool = [
                t for t in similar_tracks if str(t.get("ratingKey")) not in excluded_keys
            ]
            final_rks = {str(t.get("ratingKey")) for t in historical_sample}
            similar_candidates = [
                t for t in similar_pool if str(t.get("ratingKey")) not in final_rks
            ]
            similar_sample = (
                rng.sample(similar_candidates, min(n_similar, len(similar_candidates)))
                if similar_candidates
                else []
            )

            final_tracks = historical_sample + similar_sample
            rng.shuffle(final_tracks)
            final_tracks = final_tracks[:max_tracks]

            # 6. Convert to sync_playlist format
            tracks_for_playlist: list[dict[str, Any]] = []
            for t in final_tracks:
                rk = t.get("ratingKey")
                artist = (t.get("grandparentTitle") or "").strip()
                title = (t.get("title") or "").strip()
                album = (t.get("parentTitle") or "").strip()
                if rk and title and artist:
                    tracks_for_playlist.append(
                        {
                            "rating_key": str(rk),
                            "artist": artist,
                            "track": title,
                            "album": album,
                        }
                    )

            if not tracks_for_playlist:
                self.logger.warning("No tracks for playlist")
                return True

            playlist_title = PLAYLIST_TITLE_PREFIX
            summary = (
                f"Top {top_artists_count} artists from {lookback_days}d history + sonic expansion"
            )

            plex_for_playlist = PlexClient(self.config, token_override=user_token)
            result = plex_for_playlist.sync_playlist(
                title=playlist_title,
                tracks=tracks_for_playlist,
                summary=summary,
                library_key=library_key,
            )

            success = result.get("success", False)
            if success:
                self.logger.info(
                    f"Created playlist for {account_name}: '{playlist_title}' with "
                    f"{len(tracks_for_playlist)} tracks"
                )
            return success

        except Exception as e:
            self.logger.error(f"Error in local discovery generator: {e}")
            raise
