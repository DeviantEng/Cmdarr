"""Artist event source availability metadata (for API/UI; not enforcement)."""

from __future__ import annotations

from typing import Any

# Ticketmaster Discovery is the only source with open self-serve API registration today.
# Bandsintown and Songkick remain in Cmdarr for deployments with existing partner keys.
PROVIDER_CATALOG: dict[str, dict[str, Any]] = {
    "ticketmaster": {
        "label": "Ticketmaster",
        "registration_open": True,
        "status": "available",
        "status_message": (
            "Ticketmaster Discovery API: free developer key (Consumer Key) at "
            "developer.ticketmaster.com. Cmdarr's primary supported source."
        ),
        "docs_url": "https://developer.ticketmaster.com/products-and-docs/apis/getting-started/",
    },
    "bandsintown": {
        "label": "Bandsintown",
        "registration_open": False,
        "status": "partner_only",
        "status_message": (
            "Bandsintown requires a partner-issued app_id and written approval; not available "
            "for new self-serve integrations. Legacy keys may still work. See "
            "docs/artist-events-providers.md."
        ),
        "docs_url": "https://help.artists.bandsintown.com/en/articles/7053475-what-is-the-bandsintown-api",
    },
    "songkick": {
        "label": "Songkick",
        "registration_open": False,
        "status": "partner_only",
        "status_message": (
            "Songkick is not issuing new API keys; commercial use requires a paid partnership. "
            "Legacy keys may still work. See docs/artist-events-providers.md."
        ),
        "docs_url": "https://www.songkick.com/developer",
    },
}


def provider_status_payload(*, enabled: bool, configured: bool, provider_id: str) -> dict[str, Any]:
    meta = PROVIDER_CATALOG[provider_id]
    return {
        "enabled": enabled,
        "configured": configured,
        "registration_open": meta["registration_open"],
        "status": meta["status"],
        "status_message": meta["status_message"],
        "docs_url": meta["docs_url"],
    }
