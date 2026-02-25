"""
Timezone utilities for scheduler and cron. Handles missing tzdata (e.g. minimal Docker images).
Priority: TZ env (if set) > SCHEDULER_TIMEZONE config > UTC.
"""
import os
from datetime import datetime, timezone


def get_scheduler_timezone():
    """
    Get timezone for cron schedules.
    Priority: TZ env (Docker) > SCHEDULER_TIMEZONE config > UTC.
    Falls back to datetime.timezone.utc when ZoneInfo fails (e.g. missing tzdata).
    """
    from services.config_service import config_service
    tz_str = os.environ.get('TZ') or config_service.get('SCHEDULER_TIMEZONE') or 'UTC'
    if not tz_str or not str(tz_str).strip():
        tz_str = 'UTC'
    tz_str = str(tz_str).strip()
    try:
        from zoneinfo import ZoneInfo
        return ZoneInfo(tz_str)
    except Exception:
        return timezone.utc


def get_utc_now() -> datetime:
    """Get current UTC datetime. Falls back to timezone.utc when ZoneInfo fails."""
    try:
        from zoneinfo import ZoneInfo
        return datetime.now(ZoneInfo('UTC'))
    except Exception:
        return datetime.now(timezone.utc)
