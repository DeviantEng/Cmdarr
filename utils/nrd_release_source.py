"""Helpers for New Releases Discovery source routing."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from clients.client_base import BaseAPIClient

VALID_NRD_SOURCES = frozenset({"deezer", "spotify_scraper", "spotify"})


def normalize_nrd_source(src: str | None) -> str:
    s = (src or "deezer").strip().lower()
    if s in VALID_NRD_SOURCES:
        return s
    return "deezer"


def nrd_uses_spotify(source: str) -> bool:
    return normalize_nrd_source(source) in ("spotify", "spotify_scraper")


def nrd_mb_streaming_provider(source: str) -> str:
    return "spotify" if nrd_uses_spotify(source) else "deezer"


def nrd_lidarr_artist_id_key(source: str) -> str:
    return "spotifyArtistId" if nrd_uses_spotify(source) else "deezerArtistId"


def nrd_release_client(source: str, config) -> BaseAPIClient:
    from clients.client_deezer import DeezerClient
    from clients.client_spotify import SpotifyClient

    src = normalize_nrd_source(source)
    if src == "deezer":
        return DeezerClient(config)
    if src == "spotify_scraper":
        return SpotifyClient(config, discography_source="scraper")
    return SpotifyClient(config, discography_source="api")
