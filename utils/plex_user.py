#!/usr/bin/env python3
"""
Reusable Plex user utilities for account resolution and token lookup.
Used by playlist sync, daylist, local discovery, and other commands.
"""

from typing import Any


def get_accounts(config: Any) -> list[dict[str, Any]]:
    """Get Plex Home users (and token owner if not in home users).
    Returns list of {id, name, admin} for dropdown selection."""
    from clients.client_plex import PlexClient

    plex = PlexClient(config)
    return plex.get_accounts()


def get_token_for_user(config: Any, plex_tv_user_id: str) -> str | None:
    """Resolve Plex.tv user ID to token for playlist operations.
    Admin (server owner) uses config token; others use shared_servers accessToken."""
    from clients.client_plex import PlexClient

    plex = PlexClient(config)
    return plex.get_token_for_user(plex_tv_user_id)


def get_account_name(accounts: list[dict[str, Any]], account_id: str) -> str:
    """Get display name for an account ID from accounts list."""
    for acc in accounts:
        if str(acc.get("id", "")) == str(account_id):
            return acc.get("name") or f"Account {account_id}"
    return str(account_id)
