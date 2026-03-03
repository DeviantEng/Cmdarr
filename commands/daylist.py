#!/usr/bin/env python3
"""
Daylist Command - Time-of-day playlist generator for Plex
Inspired by Meloday (https://github.com/trackstacker/meloday).
Uses Plex Sonic Analysis and listening history to build playlists that evolve throughout the day.
Plex only.
"""

import random
import re
from collections import Counter
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from clients.client_plex import PlexClient

from .command_base import BaseCommand

# Default time periods (Meloday-style): period name -> list of hours (0-23)
DEFAULT_TIME_PERIODS = {
    "Dawn": [3, 4, 5],
    "Early Morning": [6, 7, 8],
    "Morning": [9, 10, 11],
    "Afternoon": [12, 13, 14, 15],
    "Evening": [16, 17, 18],
    "Night": [19, 20, 21],
    "Late Night": [22, 23, 0, 1, 2],
}

# Period display order for iteration
PERIOD_ORDER = list(DEFAULT_TIME_PERIODS.keys())

# Period phrases for descriptions (Meloday-style)
PERIOD_PHRASES = {
    "Dawn": "at dawn",
    "Early Morning": "in the early morning",
    "Morning": "in the morning",
    "Afternoon": "during the afternoon",
    "Evening": "in the evening",
    "Night": "at night",
    "Late Night": "late at night",
}

# Path to bundled assets (from Meloday). daylist.py lives in commands/; assets are in commands/daylist/assets
_DAYLIST_ASSETS = Path(__file__).resolve().parent / "daylist" / "assets"
_MOODMAP_PATH = _DAYLIST_ASSETS / "moodmap.json"
_COVERS_DIR = _DAYLIST_ASSETS / "covers" / "flat"
_FONT_PATH = _DAYLIST_ASSETS / "fonts" / "Circular" / "Circular-Bold.ttf"

# Period -> cover filename (Meloday assets)
PERIOD_COVERS = {
    "Dawn": "dawn_blank.webp",
    "Early Morning": "early-morning_blank.webp",
    "Morning": "morning_blank.webp",
    "Afternoon": "afternoon_blank.webp",
    "Evening": "evening_blank.webp",
    "Night": "night_blank.webp",
    "Late Night": "late-night_blank.webp",
}


def _load_moodmap() -> dict[str, list[str]]:
    """Load mood map from bundled assets. Maps Plex mood names to descriptor variants."""
    try:
        if _MOODMAP_PATH.exists():
            import json

            with open(_MOODMAP_PATH, encoding="utf-8") as f:
                return json.load(f)
    except Exception:
        pass
    return {}


def _extract_tag_list(item: Any) -> list[str]:
    """Extract tag strings from Plex metadata (Genre, Mood). Handles dict or list of dicts."""
    if item is None:
        return []
    if isinstance(item, dict):
        tag = item.get("tag")
        return [str(tag)] if tag else []
    if isinstance(item, list):
        result = []
        for x in item:
            if isinstance(x, dict):
                tag = x.get("tag")
                if tag:
                    result.append(str(tag))
            elif isinstance(x, str):
                result.append(x)
        return result
    if isinstance(item, str):
        return [item]
    return []


class DaylistCommand(BaseCommand):
    """Time-of-day playlist generator using Plex Sonic Analysis and listening history."""

    def __init__(self, config=None):
        self.config_json = {}
        super().__init__(config)
        self.plex_client = PlexClient(self.config)
        self.last_run_stats = {}

    def get_description(self) -> str:
        """Return command description."""
        return "Builds playlists that evolve throughout the day using Plex Sonic Analysis and listening history. Plex only. Inspired by Meloday."

    def get_logger_name(self) -> str:
        """Return logger name."""
        return "daylist"

    def _get_time_periods(self) -> dict[str, list[int]]:
        """Get time periods from config or defaults."""
        custom = (self.config_json or {}).get("time_periods")
        if custom and isinstance(custom, dict):
            result = {}
            for period, hours in DEFAULT_TIME_PERIODS.items():
                if period in custom and isinstance(custom[period], (list, tuple)):
                    result[period] = [int(h) for h in custom[period] if isinstance(h, (int, float))]
                else:
                    result[period] = hours
            return result
        return dict(DEFAULT_TIME_PERIODS)

    def _get_timezone(self):
        """Get timezone for period determination."""
        from zoneinfo import ZoneInfo

        tz_str = ((self.config_json or {}).get("timezone") or "").strip()
        if not tz_str:
            from utils.timezone import get_scheduler_timezone

            return get_scheduler_timezone()
        try:
            return ZoneInfo(tz_str)
        except Exception:
            from utils.timezone import get_scheduler_timezone

            return get_scheduler_timezone()

    def _get_current_period(self) -> str:
        """Determine current time period from local time."""
        tz = self._get_timezone()
        now = datetime.now(tz)
        current_hour = now.hour
        time_periods = self._get_time_periods()
        for period in PERIOD_ORDER:
            if current_hour in time_periods.get(period, []):
                return period
        return "Late Night"

    def _should_skip(self, triggered_by: str = "scheduler") -> tuple[bool, str]:
        """Check if we should skip (period unchanged). Returns (skip, reason)."""
        # When manually requested: run if playlist doesn't exist (user may have deleted it)
        if triggered_by in ("manual", "api"):
            try:
                existing = self.plex_client.find_playlist_by_prefix("[Cmdarr] Daylist")
                if not existing:
                    return False, ""  # Playlist missing, always run
            except Exception as e:
                self.logger.debug(f"Playlist existence check failed: {e}")
                return False, ""  # On error, run to be safe

        current = self._get_current_period()
        last = (self.config_json or {}).get("last_daylist_period")
        if last and last == current:
            return True, f"Period unchanged ({current})"
        return False, ""

    def _clean_title(self, title: str) -> str:
        """Normalize title for deduplication (strip remix, live, feat., etc.)."""
        version_keywords = [
            "extended",
            "deluxe",
            "remaster",
            "remastered",
            "live",
            "acoustic",
            "edit",
            "version",
            "anniversary",
            "special edition",
            "radio edit",
            "album version",
            "original mix",
            "remix",
            "mix",
            "dub",
            "instrumental",
            "karaoke",
            "cover",
            "rework",
            "re-edit",
            "bootleg",
            "vip",
            "session",
            "alternate",
            "take",
        ]
        featuring_patterns = [
            r"\(feat\.?.*?\)",
            r"\[feat\.?.*?\]",
            r"\(ft\.?.*?\)",
            r"\[ft\.?.*?\]",
            r"\bfeat\.?\s+\w+",
            r"\bfeaturing\s+\w+",
            r"\bft\.?\s+\w+",
        ]
        t = (title or "").lower().strip()
        for p in featuring_patterns:
            t = re.sub(p, "", t, flags=re.IGNORECASE).strip()
        for kw in version_keywords:
            t = re.sub(rf"\b{kw}\b", "", t, flags=re.IGNORECASE).strip()
        t = re.sub(r"[\s-]+$", "", t)
        return t

    def _filter_low_rated(self, tracks: list[dict]) -> list[dict]:
        """Filter out 1-2 star rated tracks (userRating <= 2)."""
        filtered = []
        for t in tracks:
            rating = t.get("userRating")
            if rating is not None and float(rating) <= 2:
                continue
            filtered.append(t)
        return filtered

    def _process_tracks(
        self,
        tracks: list[dict],
        max_tracks: int,
        artist_limit_pct: float = 0.05,
        genre_limit_pct: float = 0.15,
    ) -> list[dict]:
        """Deduplicate and balance tracks by artist/genre."""
        filtered = self._filter_low_rated(tracks)
        seen = set()
        result = []
        artist_count = Counter()
        genre_count = Counter()
        artist_limit = max(1, int(max_tracks * artist_limit_pct))
        genre_limit = max(1, int(max_tracks * genre_limit_pct))

        for t in filtered:
            rk = t.get("ratingKey")
            title = (t.get("title") or "").strip()
            artist = (t.get("grandparentTitle") or "").strip().lower()
            if not rk or not title or not artist:
                continue
            title_clean = self._clean_title(title)
            key = (title_clean, artist)
            if key in seen:
                continue
            if artist_count[artist] >= artist_limit:
                continue
            genres = t.get("Genre") or []
            if isinstance(genres, dict):
                genres = [genres] if genres.get("tag") else []
            elif not isinstance(genres, list):
                genres = []
            genre = "Unknown"
            if genres:
                g0 = genres[0]
                genre = g0.get("tag", str(g0)) if isinstance(g0, dict) else str(g0)
            if genre_count[genre] >= genre_limit:
                continue
            seen.add(key)
            artist_count[artist] += 1
            genre_count[genre] += 1
            result.append(t)
        return result

    def _similarity_score(
        self,
        current_rk: str | int,
        candidate_rk: str | int,
        limit: int = 20,
        max_distance: float = 1.0,
    ) -> int:
        """Score: index in sonically similar list (lower = more similar). 100 if not found."""
        similars = self.plex_client.get_sonically_similar(
            str(current_rk), limit=limit, max_distance=max_distance
        )
        for i, s in enumerate(similars):
            if str(s.get("ratingKey")) == str(candidate_rk):
                return i
        return 100

    def _sort_by_sonic_similarity(
        self,
        tracks: list[dict],
        limit: int = 20,
        max_distance: float = 1.0,
    ) -> list[dict]:
        """Greedy sonic sort: chain tracks by similarity."""
        if len(tracks) < 2:
            return tracks
        remaining = list(tracks)
        sorted_list = []
        start_idx = random.randrange(len(remaining))
        current = remaining.pop(start_idx)
        sorted_list.append(current)
        while remaining:
            current_rk = current.get("ratingKey")
            next_track = min(
                remaining,
                key=lambda c: self._similarity_score(
                    current_rk, c.get("ratingKey"), limit, max_distance
                ),
            )
            sorted_list.append(next_track)
            remaining.remove(next_track)
            current = next_track
        return sorted_list

    def _parse_viewed_at(self, item: dict, tz=None) -> datetime | None:
        """Parse viewedAt from history item (unix timestamp).
        If tz is provided, returns timezone-aware datetime for comparison with exclude_start."""
        v = item.get("viewedAt")
        if v is None:
            return None
        try:
            ts = int(v)
            if tz:
                return datetime.fromtimestamp(ts, tz=tz)
            return datetime.fromtimestamp(ts)
        except (ValueError, TypeError):
            return None

    def _generate_playlist_title_and_description(
        self, period: str, tracks: list[dict]
    ) -> tuple[str, str]:
        """Generate Meloday-style title and description from track moods/genres using mood map."""
        moodmap = _load_moodmap()
        day_name = datetime.now(self._get_timezone()).strftime("%A")
        period_phrase = PERIOD_PHRASES.get(period, f"in the {period}")

        top_genres: list[str] = []
        top_moods: list[str] = []
        for t in tracks:
            for g in _extract_tag_list(t.get("Genre")):
                top_genres.append(g)
            for m in _extract_tag_list(t.get("Mood")):
                top_moods.append(m)

        genre_counts = Counter(top_genres)
        mood_counts = Counter(top_moods)
        sorted_genres = [g for g, _ in genre_counts.most_common()]
        sorted_moods = [m for m, _ in mood_counts.most_common()]

        most_common_genre = sorted_genres[0] if sorted_genres else "Eclectic"
        most_common_mood = sorted_moods[0] if sorted_moods else "Vibes"
        second_common_mood = sorted_moods[1] if len(sorted_moods) > 1 else None

        descriptor = "Vibrant"
        if second_common_mood and moodmap:
            variants = moodmap.get(second_common_mood)
            if variants:
                descriptor = random.choice(variants)
            else:
                for key in moodmap:
                    if key.lower() == second_common_mood.lower():
                        variants = moodmap[key]
                        if variants:
                            descriptor = random.choice(variants)
                        break

        title = f"[Cmdarr] Daylist for {most_common_mood} {descriptor} {most_common_genre} {day_name} {period}"
        title = title.replace("  ", " ").strip()

        max_styles = 6
        highlight_styles = sorted_genres[:3] + sorted_moods[:3]
        highlight_styles = [
            s for s in highlight_styles if s not in {most_common_genre, most_common_mood}
        ]
        highlight_styles = list(dict.fromkeys(highlight_styles))[:max_styles]
        while len(highlight_styles) < max_styles:
            for s in sorted_genres + sorted_moods:
                if s not in highlight_styles:
                    highlight_styles.append(s)
                if len(highlight_styles) >= max_styles:
                    break
            if len(highlight_styles) >= max_styles:
                break
            break

        if second_common_mood:
            desc = f"You listened to {most_common_mood} and {most_common_genre} tracks on {day_name} {period_phrase}. "
        else:
            desc = f"You listened to {most_common_genre} and {most_common_mood} tracks on {day_name} {period_phrase}. "
        if highlight_styles:
            if len(highlight_styles) == 1:
                desc += f"Here's some {highlight_styles[0]} tracks as well."
            else:
                desc += f"Here's some {', '.join(highlight_styles[:-1])}, and {highlight_styles[-1]} tracks as well."
        desc += " Built from your Plex listening history and Sonic Analysis. Inspired by Meloday."
        return title, desc

    def _generate_cover_image(self, period: str, title: str) -> bytes | None:
        """Generate cover image with text overlay (Meloday-style). Returns JPEG bytes or None on failure."""
        try:
            from PIL import Image, ImageDraw, ImageFilter, ImageFont

            cover_file = PERIOD_COVERS.get(period)
            if not cover_file:
                return None
            cover_path = _COVERS_DIR / cover_file
            if not cover_path.exists():
                self.logger.warning(f"Cover not found: {cover_path} (assets path: {_COVERS_DIR})")
                return None

            image = Image.open(cover_path).convert("RGBA")
            # Strip "[Cmdarr] Daylist for " prefix for display (shorter text on cover)
            display_text = title
            for prefix in ("[Cmdarr] Daylist for ", "[Cmdarr] Daylist "):
                if display_text.startswith(prefix):
                    display_text = display_text[len(prefix) :].strip()
                    break

            shadow_layer = Image.new("RGBA", image.size, (0, 0, 0, 0))
            text_layer = Image.new("RGBA", image.size, (255, 255, 255, 0))
            shadow_draw = ImageDraw.Draw(shadow_layer)
            text_draw = ImageDraw.Draw(text_layer)

            # Prefer bundled Circular font (from Meloday), fall back to system fonts
            font_paths = [
                str(_FONT_PATH),  # Bundled from Meloday
                "/System/Library/Fonts/Helvetica.ttc",  # macOS
                "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",  # Linux
                "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
            ]
            font_main = ImageFont.load_default()
            for fp in font_paths:
                try:
                    if fp and Path(fp).exists():
                        font_main = ImageFont.truetype(fp, 56)
                        break
                except OSError:
                    continue

            text_box_width = 550
            text_box_right = image.width - 80
            text_box_left = text_box_right - text_box_width
            y = 80
            shadow_offset = 2
            shadow_blur = 30

            def wrap_text(txt: str, font, draw, max_w: int) -> list[str]:
                words = txt.split()
                lines = []
                current = ""
                for w in words:
                    test = f"{current} {w}".strip() if current else w
                    bbox = draw.textbbox((0, 0), test, font=font)
                    if bbox[2] - bbox[0] <= max_w:
                        current = test
                    else:
                        if current:
                            lines.append(current)
                        current = w
                if current:
                    lines.append(current)
                return lines

            lines = wrap_text(display_text, font_main, text_draw, text_box_width)
            for line in lines:
                bbox = text_draw.textbbox((0, 0), line, font=font_main)
                lw = bbox[2] - bbox[0]
                x = text_box_left + (text_box_width - lw) // 2
                shadow_draw.text(
                    (x + shadow_offset, y + shadow_offset),
                    line,
                    font=font_main,
                    fill=(0, 0, 0, 120),
                )
                text_draw.text((x, y), line, font=font_main, fill=(255, 255, 255, 255))
                y += bbox[3] - bbox[1] + 8

            shadow_layer = shadow_layer.filter(ImageFilter.GaussianBlur(radius=shadow_blur))
            combined = Image.alpha_composite(image, shadow_layer)
            combined = Image.alpha_composite(combined, text_layer)

            import io

            buf = io.BytesIO()
            combined.convert("RGB").save(buf, format="JPEG", quality=90)
            return buf.getvalue()
        except Exception as e:
            self.logger.warning(f"Cover generation failed: {e}", exc_info=True)
            return None

    async def execute(self) -> bool:
        """Execute daylist command."""
        try:
            self.logger.info("Starting Daylist command")

            config = self.config_json or {}
            account_id = config.get("plex_history_account_id")
            if not account_id:
                self.logger.error("No plex_history_account_id configured")
                return False

            # Resolve library
            music_libs = self.plex_client.get_music_libraries()
            chosen = self.plex_client._resolve_music_library(music_libs)
            if not chosen:
                self.logger.error("No music library found")
                return False
            library_key = chosen["key"]
            self.logger.info(f"Using library: {chosen.get('title', library_key)}")

            # Period check - skip if unchanged (manual/api: also run when playlist missing)
            triggered_by = (config or {}).get("triggered_by", "scheduler")
            skip, reason = self._should_skip(triggered_by=triggered_by)
            if skip:
                self.logger.info(f"Skipping: {reason}")
                self.last_run_stats = {"skipped": True, "reason": reason}
                return True

            current_period = self._get_current_period()
            self.logger.info(f"Current period: {current_period}")

            # Config
            exclude_days = int(config.get("exclude_played_days", 3))
            lookback_days = int(config.get("history_lookback_days", 45))
            max_tracks = int(config.get("max_tracks", 50))
            sonic_limit = int(config.get("sonic_similar_limit", 8))
            sonic_similarity_limit = int(config.get("sonic_similarity_limit", 50))
            sonic_similarity_distance = float(config.get("sonic_similarity_distance", 1.0))
            historical_ratio = float(config.get("historical_ratio", 0.3))

            time_periods = self._get_time_periods()
            period_hours = set(time_periods.get(current_period, [0, 1, 2]))

            tz = self._get_timezone()
            now = datetime.now(tz)
            history_start = now - timedelta(days=lookback_days)
            exclude_start = now - timedelta(days=exclude_days)

            # Fetch history
            history_raw = self.plex_client.get_play_history(
                library_key=library_key,
                account_id=account_id,
                mindate=history_start,
                maxresults=2000,
            )

            # Filter: type=track, not in exclude window. Use ALL recent history - period is for
            # title/cover/ordering only; restricting to period hours would exclude most plays.
            history_items = []
            excluded_keys = set()
            for h in history_raw:
                if str(h.get("type", "")) != "track":
                    continue
                viewed = self._parse_viewed_at(h, tz)
                if viewed and viewed >= exclude_start:
                    excluded_keys.add(str(h.get("ratingKey")))
                if viewed and str(h.get("ratingKey")) not in excluded_keys:
                    history_items.append(h)

            self.logger.info(
                f"History: {len(history_raw)} raw, {len(history_items)} tracks (excluded {len(excluded_keys)} recent)"
            )
            if not history_items:
                self.logger.warning(
                    "No play history in lookback window. Check plex_history_account_id and that "
                    "tracks (not albums/videos) were played in the music library."
                )

            # Balance popular/rare
            track_counts = Counter(h.get("ratingKey") for h in history_items)
            sorted_hist = sorted(
                history_items,
                key=lambda t: track_counts.get(t.get("ratingKey"), 0),
                reverse=True,
            )
            split_idx = max(1, len(sorted_hist) // 4)
            popular = sorted_hist[:split_idx]
            rare = sorted_hist[split_idx:]
            guaranteed_count = int(max_tracks * historical_ratio)
            historical = random.sample(
                rare, min(len(rare), int(max_tracks * 0.75))
            ) + random.sample(popular, min(len(popular), int(max_tracks * 0.25)))
            historical = random.sample(historical, min(guaranteed_count, len(historical)))

            # Fetch sonically similar
            similar_tracks = []
            for h in historical:
                rk = h.get("ratingKey")
                if not rk:
                    continue
                sims = self.plex_client.get_sonically_similar(
                    str(rk), limit=sonic_limit, max_distance=sonic_similarity_distance
                )
                for s in sims:
                    if str(s.get("ratingKey")) in excluded_keys:
                        continue
                    similar_tracks.append(s)

            # Combine and process
            all_tracks = historical + similar_tracks
            final_tracks = self._process_tracks(all_tracks, max_tracks)

            # Fill to max_tracks if needed (simplified - could loop like Meloday)
            final_rks = {str(t.get("ratingKey")) for t in final_tracks}
            attempts = 0
            while len(final_tracks) < max_tracks and attempts < 3:
                attempts += 1
                more_hist = [h for h in history_items if str(h.get("ratingKey")) not in final_rks]
                more_sim = []
                for t in final_tracks[:10]:
                    sims = self.plex_client.get_sonically_similar(
                        str(t.get("ratingKey")),
                        limit=sonic_limit,
                        max_distance=sonic_similarity_distance,
                    )
                    more_sim.extend(sims)
                candidates = [
                    t for t in (more_hist + more_sim) if str(t.get("ratingKey")) not in final_rks
                ]
                added = self._process_tracks(candidates, max_tracks - len(final_tracks))
                for t in added[: max_tracks - len(final_tracks)]:
                    final_tracks.append(t)
                    final_rks.add(str(t.get("ratingKey")))
                if not added:
                    break

            final_tracks = final_tracks[:max_tracks]

            # Sort: first=earliest played, last=most recent, middle=sonic chain
            def viewed_key(t):
                v = self._parse_viewed_at(t, tz)
                return v if v else datetime.max

            by_viewed = sorted(
                [
                    t
                    for t in final_tracks
                    if self._parse_viewed_at(t, tz)
                    and self._parse_viewed_at(t, tz).hour in period_hours
                ],
                key=viewed_key,
            )
            first_track = by_viewed[0] if by_viewed else (final_tracks[0] if final_tracks else None)
            last_track = (
                by_viewed[-1]
                if len(by_viewed) > 1
                else (final_tracks[-1] if final_tracks else None)
            )
            middle = [t for t in final_tracks if t != first_track and t != last_track]

            if middle:
                middle = self._sort_by_sonic_similarity(
                    middle, limit=sonic_similarity_limit, max_distance=sonic_similarity_distance
                )
            ordered = []
            if first_track:
                ordered.append(first_track)
            ordered.extend(middle)
            if last_track and last_track != first_track:
                ordered.append(last_track)

            if not ordered:
                self.logger.warning("No tracks to add to playlist")
                return True

            # Generate mood-based title and description (Meloday-style, uses moodmap.json)
            playlist_title, description = self._generate_playlist_title_and_description(
                current_period, ordered
            )

            rating_keys = [str(t.get("ratingKey")) for t in ordered if t.get("ratingKey")]

            success = self.plex_client.create_or_update_playlist(
                playlist_title,
                rating_keys,
                description,
                match_prefix="[Cmdarr] Daylist",
            )

            if not success:
                self.logger.error("Failed to create/update playlist")
                return False

            # Upload dynamic cover (Meloday-style: period-specific image with title overlay)
            playlist = self.plex_client.find_playlist_by_prefix("[Cmdarr] Daylist")
            if playlist:
                cover_bytes = self._generate_cover_image(current_period, playlist_title)
                if cover_bytes:
                    if self.plex_client.upload_playlist_poster(playlist["ratingKey"], cover_bytes):
                        self.logger.info("Daylist cover uploaded")
                    else:
                        self.logger.warning("Failed to upload daylist cover")

            # Persist last_daylist_period to database
            config["last_daylist_period"] = current_period
            self.config_json = config
            try:
                from database.database import get_database_manager

                db = get_database_manager()
                session = db.get_config_session_sync()
                try:
                    from database.config_models import CommandConfig

                    cmd_name = config.get("command_name", "daylist_00001")
                    cmd = (
                        session.query(CommandConfig)
                        .filter(CommandConfig.command_name == cmd_name)
                        .first()
                    )
                    if cmd:
                        cmd.config_json = dict(cmd.config_json or {})
                        cmd.config_json["last_daylist_period"] = current_period
                        session.commit()
                finally:
                    session.close()
            except Exception as e:
                self.logger.warning(f"Could not persist last_daylist_period: {e}")

            self.last_run_stats = {
                "success": True,
                "period": current_period,
                "track_count": len(rating_keys),
            }
            self.logger.info(f"Daylist updated: {current_period}, {len(rating_keys)} tracks")
            return True

        except Exception as e:
            self.logger.exception(f"Daylist failed: {e}")
            self.last_run_stats = {"success": False, "error": str(e)}
            return False
