"""
Shared User-Agent for outbound HTTP APIs (MusicBrainz, ListenBrainz, …).

Override via config key CMDARR_USER_AGENT in the database / Config UI (not via OS environment —
see services.config_service._CONFIG_KEYS_SKIP_ENV). Empty / unset uses MusicBrainz-style default:
AppName/version (project URL).
"""

from __future__ import annotations

from typing import Any

from __version__ import __version__

DEFAULT_CMDARR_USER_AGENT = f"Cmdarr/{__version__} (https://github.com/DeviantEng/Cmdarr)"


def _raw_cmdarr_user_agent_from_config(config: Any) -> str:
    if config is None:
        return ""
    if isinstance(config, dict):
        return str(config.get("CMDARR_USER_AGENT") or "").strip()
    v = getattr(config, "CMDARR_USER_AGENT", None)
    if v is not None and str(v).strip():
        return str(v).strip()
    getter = getattr(config, "get", None)
    if callable(getter):
        got = getter("CMDARR_USER_AGENT", "")
        if got is not None and str(got).strip():
            return str(got).strip()
    return ""


def resolve_cmdarr_user_agent(config: Any) -> str:
    """Return CMDARR_USER_AGENT from config when set; otherwise DEFAULT_CMDARR_USER_AGENT."""
    raw = _raw_cmdarr_user_agent_from_config(config)
    return raw if raw else DEFAULT_CMDARR_USER_AGENT
