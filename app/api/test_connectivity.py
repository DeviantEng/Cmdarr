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
logger = get_logger('cmdarr.api.test_connectivity')


class ConnectivityTestResult(BaseModel):
    """Result of a connectivity test"""
    service: str
    success: bool
    message: str
    error: str = None


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
        
        # Calculate overall success
        overall_success = all(result.success for result in results)
        
        return ConnectivityTestResponse(
            results=results,
            overall_success=overall_success
        )
        
    except Exception as e:
        logger.error(f"Connectivity test failed: {e}")
        raise HTTPException(status_code=500, detail=f"Connectivity test failed: {str(e)}")


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
                error="Lidarr URL or API key not set"
            )
        
        # Test connection
        from clients.client_lidarr import LidarrClient
        config = ConfigAdapter()
        client = LidarrClient(config)
        
        # Use the existing test_connection method
        success = await client.test_connection()
        
        if success:
            return ConnectivityTestResult(
                service="Lidarr",
                success=True,
                message="Connected successfully"
            )
        else:
            return ConnectivityTestResult(
                service="Lidarr",
                success=False,
                message="Connection failed",
                error="Unable to connect to Lidarr"
            )
            
    except Exception as e:
        return ConnectivityTestResult(
            service="Lidarr",
            success=False,
            message="Test failed",
            error=str(e)
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
                error="Last.fm API key not set"
            )
        
        # Test connection
        from clients.client_lastfm import LastFMClient
        config = ConfigAdapter()
        client = LastFMClient(config)
        
        # Use the existing test_connection method
        success = await client.test_connection()
        
        if success:
            return ConnectivityTestResult(
                service="Last.fm",
                success=True,
                message="Connected successfully"
            )
        else:
            return ConnectivityTestResult(
                service="Last.fm",
                success=False,
                message="Connection failed",
                error="Unable to connect to Last.fm"
            )
            
    except Exception as e:
        return ConnectivityTestResult(
            service="Last.fm",
            success=False,
            message="Test failed",
            error=str(e)
        )


async def _test_plex() -> ConnectivityTestResult:
    """Test Plex connectivity"""
    try:
        # Check if Plex is configured
        plex_url = config_service.get('PLEX_URL')
        plex_token = config_service.get('PLEX_TOKEN')
        
        if not plex_url or not plex_token:
            return ConnectivityTestResult(
                service="Plex",
                success=False,
                message="Not configured",
                error="Plex URL or token not set"
            )
        
        # Test connection
        from clients.client_plex import PlexClient
        config = ConfigAdapter()
        client = PlexClient(config)
        
        # Use the existing test_connection method
        success = await client.test_connection()
        
        if success:
            return ConnectivityTestResult(
                service="Plex",
                success=True,
                message="Connected successfully"
            )
        else:
            return ConnectivityTestResult(
                service="Plex",
                success=False,
                message="Connection failed",
                error="Unable to connect to Plex"
            )
            
    except Exception as e:
        return ConnectivityTestResult(
            service="Plex",
            success=False,
            message="Test failed",
            error=str(e)
        )


async def _test_jellyfin() -> ConnectivityTestResult:
    """Test Jellyfin connectivity"""
    try:
        # Check if Jellyfin is configured
        jellyfin_url = config_service.get('JELLYFIN_URL')
        jellyfin_token = config_service.get('JELLYFIN_TOKEN')
        
        if not jellyfin_url or not jellyfin_token:
            return ConnectivityTestResult(
                service="Jellyfin",
                success=False,
                message="Not configured",
                error="Jellyfin URL or token not set"
            )
        
        # Test connection
        from clients.client_jellyfin import JellyfinClient
        config = ConfigAdapter()
        client = JellyfinClient(config)
        
        # Use the existing test_connection method (JellyfinClient has sync test_connection)
        success = client.test_connection()
        
        if success:
            return ConnectivityTestResult(
                service="Jellyfin",
                success=True,
                message="Connected successfully"
            )
        else:
            return ConnectivityTestResult(
                service="Jellyfin",
                success=False,
                message="Connection failed",
                error="Unable to connect to Jellyfin"
            )
            
    except Exception as e:
        return ConnectivityTestResult(
            service="Jellyfin",
            success=False,
            message="Test failed",
            error=str(e)
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
                error="ListenBrainz token not set"
            )
        
        # Test connection
        from clients.client_listenbrainz import ListenBrainzClient
        config = ConfigAdapter()
        client = ListenBrainzClient(config)
        
        # Use the existing test_connection method
        success = await client.test_connection()
        
        if success:
            return ConnectivityTestResult(
                service="ListenBrainz",
                success=True,
                message="Connected successfully"
            )
        else:
            return ConnectivityTestResult(
                service="ListenBrainz",
                success=False,
                message="Connection failed",
                error="Unable to connect to ListenBrainz"
            )
            
    except Exception as e:
        return ConnectivityTestResult(
            service="ListenBrainz",
            success=False,
            message="Test failed",
            error=str(e)
        )


async def _test_musicbrainz() -> ConnectivityTestResult:
    """Test MusicBrainz connectivity"""
    try:
        # MusicBrainz doesn't require authentication for basic queries
        # We can test with a simple API call
        
        # Test connection
        from clients.client_musicbrainz import MusicBrainzClient
        config = ConfigAdapter()
        client = MusicBrainzClient(config)
        
        # Use the existing test_connection method
        success = await client.test_connection()
        
        if success:
            return ConnectivityTestResult(
                service="MusicBrainz",
                success=True,
                message="Connected successfully"
            )
        else:
            return ConnectivityTestResult(
                service="MusicBrainz",
                success=False,
                message="Connection failed",
                error="Unable to connect to MusicBrainz"
            )
            
    except Exception as e:
        return ConnectivityTestResult(
            service="MusicBrainz",
            success=False,
            message="Test failed",
            error=str(e)
        )
