"""Singleton command families: at most one active (non-deleted) command per group.

``CommandConfig.singleton_group`` marks rows that belong to a singleton family.
Create APIs and the Add New type picker consult this module so only one live
instance can exist (Daylist, Local Discovery, Lidarr Update All, Lidarr Wanted Search).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from fastapi import HTTPException
from sqlalchemy.orm import Session

from database.config_models import CommandConfig

SINGLETON_MESSAGE = "Only one instance of this command is allowed."


@dataclass(frozen=True)
class SingletonFamily:
    """One createable command type that may only have a single active instance."""

    group: str
    create_type: str
    fixed_display_name: str | None = None


SINGLETON_FAMILIES: dict[str, SingletonFamily] = {
    "lidarr_update_all": SingletonFamily(
        group="lidarr_update_all",
        create_type="lidarr_update_all",
        fixed_display_name="Lidarr Maintenance - Artist Refresh",
    ),
    "lidarr_wanted_search": SingletonFamily(
        group="lidarr_wanted_search",
        create_type="lidarr_wanted_search",
        fixed_display_name="Lidarr Maintenance - Missing Search",
    ),
    "daylist": SingletonFamily(
        group="daylist",
        create_type="daylist",
    ),
    "local_discovery": SingletonFamily(
        group="local_discovery",
        create_type="local_discovery",
    ),
}


def get_family(create_type: str) -> SingletonFamily | None:
    return SINGLETON_FAMILIES.get(create_type)


def find_active_singleton(db: Session, family: SingletonFamily) -> CommandConfig | None:
    """Return an active command for this family, if any."""
    return (
        db.query(CommandConfig)
        .filter(
            CommandConfig.singleton_group == family.group,
            CommandConfig.deleted_at.is_(None),
        )
        .first()
    )


def singleton_occupied(db: Session, create_type: str) -> bool:
    family = get_family(create_type)
    if family is None:
        return False
    return find_active_singleton(db, family) is not None


def require_singleton_available(db: Session, create_type: str) -> SingletonFamily | None:
    """Raise 409 if this create type is a singleton and already occupied.

    Returns the family when the type is a singleton (for display-name / group assignment),
    or None when the type is not singleton-constrained.
    """
    family = get_family(create_type)
    if family is None:
        return None
    if find_active_singleton(db, family) is not None:
        raise HTTPException(status_code=409, detail=SINGLETON_MESSAGE)
    return family


def availability_for_create(db: Session) -> dict[str, dict[str, Any]]:
    """Map create_type → {available, reason} for the Add New type picker."""
    out: dict[str, dict[str, Any]] = {}
    for create_type, family in SINGLETON_FAMILIES.items():
        occupied = find_active_singleton(db, family) is not None
        out[create_type] = {
            "available": not occupied,
            "reason": SINGLETON_MESSAGE if occupied else None,
        }
    return out
