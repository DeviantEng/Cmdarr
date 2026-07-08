"""MusicBrainz release validation helpers for New Release Discovery."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Any

from sqlalchemy.orm import Session

from database.config_models import DismissedArtistAlbum, NewReleaseIgnoredArtist, NewReleasePending

if TYPE_CHECKING:
    from clients.client_musicbrainz import MusicBrainzClient


def validation_cutoff(interval_days: int, now: datetime | None = None) -> datetime:
    """Rows with last_mb_recheck_at before this (or NULL) are due for recheck."""
    ref = now or datetime.now(UTC)
    return ref - timedelta(days=max(1, interval_days))


def is_due_for_recheck(row: NewReleasePending, cutoff: datetime) -> bool:
    if not row.artist_mbid or not row.album_title:
        return False
    if row.last_mb_recheck_at is None:
        return True
    checked = row.last_mb_recheck_at
    if checked.tzinfo is None:
        checked = checked.replace(tzinfo=UTC)
    return checked < cutoff


def select_validation_candidates(
    session: Session,
    *,
    batch_size: int,
    interval_days: int,
    now: datetime | None = None,
) -> list[NewReleasePending]:
    """Pending rows first, then dismissed; oldest/never-checked first."""
    cutoff = validation_cutoff(interval_days, now)
    ignored_mbids = {
        r.artist_mbid for r in session.query(NewReleaseIgnoredArtist.artist_mbid).all()
    }
    batch_size = max(1, min(100, batch_size))
    selected: list[NewReleasePending] = []
    remaining = batch_size

    for status in ("pending", "dismissed"):
        if remaining <= 0:
            break
        q = session.query(NewReleasePending).filter(NewReleasePending.status == status)
        if ignored_mbids:
            q = q.filter(~NewReleasePending.artist_mbid.in_(ignored_mbids))
        rows = q.order_by(
            NewReleasePending.last_mb_recheck_at.asc().nullsfirst(),
            NewReleasePending.added_at.asc(),
        ).all()
        for row in rows:
            if remaining <= 0:
                break
            if is_due_for_recheck(row, cutoff):
                selected.append(row)
                remaining -= 1

    return selected


async def check_release_in_mb(
    mb_client: MusicBrainzClient,
    artist_mbid: str,
    album_title: str,
) -> bool:
    return await mb_client.release_exists_by_artist_and_title(
        artist_mbid, album_title, cache_ttl_days=0
    )


def _release_date_key(release_date: str | None) -> str | None:
    return (release_date or "").strip() or None


def apply_mb_found(session: Session, row: NewReleasePending) -> None:
    """Remove pending row and matching dismissed entry when release exists in MB."""
    release_date = _release_date_key(row.release_date)
    dismissed = (
        session.query(DismissedArtistAlbum)
        .filter(
            DismissedArtistAlbum.artist_mbid == row.artist_mbid,
            DismissedArtistAlbum.album_title == row.album_title,
            DismissedArtistAlbum.release_date == release_date,
        )
        .first()
    )
    if dismissed:
        session.delete(dismissed)
    session.delete(row)


def apply_mb_not_found(
    session: Session, row: NewReleasePending, now: datetime | None = None
) -> None:
    row.last_mb_recheck_at = now or datetime.now(UTC)


async def run_validation_batch(
    session: Session,
    mb_client: MusicBrainzClient,
    *,
    batch_size: int = 50,
    interval_days: int = 14,
) -> dict[str, Any]:
    """Recheck due pending/dismissed rows against MusicBrainz."""
    candidates = select_validation_candidates(
        session, batch_size=batch_size, interval_days=interval_days
    )
    stats = {
        "validation_checked": 0,
        "validation_removed": 0,
        "validation_pending_checked": 0,
        "validation_dismissed_checked": 0,
    }
    for row in candidates:
        status = row.status
        try:
            found = await check_release_in_mb(mb_client, row.artist_mbid, row.album_title)
        except Exception:
            # Rate limit or transient MB error — stop batch; discovery can continue
            break
        stats["validation_checked"] += 1
        if status == "pending":
            stats["validation_pending_checked"] += 1
        elif status == "dismissed":
            stats["validation_dismissed_checked"] += 1
        if found:
            apply_mb_found(session, row)
            stats["validation_removed"] += 1
        else:
            apply_mb_not_found(session, row)
    return stats
