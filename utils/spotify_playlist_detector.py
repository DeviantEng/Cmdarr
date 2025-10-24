#!/usr/bin/env python3
"""
Spotify Playlist Detector Utility
Detects and classifies Spotify playlist types based on ID patterns
"""

from typing import Dict, Optional


class SpotifyPlaylistDetector:
    """Detect and classify Spotify playlist types"""
    
    # Known playlists with specific metadata
    KNOWN_PLAYLISTS = {
        '37i9dQZF1EP6YuccBxUcC1': {
            'name': 'Daylist',
            'description': 'Your day in a playlist',
            'update_frequency': 'Multiple times daily',
            'recommended_sync_hours': 4,  # Updated to 4 hours
            'requires_listening_history': True
        },
        '37i9dQZEVXcJ8o4aRB1zXJ': {
            'name': 'Discover Weekly',
            'description': 'Your weekly mixtape of fresh music',
            'update_frequency': 'Weekly (Mondays)',
            'recommended_sync_hours': 168,
            'requires_listening_history': True
        },
        '37i9dQZEVXbng2vJ1z5K7r': {
            'name': 'Release Radar',
            'description': 'New releases from artists you follow',
            'update_frequency': 'Weekly (Fridays)',
            'recommended_sync_hours': 168,
            'requires_listening_history': True
        },
        # Add more as needed
    }
    
    @staticmethod
    def is_user_generated_playlist(playlist_id: str) -> bool:
        """
        Check if playlist ID matches Spotify-generated pattern.
        All personalized playlists start with 37i9dQZF1E
        """
        return playlist_id.startswith('37i9dQZF1E')
    
    @staticmethod
    def get_playlist_info(playlist_id: str) -> Dict[str, any]:
        """
        Get known info about playlist or return generic info.
        Used for UI hints and recommended settings.
        """
        if playlist_id in SpotifyPlaylistDetector.KNOWN_PLAYLISTS:
            return {
                'type': 'spotify_generated',
                **SpotifyPlaylistDetector.KNOWN_PLAYLISTS[playlist_id]
            }
        
        if SpotifyPlaylistDetector.is_user_generated_playlist(playlist_id):
            return {
                'type': 'spotify_generated',
                'name': 'Spotify Personalized Playlist',
                'description': 'Algorithm-generated based on listening history',
                'update_frequency': 'Varies',
                'recommended_sync_hours': 24,
                'requires_listening_history': True
            }
        
        return {
            'type': 'public',
            'name': 'Public Playlist',
            'recommended_sync_hours': 24,
            'requires_listening_history': False
        }
    
    @staticmethod
    def requires_user_auth(playlist_id: str) -> bool:
        """
        Determine if playlist requires user authentication.
        Based on pattern - fast and reliable.
        """
        return SpotifyPlaylistDetector.is_user_generated_playlist(playlist_id)
