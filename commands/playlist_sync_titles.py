"""Title and sync-mode helpers for external playlist sync (Spotify, Deezer)."""

from __future__ import annotations

PREFIX_SETTING_BY_SOURCE = {
    "spotify": "PLAYLIST_SYNC_PREFIX_SPOTIFY",
    "deezer": "PLAYLIST_SYNC_PREFIX_DEEZER",
}

DEFAULT_PREFIX_BY_SOURCE = {
    "spotify": "[Spotify]",
    "deezer": "[Deezer]",
}


def is_append_sync_mode(sync_mode: str | None) -> bool:
    """True when the command should add missing tracks and leave the playlist in place.

    The create form stores ``append``. Older configs may say ``additive``.
    """
    return (sync_mode or "").strip().lower() in {"append", "additive"}


def default_prefix_for_source(source: str | None) -> str:
    key = (source or "").strip().lower()
    if key in DEFAULT_PREFIX_BY_SOURCE:
        return DEFAULT_PREFIX_BY_SOURCE[key]
    label = (source or "Unknown").strip().title() or "Unknown"
    return f"[{label}]"


def prefix_for_source(source: str | None, configured: str | None = None) -> str:
    """Return the title prefix. An empty configured value disables the prefix."""
    if configured is None:
        return default_prefix_for_source(source)
    return str(configured).strip()


def load_prefix_for_source(source: str | None) -> str:
    """Read the global prefix setting. Missing settings use the built-in default."""
    from services.config_service import config_service

    key = PREFIX_SETTING_BY_SOURCE.get((source or "").strip().lower())
    if not key:
        return default_prefix_for_source(source)
    configured = config_service.get(key, None)
    if configured is None:
        return default_prefix_for_source(source)
    return prefix_for_source(source, str(configured))


def build_playlist_sync_title(playlist_name: str | None, prefix: str | None) -> str:
    """Playlist title Cmdarr writes to Plex or Jellyfin."""
    name = (playlist_name or "").strip()
    cleaned_prefix = (prefix or "").strip()
    if cleaned_prefix and name:
        return f"{cleaned_prefix} {name}"
    return cleaned_prefix or name
