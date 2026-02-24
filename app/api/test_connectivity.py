#!/usr/bin/env python3
"""
Test connectivity API endpoint
"""

from fastapi import APIRouter, HTTPException
from typing import Dict, Any, List
from pydantic import BaseModel

from services.config_service import config_service
from commands.config_adapter import ConfigAdapter
from utils.logger import get_logger

router = APIRouter()
# Lazy-load logger to avoid initialization issues
def get_test_connectivity_logger():
    return get_logger('cmdarr.api.test_connectivity')


class ConnectivityTestResult(BaseModel):
    """Result of a connectivity test"""
    service: str
    success: bool
    message: str
    error: str = None
    status: str = "success"  # "success", "warning", "error"


class ConnectivityTestResponse(BaseModel):
    """Response for connectivity test"""
    results: List[ConnectivityTestResult]
    overall_success: bool


@router.post("/test-connectivity", response_model=ConnectivityTestResponse)
async def test_connectivity():
    """Test connectivity to all configured services"""
    try:
        results = []
        
        # Test Lidarr
        lidarr_result = await _test_lidarr()
        results.append(lidarr_result)
        
        # Test Last.fm
        lastfm_result = await _test_lastfm()
        results.append(lastfm_result)
        
        # Test Plex
        plex_result = await _test_plex()
        results.append(plex_result)
        
        # Test Jellyfin
        jellyfin_result = await _test_jellyfin()
        results.append(jellyfin_result)
        
        # Test ListenBrainz
        listenbrainz_result = await _test_listenbrainz()
        results.append(listenbrainz_result)
        
        # Test MusicBrainz
        musicbrainz_result = await _test_musicbrainz()
        results.append(musicbrainz_result)
        
        # Test Spotify
        spotify_result = await _test_spotify()
        results.append(spotify_result)
        
        # Calculate overall success
        overall_success = all(result.success for result in results)
        
        # Sort results alphabetically by service name
        results.sort(key=lambda x: x.service)
        
        return ConnectivityTestResponse(
            results=results,
            overall_success=overall_success
        )
        
    except Exception as e:
        get_test_connectivity_logger().error(f"Connectivity test failed: {e}")
        raise HTTPException(status_code=500, detail="Connectivity test failed")


async def _test_lidarr() -> ConnectivityTestResult:
    """Test Lidarr connectivity"""
    try:
        # Check if Lidarr is configured
        lidarr_url = config_service.get('LIDARR_URL')
        lidarr_api_key = config_service.get('LIDARR_API_KEY')
        
        if not lidarr_url or not lidarr_api_key:
            return ConnectivityTestResult(
                service="Lidarr",
                success=False,
                message="Not configured",
                error="Lidarr URL or API key not set",
                status="error"
            )
        
        # Test connection
        from clients.client_lidarr import LidarrClient
        config = ConfigAdapter()
        
        async with LidarrClient(config) as client:
            # Use the existing test_connection method
            success = await client.test_connection()
        
        if success:
            return ConnectivityTestResult(
                service="Lidarr",
                success=True,
                message="Connected successfully",
                status="success"
            )
        else:
            return ConnectivityTestResult(
                service="Lidarr",
                success=False,
                message="Connection failed",
                error="Unable to connect to Lidarr",
                status="error"
            )
            
    except Exception as e:
        get_test_connectivity_logger().error(f"Lidarr test failed: {e}")
        return ConnectivityTestResult(
            service="Lidarr",
            success=False,
            message="Test failed",
            error="Connection test failed",
            status="error"
        )


async def _test_lastfm() -> ConnectivityTestResult:
    """Test Last.fm connectivity"""
    try:
        # Check if Last.fm is configured
        lastfm_api_key = config_service.get('LASTFM_API_KEY')
        
        if not lastfm_api_key:
            return ConnectivityTestResult(
                service="Last.fm",
                success=False,
                message="Not configured",
                error="Last.fm API key not set",
                status="error"
            )
        
        # Test connection
        from clients.client_lastfm import LastFMClient
        config = ConfigAdapter()
        
        async with LastFMClient(config) as client:
            # Use the existing test_connection method
            success = await client.test_connection()
        
        if success:
            return ConnectivityTestResult(
                service="Last.fm",
                success=True,
                message="Connected successfully",
                status="success"
            )
        else:
            return ConnectivityTestResult(
                service="Last.fm",
                success=False,
                message="Connection failed",
                error="Unable to connect to Last.fm",
                status="error"
            )
            
    except Exception as e:
        get_test_connectivity_logger().error(f"Last.fm test failed: {e}")
        return ConnectivityTestResult(
            service="Last.fm",
            success=False,
            message="Test failed",
            error="Connection test failed",
            status="error"
        )


async def _test_plex() -> ConnectivityTestResult:
    """Test Plex connectivity"""
    try:
        # Check if Plex client is enabled
        plex_enabled = config_service.get('PLEX_CLIENT_ENABLED', False)
        if not plex_enabled:
            return ConnectivityTestResult(
                service="Plex",
                success=False,
                message="Disabled",
                error="Plex client is disabled",
                status="warning"
            )
        
        # Check if Plex is configured
        plex_url = config_service.get('PLEX_URL')
        plex_token = config_service.get('PLEX_TOKEN')
        
        if not plex_url or not plex_token:
            return ConnectivityTestResult(
                service="Plex",
                success=False,
                message="Not configured",
                error="Plex URL or token not set",
                status="error"
            )
        
        # Test connection
        from clients.client_plex import PlexClient
        config = ConfigAdapter()
        
        async with PlexClient(config) as client:
            # Use the existing test_connection method
            success = await client.test_connection()
        
        if success:
            return ConnectivityTestResult(
                service="Plex",
                success=True,
                message="Connected successfully",
                status="success"
            )
        else:
            return ConnectivityTestResult(
                service="Plex",
                success=False,
                message="Connection failed",
                error="Unable to connect to Plex",
                status="error"
            )
            
    except Exception as e:
        get_test_connectivity_logger().error(f"Plex test failed: {e}")
        return ConnectivityTestResult(
            service="Plex",
            success=False,
            message="Test failed",
            error="Connection test failed",
            status="error"
        )


async def _test_jellyfin() -> ConnectivityTestResult:
    """Test Jellyfin connectivity"""
    try:
        # Check if Jellyfin client is enabled
        jellyfin_enabled = config_service.get('JELLYFIN_CLIENT_ENABLED', False)
        if not jellyfin_enabled:
            return ConnectivityTestResult(
                service="Jellyfin",
                success=False,
                message="Disabled",
                error="Jellyfin client is disabled",
                status="warning"
            )
        
        # Check if Jellyfin is configured
        jellyfin_url = config_service.get('JELLYFIN_URL')
        jellyfin_token = config_service.get('JELLYFIN_TOKEN')
        
        if not jellyfin_url or not jellyfin_token:
            return ConnectivityTestResult(
                service="Jellyfin",
                success=False,
                message="Not configured",
                error="Jellyfin URL or token not set",
                status="error"
            )
        
        # Test connection
        from clients.client_jellyfin import JellyfinClient
        config = ConfigAdapter()
        
        # JellyfinClient has sync test_connection method
        client = JellyfinClient(config)
        success = client.test_connection()
        
        if success:
            return ConnectivityTestResult(
                service="Jellyfin",
                success=True,
                message="Connected successfully",
                status="success"
            )
        else:
            return ConnectivityTestResult(
                service="Jellyfin",
                success=False,
                message="Connection failed",
                error="Unable to connect to Jellyfin",
                status="error"
            )
            
    except Exception as e:
        get_test_connectivity_logger().error(f"Jellyfin test failed: {e}")
        return ConnectivityTestResult(
            service="Jellyfin",
            success=False,
            message="Test failed",
            error="Connection test failed",
            status="error"
        )


async def _test_listenbrainz() -> ConnectivityTestResult:
    """Test ListenBrainz connectivity"""
    try:
        # Check if ListenBrainz is configured
        listenbrainz_token = config_service.get('LISTENBRAINZ_TOKEN')
        
        if not listenbrainz_token:
            return ConnectivityTestResult(
                service="ListenBrainz",
                success=False,
                message="Not configured",
                error="ListenBrainz token not set",
                status="error"
            )
        
        # Test connection
        from clients.client_listenbrainz import ListenBrainzClient
        config = ConfigAdapter()
        
        async with ListenBrainzClient(config) as client:
            # Use the existing test_connection method
            success = await client.test_connection()
        
        if success:
            return ConnectivityTestResult(
                service="ListenBrainz",
                success=True,
                message="Connected successfully",
                status="success"
            )
        else:
            return ConnectivityTestResult(
                service="ListenBrainz",
                success=False,
                message="Connection failed",
                error="Unable to connect to ListenBrainz",
                status="error"
            )
            
    except Exception as e:
        get_test_connectivity_logger().error(f"ListenBrainz test failed: {e}")
        return ConnectivityTestResult(
            service="ListenBrainz",
            success=False,
            message="Test failed",
            error="Connection test failed",
            status="error"
        )


async def _test_musicbrainz() -> ConnectivityTestResult:
    """Test MusicBrainz connectivity"""
    try:
        # MusicBrainz doesn't require authentication for basic queries
        # We can test with a simple API call
        
        # Test connection
        from clients.client_musicbrainz import MusicBrainzClient
        config = ConfigAdapter()
        
        async with MusicBrainzClient(config) as client:
            # Use the existing test_connection method
            success = await client.test_connection()
        
        if success:
            return ConnectivityTestResult(
                service="MusicBrainz",
                success=True,
                message="Connected successfully",
                status="success"
            )
        else:
            return ConnectivityTestResult(
                service="MusicBrainz",
                success=False,
                message="Connection failed",
                error="Unable to connect to MusicBrainz",
                status="error"
            )
            
    except Exception as e:
        get_test_connectivity_logger().error(f"MusicBrainz test failed: {e}")
        return ConnectivityTestResult(
            service="MusicBrainz",
            success=False,
            message="Test failed",
            error="Connection test failed",
            status="error"
        )


async def _test_spotify() -> ConnectivityTestResult:
    """Test Spotify connectivity"""
    try:
        # Check if Spotify is configured
        spotify_client_id = config_service.get('SPOTIFY_CLIENT_ID')
        spotify_client_secret = config_service.get('SPOTIFY_CLIENT_SECRET')
        
        if not spotify_client_id or not spotify_client_secret:
            return ConnectivityTestResult(
                service="Spotify",
                success=False,
                message="Not configured",
                error="Spotify Client ID or Client Secret not set",
                status="error"
            )
        
        # Test connection
        from clients.client_spotify import SpotifyClient
        config = ConfigAdapter()
        
        async with SpotifyClient(config) as client:
            # Use the existing test_connection method
            success = await client.test_connection()
        
        if success:
            return ConnectivityTestResult(
                service="Spotify",
                success=True,
                message="Connected successfully",
                status="success"
            )
        else:
            return ConnectivityTestResult(
                service="Spotify",
                success=False,
                message="Connection failed",
                error="Unable to authenticate with Spotify API",
                status="error"
            )
            
    except Exception as e:
        get_test_connectivity_logger().error(f"Spotify test failed: {e}")
        return ConnectivityTestResult(
            service="Spotify",
            success=False,
            message="Test failed",
            error="Connection test failed",
            status="error"
        )
