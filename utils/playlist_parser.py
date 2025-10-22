#!/usr/bin/env python3
"""
Playlist URL Parser
Parses playlist URLs from various sources and extracts metadata
"""

import re
from typing import Dict, Optional


def parse_playlist_url(url: str) -> Dict[str, any]:
    """
    Parse playlist URL and detect source
    
    Args:
        url: Playlist URL string
        
    Returns:
        dict with keys:
            - source: 'spotify' | 'unknown'
            - playlist_id: Extracted playlist ID
            - valid: Boolean indicating if URL is valid
            - error: Error message if invalid
    """
    if not url or not isinstance(url, str):
        return {
            'source': 'unknown',
            'playlist_id': None,
            'valid': False,
            'error': 'Invalid URL provided'
        }
    
    url = url.strip()
    
    # Spotify pattern: open.spotify.com/playlist/{id} or open.spotify.com/playlist/{id}?si=...
    spotify_pattern = r'open\.spotify\.com/playlist/([a-zA-Z0-9]+)'
    spotify_match = re.search(spotify_pattern, url)
    
    if spotify_match:
        playlist_id = spotify_match.group(1)
        return {
            'source': 'spotify',
            'playlist_id': playlist_id,
            'valid': True,
            'error': None
        }
    
    # Deezer pattern: deezer.com/*/playlist/{id}
    deezer_pattern = r'deezer\.com/.+/playlist/([0-9]+)'
    deezer_match = re.search(deezer_pattern, url)
    
    if deezer_match:
        playlist_id = deezer_match.group(1)
        return {
            'source': 'deezer',
            'playlist_id': playlist_id,
            'valid': True,
            'error': None
        }
    
    # Unknown/unsupported URL
    return {
        'source': 'unknown',
        'playlist_id': None,
        'valid': False,
        'error': 'Unsupported playlist URL. Currently only Spotify and Deezer playlists are supported.'
    }


def get_supported_sources() -> list:
    """
    Get list of currently supported playlist sources
    
    Returns:
        List of supported source identifiers
    """
    return ['spotify', 'deezer']


def get_example_url(source: str) -> Optional[str]:
    """
    Get example URL for a given source
    
    Args:
        source: Source identifier (spotify, etc.)
        
    Returns:
        Example URL string or None if source unknown
    """
    examples = {
        'spotify': 'https://open.spotify.com/playlist/4NDXWHwYWjFmgVPkNy4YlF',
        'deezer': 'https://www.deezer.com/en/playlist/1479458365'
    }
    
    return examples.get(source)

