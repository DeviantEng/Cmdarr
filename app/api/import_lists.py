"""
Import Lists API endpoints
"""

import os
import json
from datetime import datetime
from typing import Dict, Any, Optional
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from database.database import get_database_manager

router = APIRouter()


def _get_file_metrics(file_path: str) -> Dict[str, Any]:
    """Get comprehensive metrics for an import list file"""
    if not os.path.exists(file_path):
        return {
            'exists': False,
            'entry_count': 0,
            'file_size': 0,
            'file_mtime': 0,
            'age_hours': None,
            'age_human': 'Not available',
            'status': 'missing'
        }
    
    file_size = os.path.getsize(file_path)
    file_mtime = os.path.getmtime(file_path)
    
    # Calculate file age
    now = datetime.now().timestamp()
    age_seconds = now - file_mtime
    age_hours = age_seconds / 3600
    
    # Human readable age
    if age_seconds < 3600:
        age_human = f"{int(age_seconds // 60)} minutes ago"
    elif age_seconds < 86400:
        age_human = f"{int(age_hours)} hours ago"
    else:
        age_days = age_seconds / 86400
        age_human = f"{int(age_days)} days ago"
    
    # Count entries in JSON file
    entry_count = 0
    sample_entries = []
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            entry_count = len(data)
            # Get first few entries as samples for debugging
            sample_entries = data[:3] if len(data) > 0 else []
    except (json.JSONDecodeError, Exception):
        pass
    
    # Determine status based on age and content
    if entry_count == 0:
        # For playlist sync discovery, empty is normal (no new artists found)
        # For Last.fm, empty might indicate an issue
        if 'listenbrainz' in file_path.lower():
            status = 'no_new_artists'  # Normal state for playlist sync discovery
        else:
            status = 'empty'  # Potentially problematic for Last.fm
    elif age_hours < 25:  # Within expected update cycle
        status = 'fresh'
    elif age_hours < 72:  # Somewhat stale
        status = 'stale'
    else:
        status = 'very_stale'
    
    return {
        'exists': True,
        'entry_count': entry_count,
        'file_size': file_size,
        'file_mtime': file_mtime,
        'age_hours': age_hours,
        'age_human': age_human,
        'status': status,
        'sample_entries': sample_entries
    }


@router.get("/metrics")
async def get_import_list_metrics():
    """Get metrics for all import list files"""
    try:
        # Import services inside function to avoid startup issues
        from services.config_service import config_service
        from utils.logger import get_logger
        logger = get_logger('cmdarr.api.import_lists')
        
        # Get file paths from config
        lastfm_file = config_service.get('OUTPUT_FILE')
        unified_file = "data/import_lists/discovery_playlistsync.json"
        
        # Get metrics for both discovery files
        lastfm_metrics = _get_file_metrics(lastfm_file)
        unified_metrics = _get_file_metrics(unified_file)
        
        return {
            'lastfm': lastfm_metrics,
            'unified': unified_metrics,
            'timestamp': datetime.utcnow().isoformat() + 'Z'
        }
        
    except Exception as e:
        logger.error(f"Failed to get import list metrics: {e}")
        raise HTTPException(status_code=500, detail="Failed to get import list metrics")


@router.get("/discovery_lastfm")
async def serve_discovery_lastfm():
    """Serve the Last.fm discovery JSON file"""
    try:
        # Import services inside function to avoid startup issues
        from services.config_service import config_service
        from utils.logger import get_logger
        logger = get_logger('cmdarr.api.import_lists')
        
        file_path = config_service.get('OUTPUT_FILE')
        
        if not os.path.exists(file_path):
            logger.warning(f"Last.fm discovery file not found: {file_path}")
            raise HTTPException(status_code=404, detail="Last.fm discovery file not found")
        
        # Read and serve the file
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        logger.debug(f"Served discovery_lastfm with {len(data)} entries")
        return data
        
    except json.JSONDecodeError as e:
        logger.error(f"Invalid JSON in Last.fm discovery file: {e}")
        raise HTTPException(status_code=500, detail="Invalid JSON file")
    except Exception as e:
        logger.error(f"Error serving Last.fm discovery: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/discovery_playlistsync")
async def serve_discovery_playlistsync():
    """Serve the playlist sync discovery import list"""
    try:
        from utils.logger import get_logger
        logger = get_logger('cmdarr.api.import_lists')
        
        file_path = "data/import_lists/discovery_playlistsync.json"
        
        if not os.path.exists(file_path):
            logger.warning(f"Playlist sync discovery file not found: {file_path}")
            return []
        
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        logger.debug(f"Served discovery_playlistsync with {len(data)} entries")
        return data
        
    except json.JSONDecodeError as e:
        logger.error(f"Invalid JSON in playlist sync discovery file: {e}")
        raise HTTPException(status_code=500, detail="Invalid JSON file")
    except Exception as e:
        logger.error(f"Error serving playlist sync discovery: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

