#!/usr/bin/env python3
"""Batch refresh live event data for Lidarr artists from enabled providers."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import case, or_

from clients.client_bandsintown import BandsintownClient
from clients.client_songkick import SongkickClient
from clients.client_ticketmaster import TicketmasterClient
from commands.command_base import BaseCommand
from commands.config_adapter import ConfigAdapter
from database.config_models import (
    ArtistEvent,
    ArtistEventRefresh,
    ArtistEventSource,
    LidarrArtist,
)
from database.database import get_database_manager
from services.config_service import config_service
from utils.event_ingest import persist_normalized_events
from utils.http_client import QuotaExceededError


class ArtistEventsRefreshCommand(BaseCommand):
    """Fetch upcoming events per Lidarr artist; TTL-driven batches."""

    def __init__(self, config=None):
        super().__init__(config if config else ConfigAdapter())
        self.config_adapter = ConfigAdapter()
        self.last_run_stats: dict[str, Any] = {}
        self._quota_locked: dict[str, float] = {}

    def get_description(self) -> str:
        return "Refresh artist events for Lidarr library (Bandsintown / Songkick / Ticketmaster)"

    def get_logger_name(self) -> str:
        return "cmdarr.artist_events_refresh"

    async def execute(self) -> bool:
        log = self.logger
        cfg = self.config_adapter
        cj = getattr(self, "config_json", None) or {}
        ttl_days = max(1, min(365, int(cj.get("refresh_ttl_days", 14))))
        artists_per_run = int(cj.get("artists_per_run", 20))
        artists_per_run = max(1, min(50, artists_per_run))
        refresh_all_due = bool(cj.get("refresh_all_due", False))
        force_refresh_all = bool(cj.get("force_refresh_all", False))
        if force_refresh_all:
            refresh_all_due = True
        error_retry_minutes = max(5, min(24 * 60, int(cj.get("error_retry_minutes", 60))))
        past_event_retention_days = max(0, min(365, int(cj.get("past_event_retention_days", 1))))

        bit_on = config_service.get("ARTIST_EVENTS_BANDSINTOWN_ENABLED", False)
        bit_app = (config_service.get("ARTIST_EVENTS_BANDSINTOWN_APP_ID", "") or "").strip()
        sk_on = config_service.get("ARTIST_EVENTS_SONGKICK_ENABLED", False)
        sk_key = (config_service.get("ARTIST_EVENTS_SONGKICK_API_KEY", "") or "").strip()
        tm_on = config_service.get("ARTIST_EVENTS_TICKETMASTER_ENABLED", False)
        tm_key = (config_service.get("ARTIST_EVENTS_TICKETMASTER_API_KEY", "") or "").strip()

        providers_ok = (
            (bit_on and bool(bit_app)) or (sk_on and bool(sk_key)) or (tm_on and bool(tm_key))
        )
        if not providers_ok:
            log.error("No event provider enabled with valid credentials")
            self.last_run_stats = {"error": "Configure at least one event provider in Config"}
            return False

        if not cfg.LIDARR_API_KEY or not cfg.LIDARR_URL:
            log.error("Lidarr not configured")
            self.last_run_stats = {"error": "Lidarr not configured"}
            return False

        db = get_database_manager()
        session = db.get_config_session_sync()
        now = datetime.now(UTC)
        try:
            past_events_purged = self._delete_past_events(session, now, past_event_retention_days)
            session.commit()
            if past_events_purged:
                log.info(
                    "Purged %s past event row(s) older than %s day(s) before refresh",
                    past_events_purged,
                    past_event_retention_days,
                )

            q = (
                session.query(LidarrArtist)
                .outerjoin(
                    ArtistEventRefresh,
                    LidarrArtist.artist_mbid == ArtistEventRefresh.artist_mbid,
                )
                .order_by(
                    case((ArtistEventRefresh.next_due_at.is_(None), 0), else_=1),
                    ArtistEventRefresh.next_due_at.asc(),
                )
            )
            if not force_refresh_all:
                q = q.filter(
                    or_(
                        ArtistEventRefresh.next_due_at.is_(None),
                        ArtistEventRefresh.next_due_at < now,
                    )
                )
            if not refresh_all_due:
                q = q.limit(artists_per_run)
            rows = q.all()

            if not rows:
                log.info("No Lidarr artists due for event refresh")
                self.last_run_stats = {
                    "artists_processed": 0,
                    "new_events": 0,
                    "sources_added": 0,
                }
                return True

            total_new = 0
            total_sources = 0
            processed = 0
            artists_with_errors = 0
            provider_error_counts: dict[str, int] = {
                "bandsintown": 0,
                "songkick": 0,
                "ticketmaster": 0,
            }
            self._quota_locked = {}

            for la in rows:
                merged, provider_errors = await self._fetch_for_artist(
                    cfg,
                    la.artist_name,
                    la.artist_mbid,
                    bit_on,
                    bit_app,
                    sk_on,
                    sk_key,
                    tm_on,
                    tm_key,
                )
                if merged:
                    n, s = persist_normalized_events(session, merged)
                    total_new += n
                    total_sources += s
                for p in provider_errors:
                    provider_error_counts[p] = provider_error_counts.get(p, 0) + 1
                had_error = bool(provider_errors)
                if had_error:
                    artists_with_errors += 1

                ar = (
                    session.query(ArtistEventRefresh)
                    .filter(ArtistEventRefresh.artist_mbid == la.artist_mbid)
                    .first()
                )
                if had_error:
                    # Retry sooner than the normal TTL; never stamp last_fetched_at on a failure
                    # so "never succeeded" remains observable in the UI / DB.
                    # If any provider is quota-locked, push the retry to the quota-reset
                    # horizon so we don't burn a second wave of rejections as soon as the
                    # scheduler fires again.
                    retry_due = now + timedelta(minutes=error_retry_minutes)
                    if self._quota_locked:
                        max_lock_seconds = max(self._quota_locked.values())
                        quota_retry = now + timedelta(
                            seconds=max(max_lock_seconds, error_retry_minutes * 60)
                        )
                        if quota_retry > retry_due:
                            retry_due = quota_retry
                    if not ar:
                        session.add(
                            ArtistEventRefresh(
                                artist_mbid=la.artist_mbid,
                                last_fetched_at=None,
                                next_due_at=retry_due,
                            )
                        )
                    else:
                        ar.next_due_at = retry_due
                else:
                    next_due = now + timedelta(days=ttl_days)
                    if not ar:
                        session.add(
                            ArtistEventRefresh(
                                artist_mbid=la.artist_mbid,
                                last_fetched_at=now,
                                next_due_at=next_due,
                            )
                        )
                    else:
                        ar.last_fetched_at = now
                        ar.next_due_at = next_due
                processed += 1
                session.commit()

            self.last_run_stats = {
                "artists_processed": processed,
                "new_events": total_new,
                "sources_added": total_sources,
                "refresh_all_due": refresh_all_due,
                "force_refresh_all": force_refresh_all,
                "artists_per_run_cap": artists_per_run,
                "artists_with_errors": artists_with_errors,
                "provider_errors": provider_error_counts,
                "past_events_purged": past_events_purged,
                "past_event_retention_days": past_event_retention_days,
                "quota_locked_providers": sorted(self._quota_locked.keys()),
            }
            log.info(
                "Artist events refresh: %s artists processed (force_all=%s, all_due=%s, cap=%s), "
                "%s new events, %s new sources, %s artists had provider errors (bit=%s sk=%s tm=%s)",
                processed,
                force_refresh_all,
                refresh_all_due,
                artists_per_run,
                total_new,
                total_sources,
                artists_with_errors,
                provider_error_counts["bandsintown"],
                provider_error_counts["songkick"],
                provider_error_counts["ticketmaster"],
            )
            return True
        except Exception as e:
            log.exception("Artist events refresh failed: %s", e)
            session.rollback()
            self.last_run_stats = {"error": str(e)}
            return False
        finally:
            session.close()

    def _delete_past_events(self, session, now: datetime, retention_days: int) -> int:
        """Remove canonical events whose start time is older than `retention_days` ago.

        Returns the number of canonical `concert_event` rows deleted. With
        `PRAGMA foreign_keys=ON` enabled globally (see database.database._enable_sqlite_fk)
        dependent rows in `concert_event_source` and `artist_concert_hidden_event` cascade
        automatically. The explicit source delete below is kept as a belt-and-suspenders
        safeguard so cleanup still works if FK enforcement is ever disabled.
        """
        cutoff = now - timedelta(days=max(0, retention_days))
        old_ids = [
            r[0]
            for r in session.query(ArtistEvent.id).filter(ArtistEvent.starts_at_utc < cutoff).all()
        ]
        if not old_ids:
            return 0
        session.query(ArtistEventSource).filter(
            ArtistEventSource.concert_event_id.in_(old_ids)
        ).delete(synchronize_session=False)
        session.query(ArtistEvent).filter(ArtistEvent.id.in_(old_ids)).delete(
            synchronize_session=False
        )
        return len(old_ids)

    async def _fetch_for_artist(
        self,
        cfg: ConfigAdapter,
        artist_name: str,
        artist_mbid: str,
        bit_on: bool,
        bit_app: str,
        sk_on: bool,
        sk_key: str,
        tm_on: bool,
        tm_key: str,
    ) -> tuple[list[dict[str, Any]], list[str]]:
        """Return (merged_events, errored_providers).

        A provider contributes to errored_providers when its client returns None (HTTP / parse
        failure) or raises. Clients that return an empty list (valid "no events") and disabled
        providers are treated as success and are NOT reported as errors.
        """

        async def run_bit():
            if not bit_on or not bit_app or "bandsintown" in self._quota_locked:
                return []
            async with BandsintownClient(cfg, bit_app) as c:
                return await c.fetch_upcoming_events(artist_name, artist_mbid)

        async def run_sk():
            if not sk_on or not sk_key or "songkick" in self._quota_locked:
                return []
            async with SongkickClient(cfg, sk_key) as c:
                return await c.fetch_upcoming_events(artist_name, artist_mbid)

        async def run_tm():
            if not tm_on or not tm_key or "ticketmaster" in self._quota_locked:
                return []
            async with TicketmasterClient(cfg, tm_key) as c:
                return await c.fetch_upcoming_events(artist_name, artist_mbid)

        merged: list[dict[str, Any]] = []
        errored: list[str] = []
        provider_order = ["bandsintown", "songkick", "ticketmaster"]
        results = await asyncio.gather(
            run_bit(),
            run_sk(),
            run_tm(),
            return_exceptions=True,
        )
        for provider_name, res in zip(provider_order, results, strict=False):
            if isinstance(res, QuotaExceededError):
                # Long-window quota lockout: stop using this provider for the rest of the run.
                # Every subsequent request would also be rejected and would further delay the
                # scheduler's eventual unblock. Record the lock-until horizon so the per-artist
                # next_due_at can be pushed past the quota window.
                retry_after = res.retry_after_seconds or 3600.0
                self._quota_locked[provider_name] = retry_after
                self.logger.error(
                    "%s quota exceeded while fetching '%s'; disabling %s for the rest of this "
                    "run (next request allowed in ~%s min). Detail: %s",
                    provider_name,
                    artist_name,
                    provider_name,
                    int(retry_after / 60),
                    res.detail[:200],
                )
                errored.append(provider_name)
                continue
            if isinstance(res, Exception):
                self.logger.warning("%s fetch raised for '%s': %s", provider_name, artist_name, res)
                errored.append(provider_name)
                continue
            if res is None:
                self.logger.warning(
                    "%s fetch failed for '%s' (HTTP error or invalid payload); will retry sooner",
                    provider_name,
                    artist_name,
                )
                errored.append(provider_name)
                continue
            merged.extend(res)
        return merged, errored
