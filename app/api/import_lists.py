"""
Import Lists API endpoints (playlist sync discovery only).
"""

import json
import os
from datetime import datetime
from typing import Any

from fastapi import APIRouter, HTTPException

router = APIRouter()

_PLAYLISTSYNC_FILE = "data/import_lists/discovery_playlistsync.json"


def _get_file_metrics(file_path: str) -> dict[str, Any]:
    """Get comprehensive metrics for an import list file"""
    if not os.path.exists(file_path):
        return {
            "exists": False,
            "entry_count": 0,
            "file_size": 0,
            "file_mtime": 0,
            "age_hours": None,
            "age_human": "Not available",
            "status": "missing",
        }

    file_size = os.path.getsize(file_path)
    file_mtime = os.path.getmtime(file_path)

    now = datetime.now().timestamp()
    age_seconds = now - file_mtime
    age_hours = age_seconds / 3600

    if age_seconds < 3600:
        age_human = f"{int(age_seconds // 60)} minutes ago"
    elif age_seconds < 86400:
        age_human = f"{int(age_hours)} hours ago"
    else:
        age_days = age_seconds / 86400
        age_human = f"{int(age_days)} days ago"

    entry_count = 0
    sample_entries = []
    try:
        with open(file_path, encoding="utf-8") as f:
            data = json.load(f)
            entry_count = len(data)
            sample_entries = data[:3] if len(data) > 0 else []
    except json.JSONDecodeError, Exception:
        pass

    # Empty is normal for playlist sync discovery (no new artists found)
    if entry_count == 0:
        status = "no_new_artists"
    elif age_hours < 25:
        status = "fresh"
    elif age_hours < 72:
        status = "stale"
    else:
        status = "very_stale"

    return {
        "exists": True,
        "entry_count": entry_count,
        "file_size": file_size,
        "file_mtime": file_mtime,
        "age_hours": age_hours,
        "age_human": age_human,
        "status": status,
        "sample_entries": sample_entries,
    }


@router.get("/metrics")
async def get_import_list_metrics():
    """Get metrics for playlist sync discovery import list."""
    try:
        from utils.logger import get_logger

        logger = get_logger("cmdarr.api.import_lists")

        unified_metrics = _get_file_metrics(_PLAYLISTSYNC_FILE)

        return {
            "unified": unified_metrics,
            "timestamp": datetime.utcnow().isoformat() + "Z",
        }

    except Exception as e:
        logger.error(f"Failed to get import list metrics: {e}")
        raise HTTPException(status_code=500, detail="Failed to get import list metrics")


@router.post("/discovery_playlistsync/reset")
async def reset_discovery_playlistsync():
    """Clear Playlist Sync import list (overwrite with empty array)."""
    try:
        from utils.logger import get_logger

        logger = get_logger("cmdarr.api.import_lists")

        file_path = _PLAYLISTSYNC_FILE
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump([], f)

        logger.info(f"Reset Playlist Sync import list: {file_path}")
        return {"success": True, "entry_count": 0}
    except Exception as e:
        logger.error(f"Failed to reset Playlist Sync import list: {e}")
        raise HTTPException(
            status_code=500, detail="Failed to reset Playlist Sync import list"
        ) from None


@router.get("/discovery_playlistsync")
async def serve_discovery_playlistsync():
    """Serve the playlist sync discovery import list"""
    try:
        from utils.logger import get_logger

        logger = get_logger("cmdarr.api.import_lists")

        file_path = _PLAYLISTSYNC_FILE

        if not os.path.exists(file_path):
            logger.warning(f"Playlist sync discovery file not found: {file_path}")
            return []

        with open(file_path, encoding="utf-8") as f:
            data = json.load(f)

        logger.debug(f"Served discovery_playlistsync with {len(data)} entries")
        return data

    except json.JSONDecodeError as e:
        logger.error(f"Invalid JSON in playlist sync discovery file: {e}")
        raise HTTPException(status_code=500, detail="Invalid JSON file")
    except Exception as e:
        logger.error(f"Error serving playlist sync discovery: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")
