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
        # Manual/api: always run (user may have changed settings, deleted playlist, or wants to regenerate)
        if triggered_by in ("manual", "api"):
            return False, ""

        # Scheduled runs only: skip if period unchanged
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

    def _daylist_track_title(self, t: dict) -> str:
        return (t.get("title") or t.get("originalTitle") or "").strip()

    def _daylist_artist_key(self, t: dict) -> str:
        a = (t.get("grandparentTitle") or "").strip().lower()
        if a:
            return a
        for tag in _extract_tag_list(t.get("Artist")):
            s = tag.strip().lower()
            if s:
                return s
        gpk = t.get("grandparentRatingKey")
        if gpk is not None and str(gpk).strip():
            return f"__gpk_{gpk}"
        return ""

    def _balance_state_from_tracks(self, tracks: list[dict]) -> tuple[set, Counter]:
        seen: set[tuple[str, str]] = set()
        artist_count: Counter = Counter()
        for t in tracks:
            rk = t.get("ratingKey")
            title = self._daylist_track_title(t)
            artist = self._daylist_artist_key(t)
            if not rk or not title or not artist:
                continue
            title_clean = self._clean_title(title)
            key = (title_clean, artist)
            if key in seen:
                continue
            seen.add(key)
            artist_count[artist] += 1
        return seen, artist_count

    def _process_tracks(
        self,
        tracks: list[dict],
        *,
        artist_limit: int,
        seen: set | None = None,
        artist_count: Counter | None = None,
        max_to_add: int | None = None,
    ) -> list[dict]:
        filtered = self._filter_low_rated(tracks)
        seen = set(seen) if seen is not None else set()
        artist_count = Counter(artist_count) if artist_count is not None else Counter()
        result = []

        for t in filtered:
            if max_to_add is not None and len(result) >= max_to_add:
                break
            rk = t.get("ratingKey")
            title = self._daylist_track_title(t)
            artist = self._daylist_artist_key(t)
            if not rk or not title or not artist:
                continue
            title_clean = self._clean_title(title)
            key = (title_clean, artist)
            if key in seen:
                continue
            if artist_count[artist] >= artist_limit:
                continue
            seen.add(key)
            artist_count[artist] += 1
            result.append(t)
        return result

    def _similarity_score(
        self,
        current_rk: str | int,
        candidate_rk: str | int,
        limit: int = 20,
        max_distance: float = 1.0,
        library_key: str | None = None,
    ) -> int:
        """Score: index in sonically similar list (lower = more similar). 100 if not found."""
        similars = self.plex_client.get_sonically_similar(
            str(current_rk),
            limit=limit,
            max_distance=max_distance,
            library_key=library_key,
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
        library_key: str | None = None,
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
                    current_rk, c.get("ratingKey"), limit, max_distance, library_key
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
        except ValueError, TypeError:
            return None

    def _last_played_at_for_similar(self, item: dict, tz) -> datetime | None:
        """Best-effort last play time from track metadata (Plex may expose lastViewedAt / viewedAt)."""
        for key in ("lastViewedAt", "viewedAt"):
            v = item.get(key)
            if v is None:
                continue
            try:
                ts = int(v)
                if tz:
                    return datetime.fromtimestamp(ts, tz=tz)
                return datetime.fromtimestamp(ts)
            except ValueError, TypeError:
                continue
        return None

    def _similar_played_inside_exclude_window(
        self, item: dict, exclude_start: datetime, tz
    ) -> bool:
        lp = self._last_played_at_for_similar(item, tz)
        return lp is not None and lp >= exclude_start

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

        # Use primary (most common) or secondary mood for descriptor (Meloday uses secondary)
        use_primary = bool((self.config_json or {}).get("use_primary_mood", False))
        mood_for_descriptor = most_common_mood if use_primary else second_common_mood

        descriptor = "Vibrant"
        if mood_for_descriptor and moodmap:
            variants = moodmap.get(mood_for_descriptor)
            if variants:
                descriptor = random.choice(variants)
            else:
                for key in moodmap:
                    if key.lower() == mood_for_descriptor.lower():
                        variants = moodmap[key]
                        if variants:
                            descriptor = random.choice(variants)
                        break

        playlist_title = "[Cmdarr] Daylist"
        cover_text = (
            f"{most_common_mood} {descriptor} {most_common_genre} {day_name} {period}".replace(
                "  ", " "
            ).strip()
        )

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
        return playlist_title, desc, cover_text

    def _generate_cover_image(self, period: str, cover_text: str) -> bytes | None:
        """Generate cover image with text overlay (Meloday-style). Returns JPEG bytes or None on failure."""
        try:
            import logging

            logging.getLogger("PIL").setLevel(logging.WARNING)
            from PIL import Image, ImageDraw, ImageFilter, ImageFont

            cover_file = PERIOD_COVERS.get(period)
            if not cover_file:
                return None
            cover_path = _COVERS_DIR / cover_file
            if not cover_path.exists():
                self.logger.warning(f"Cover not found: {cover_path} (assets path: {_COVERS_DIR})")
                return None

            image = Image.open(cover_path).convert("RGBA")
            display_text = (cover_text or period).strip()

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
            mood_font_size = 90  # ~20% smaller than original 112
            branding_font_size = 110  # Larger than mood; "[Cmdarr] Daylist" at bottom
            font_mood = ImageFont.load_default()
            font_branding = ImageFont.load_default()
            for fp in font_paths:
                try:
                    if fp and Path(fp).exists():
                        font_mood = ImageFont.truetype(fp, mood_font_size)
                        font_branding = ImageFont.truetype(fp, branding_font_size)
                        break
                except OSError:
                    continue
            else:
                self.logger.warning(
                    "No truetype font found, using default (fixed size). "
                    "Cover text may appear small."
                )

            text_box_width = 600
            text_box_right = image.width - 80
            text_box_left = text_box_right - text_box_width
            y = 60
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

            # Mood adjectives in upper right (smaller font)
            lines = wrap_text(display_text, font_mood, text_draw, text_box_width)
            for line in lines:
                bbox = text_draw.textbbox((0, 0), line, font=font_mood)
                lw = bbox[2] - bbox[0]
                x = text_box_left + (text_box_width - lw) // 2
                shadow_draw.text(
                    (x + shadow_offset, y + shadow_offset),
                    line,
                    font=font_mood,
                    fill=(0, 0, 0, 120),
                )
                text_draw.text((x, y), line, font=font_mood, fill=(255, 255, 255, 255))
                y += bbox[3] - bbox[1] + 12

            # Semi-transparent dark bar at bottom (Spotify-style) for readability
            branding_text = "[Cmdarr] Daylist"
            bbox_brand = text_draw.textbbox((0, 0), branding_text, font=font_branding)
            brand_w = bbox_brand[2] - bbox_brand[0]
            brand_h = bbox_brand[3] - bbox_brand[1]
            bar_height = brand_h + 80  # padding above and below text
            bar_top = image.height - bar_height
            bar_layer = Image.new("RGBA", image.size, (0, 0, 0, 0))
            bar_draw = ImageDraw.Draw(bar_layer)
            bar_draw.rectangle(
                [(0, bar_top), (image.width, image.height)],
                fill=(0, 0, 0, 180),
            )
            brand_x = (image.width - brand_w) // 2
            brand_y = bar_top + (bar_height - brand_h) // 2
            shadow_draw.text(
                (brand_x + shadow_offset, brand_y + shadow_offset),
                branding_text,
                font=font_branding,
                fill=(0, 0, 0, 120),
            )
            text_draw.text(
                (brand_x, brand_y), branding_text, font=font_branding, fill=(255, 255, 255, 255)
            )

            shadow_layer = shadow_layer.filter(ImageFilter.GaussianBlur(radius=shadow_blur))
            combined = Image.alpha_composite(image, shadow_layer)
            combined = Image.alpha_composite(combined, bar_layer)
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
            config = self.config_json or {}
            account_id = config.get("plex_history_account_id")
            if not account_id:
                self.logger.error("No plex_history_account_id configured")
                return False

            accounts = self.plex_client.get_accounts()
            account_name = next(
                (a["name"] for a in accounts if a["id"] == str(account_id)),
                str(account_id),
            )
            self.logger.info(f"Starting Daylist command for user: {account_name}")

            user_token = self.plex_client.get_token_for_user(str(account_id))
            if not user_token:
                self.logger.error(
                    f"Could not resolve token for user {account_id}. "
                    "User must be admin or in shared_servers."
                )
                return False

            # Resolve library
            chosen = self.plex_client.get_resolved_library()
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
            sonic_limit = int(config.get("sonic_similar_limit", 10))
            sonic_similarity_limit = int(config.get("sonic_similarity_limit", 50))
            sonic_similarity_distance = float(config.get("sonic_similarity_distance", 0.8))
            historical_ratio = float(config.get("historical_ratio", 0.3))
            artist_limit = min(2, max_tracks)

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

            # Filter: type=track, not in exclude window (full lookback for pool + exclusions).
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
                f"History for {account_name}: {len(history_raw)} raw, {len(history_items)} tracks "
                f"(excluded {len(excluded_keys)} recent)"
            )
            if not history_items:
                self.logger.warning(
                    f"No play history for {account_name} in lookback window. Check plex_history_account_id "
                    "and that tracks (not albums/videos) were played in the music library."
                )

            # Meloday-style: popular/rare split on plays in the *current period* hours when enough data.
            min_period_plays = max(25, max_tracks // 2)
            seed_history = [
                h
                for h in history_items
                if self._parse_viewed_at(h, tz)
                and self._parse_viewed_at(h, tz).hour in period_hours
            ]
            if len(seed_history) < min_period_plays:
                self.logger.info(
                    f"Period-filtered plays ({len(seed_history)}) below threshold {min_period_plays}; "
                    "using full lookback for seed selection"
                )
                seed_history = list(history_items)
            else:
                self.logger.info(
                    f"Seed selection from {current_period} hours: {len(seed_history)} plays "
                    f"(full lookback {len(history_items)} tracks)"
                )

            # Balance popular/rare (on seed_history)
            track_counts = Counter(h.get("ratingKey") for h in seed_history)
            sorted_hist = sorted(
                seed_history,
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

            similar_tracks = []
            for h in historical:
                rk = h.get("ratingKey")
                if not rk:
                    continue
                sims = self.plex_client.get_sonically_similar(
                    str(rk),
                    limit=sonic_limit,
                    max_distance=sonic_similarity_distance,
                    library_key=library_key,
                )
                for s in sims:
                    if str(s.get("ratingKey")) in excluded_keys:
                        continue
                    if self._similar_played_inside_exclude_window(s, exclude_start, tz):
                        continue
                    similar_tracks.append(s)

            # Combine and process
            all_tracks = historical + similar_tracks
            final_tracks = self._process_tracks(
                all_tracks,
                artist_limit=artist_limit,
            )
            fill_ref_cap = min(max(80, max_tracks * 2), 150)
            final_rks = {str(t.get("ratingKey")) for t in final_tracks}
            seen, ac = self._balance_state_from_tracks(final_tracks)
            attempts = 0
            while len(final_tracks) < max_tracks and attempts < 6:
                attempts += 1
                more_hist = [h for h in history_items if str(h.get("ratingKey")) not in final_rks]
                more_sim = []
                ref_pool = list(final_tracks)
                if len(ref_pool) > fill_ref_cap:
                    ref_pool = random.sample(ref_pool, fill_ref_cap)
                for t in ref_pool:
                    sims = self.plex_client.get_sonically_similar(
                        str(t.get("ratingKey")),
                        limit=sonic_limit,
                        max_distance=sonic_similarity_distance,
                        library_key=library_key,
                    )
                    for s in sims:
                        sk = str(s.get("ratingKey", ""))
                        if sk in excluded_keys:
                            continue
                        if self._similar_played_inside_exclude_window(s, exclude_start, tz):
                            continue
                        more_sim.append(s)
                candidates = [
                    t for t in (more_hist + more_sim) if str(t.get("ratingKey")) not in final_rks
                ]
                random.shuffle(candidates)
                need = max_tracks - len(final_tracks)
                added = self._process_tracks(
                    candidates,
                    artist_limit=artist_limit,
                    seen=seen,
                    artist_count=ac,
                    max_to_add=need,
                )
                for t in added:
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
                    middle,
                    limit=sonic_similarity_limit,
                    max_distance=sonic_similarity_distance,
                    library_key=library_key,
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
            playlist_title, description, cover_text = self._generate_playlist_title_and_description(
                current_period, ordered
            )

            rating_keys = [str(t.get("ratingKey")) for t in ordered if t.get("ratingKey")]

            plex_for_playlist = PlexClient(self.config, token_override=user_token)
            success = plex_for_playlist.create_or_update_playlist(
                playlist_title,
                rating_keys,
                description,
                match_prefix="[Cmdarr] Daylist",
            )

            if not success:
                self.logger.error("Failed to create/update playlist")
                return False

            # Upload dynamic cover (Meloday-style: period-specific image with title overlay)
            playlist = plex_for_playlist.find_playlist_by_prefix("[Cmdarr] Daylist")
            if playlist:
                cover_bytes = self._generate_cover_image(current_period, cover_text)
                if cover_bytes:
                    if plex_for_playlist.upload_playlist_poster(playlist["ratingKey"], cover_bytes):
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
            self.logger.info(
                f"Daylist updated for {account_name}: {current_period}, {len(rating_keys)} tracks"
            )
            return True

        except Exception as e:
            self.logger.exception(f"Daylist failed: {e}")
            self.last_run_stats = {"success": False, "error": str(e)}
            return False
