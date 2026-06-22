#!/usr/bin/env python3
"""Batch refresh live event data for Lidarr artists from enabled providers."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from typing import Any

import aiohttp
from sqlalchemy import case, func, or_

from clients.client_deezer_events import DeezerEventsClient
from clients.client_lidarr import LidarrClient
from clients.client_seatgeek import SeatGeekClient
from clients.client_ticketmaster import TicketmasterClient
from commands.command_base import BaseCommand
from commands.config_adapter import ConfigAdapter
from database.config_models import (
    ArtistConcertHiddenEvent,
    ArtistEvent,
    ArtistEventRefresh,
    ArtistEventSource,
    LidarrArtist,
)
from database.database import get_database_manager
from services.config_service import config_service
from utils.cmdarr_user_agent import resolve_cmdarr_user_agent
from utils.event_ingest import persist_normalized_events
from utils.http_client import QuotaExceededError
from utils.lidarr_artist_sync import upsert_lidarr_artists_from_payload
from utils.venue_geocode import resolve_venue_coordinates


class ArtistEventsRefreshCommand(BaseCommand):
    """Fetch upcoming events per Lidarr artist; TTL-driven batches."""

    def __init__(self, config=None):
        super().__init__(config if config else ConfigAdapter())
        self.config_adapter = ConfigAdapter()
        self.last_run_stats: dict[str, Any] = {}
        self._quota_locked: dict[str, float] = {}

    def get_description(self) -> str:
        return "Refresh artist events for Lidarr library (Ticketmaster / SeatGeek / Deezer)"

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

        tm_on = config_service.get("ARTIST_EVENTS_TICKETMASTER_ENABLED", False)
        tm_key = (config_service.get("ARTIST_EVENTS_TICKETMASTER_API_KEY", "") or "").strip()
        sg_on = config_service.get("ARTIST_EVENTS_SEATGEEK_ENABLED", False)
        sg_id = (config_service.get("ARTIST_EVENTS_SEATGEEK_CLIENT_ID", "") or "").strip()
        dz_on = config_service.get("ARTIST_EVENTS_DEEZER_ENABLED", False)
        dz_arl = (config_service.get("ARTIST_EVENTS_DEEZER_ARL", "") or "").strip()

        tm_ready = bool(tm_on and tm_key)
        sg_ready = bool(sg_on and sg_id)
        dz_ready = bool(dz_on and dz_arl)
        if not tm_ready and not sg_ready and not dz_ready:
            log.error("No event provider enabled with valid credentials")
            self.last_run_stats = {
                "error": (
                    "Enable Ticketmaster, SeatGeek, and/or Deezer with credentials in "
                    "Config → Event Sources"
                )
            }
            return False

        if not cfg.LIDARR_API_KEY or not cfg.LIDARR_URL:
            log.error("Lidarr not configured")
            self.last_run_stats = {"error": "Lidarr not configured"}
            return False

        db = get_database_manager()
        session = db.get_config_session_sync()
        now = datetime.now(UTC)
        try:
            hidden_past_pruned, hidden_orphans_removed = self._prune_stale_hidden_single_events(
                session, now
            )
            past_events_purged = self._delete_past_events(session, now, past_event_retention_days)
            session.commit()
            if hidden_past_pruned or hidden_orphans_removed or past_events_purged:
                log.info(
                    "Event cleanup: %s past per-event hide(s) removed, %s orphan hide(s) removed, "
                    "%s concert row(s) purged (retention %s day(s))",
                    hidden_past_pruned,
                    hidden_orphans_removed,
                    past_events_purged,
                    past_event_retention_days,
                )

            inserted, updated, lidarr_total = await self._sync_lidarr_artist_cache(
                cfg, session, now, log
            )
            if lidarr_total == 0:
                log.warning("Lidarr artist cache is empty after sync; nothing to refresh")
                self.last_run_stats = {
                    "error": "No Lidarr artists found — check Lidarr connection and library",
                    "past_events_purged": past_events_purged,
                    "past_event_retention_days": past_event_retention_days,
                    "hidden_past_single_events_pruned": hidden_past_pruned,
                    "hidden_single_event_orphans_removed": hidden_orphans_removed,
                }
                return False

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
                    "past_events_purged": past_events_purged,
                    "past_event_retention_days": past_event_retention_days,
                    "hidden_past_single_events_pruned": hidden_past_pruned,
                    "hidden_single_event_orphans_removed": hidden_orphans_removed,
                }
                return True

            total_new = 0
            total_sources = 0
            processed = 0
            artists_with_errors = 0
            provider_error_counts: dict[str, int] = {
                "ticketmaster": 0,
                "seatgeek": 0,
                "deezer": 0,
            }
            self._quota_locked = {}

            for la in rows:
                merged, provider_errors, resolved_dz_id = await self._fetch_for_artist(
                    cfg,
                    la.artist_name,
                    la.artist_mbid,
                    la.deezer_artist_id,
                    tm_on,
                    tm_key,
                    sg_on,
                    sg_id,
                    dz_on,
                    dz_arl,
                )
                if resolved_dz_id and resolved_dz_id != la.deezer_artist_id:
                    la.deezer_artist_id = resolved_dz_id
                if merged:
                    await self._geocode_normalized_events(cfg, session, merged, max_lookups=5)
                    n, s = persist_normalized_events(session, merged)
                    total_new += n
                    total_sources += s
                    await self._geocode_stored_events_for_artist(
                        cfg, session, la.artist_mbid, max_lookups=2
                    )
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
                "hidden_past_single_events_pruned": hidden_past_pruned,
                "hidden_single_event_orphans_removed": hidden_orphans_removed,
                "quota_locked_providers": sorted(self._quota_locked.keys()),
            }
            log.info(
                "Artist events refresh: %s artists processed (force_all=%s, all_due=%s, cap=%s), "
                "%s new events, %s new sources, %s artists had provider errors "
                "(tm=%s sg=%s dz=%s)",
                processed,
                force_refresh_all,
                refresh_all_due,
                artists_per_run,
                total_new,
                total_sources,
                artists_with_errors,
                provider_error_counts["ticketmaster"],
                provider_error_counts["seatgeek"],
                provider_error_counts["deezer"],
            )
            return True
        except Exception as e:
            log.exception("Artist events refresh failed: %s", e)
            session.rollback()
            self.last_run_stats = {"error": str(e)}
            return False
        finally:
            session.close()

    async def _sync_lidarr_artist_cache(
        self, cfg: ConfigAdapter, session, now: datetime, log
    ) -> tuple[int, int, int]:
        """Refresh lidarr_artist from Lidarr API. Returns (inserted, updated, total_rows)."""
        log.info("Syncing Lidarr artist cache before event provider queries")
        async with LidarrClient(cfg) as lidarr_client:
            lidarr_rows = await lidarr_client.get_all_artists()
        inserted, updated = upsert_lidarr_artists_from_payload(session, lidarr_rows, now=now)
        session.commit()
        total = session.query(func.count(LidarrArtist.id)).scalar() or 0
        log.info(
            "Lidarr artist cache: %s artists from API (%s inserted, %s updated, %s cached rows)",
            len(lidarr_rows),
            inserted,
            updated,
            total,
        )
        return inserted, updated, int(total)

    def _prune_stale_hidden_single_events(self, session, now: datetime) -> tuple[int, int]:
        """Remove per-event hides that no longer matter: old past shows and broken FK refs."""
        hide_prune_cutoff = now - timedelta(days=1)
        n_past = (
            session.query(ArtistConcertHiddenEvent)
            .filter(
                ArtistConcertHiddenEvent.event_id.in_(
                    session.query(ArtistEvent.id).filter(
                        ArtistEvent.starts_at_utc < hide_prune_cutoff
                    )
                )
            )
            .delete(synchronize_session=False)
        )
        n_orphan = (
            session.query(ArtistConcertHiddenEvent)
            .filter(~ArtistConcertHiddenEvent.event_id.in_(session.query(ArtistEvent.id)))
            .delete(synchronize_session=False)
        )
        return int(n_past or 0), int(n_orphan or 0)

    def _delete_past_events(self, session, now: datetime, retention_days: int) -> int:
        """Remove canonical events whose start time is older than `retention_days` ago."""
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
        deezer_artist_id: str | None,
        tm_on: bool,
        tm_key: str,
        sg_on: bool,
        sg_client_id: str,
        dz_on: bool,
        dz_arl: str,
    ) -> tuple[list[dict[str, Any]], list[str], str | None]:
        """Return (merged_events, errored_providers, resolved_deezer_artist_id)."""

        async def run_tm():
            if not tm_on or not tm_key or "ticketmaster" in self._quota_locked:
                return []
            async with TicketmasterClient(cfg, tm_key) as c:
                return await c.fetch_upcoming_events(artist_name, artist_mbid)

        async def run_sg():
            if not sg_on or not sg_client_id or "seatgeek" in self._quota_locked:
                return []
            async with SeatGeekClient(cfg, sg_client_id) as c:
                return await c.fetch_upcoming_events(artist_name, artist_mbid)

        async def run_dz():
            if not dz_on or not dz_arl or "deezer" in self._quota_locked:
                return [], deezer_artist_id
            async with DeezerEventsClient(cfg, dz_arl) as c:
                return await c.fetch_upcoming_events(
                    artist_name, artist_mbid, deezer_artist_id=deezer_artist_id
                )

        merged: list[dict[str, Any]] = []
        errored: list[str] = []
        resolved_dz_id = deezer_artist_id
        provider_order = ["ticketmaster", "seatgeek", "deezer"]
        results = await asyncio.gather(
            run_tm(),
            run_sg(),
            run_dz(),
            return_exceptions=True,
        )
        for provider_name, res in zip(provider_order, results, strict=False):
            if provider_name == "deezer" and isinstance(res, tuple):
                events, resolved_dz_id = res
                res = events
            if isinstance(res, QuotaExceededError):
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
        return merged, errored, resolved_dz_id

    async def _geocode_normalized_events(
        self,
        cfg: ConfigAdapter,
        session,
        items: list[dict[str, Any]],
        *,
        max_lookups: int,
    ) -> None:
        pending = [
            item
            for item in items
            if item.get("venue_lat") is None
            and item.get("venue_lon") is None
            and (item.get("venue_name") or item.get("venue_city"))
        ]
        if not pending or max_lookups <= 0:
            return
        ua = resolve_cmdarr_user_agent(cfg) or "Cmdarr (artist events geocode)"
        dbapi = session.connection().connection
        cursor = dbapi.cursor()
        async with aiohttp.ClientSession() as http:
            for item in pending[:max_lookups]:
                coords = await resolve_venue_coordinates(
                    http,
                    cursor,
                    item.get("venue_name"),
                    item.get("venue_city"),
                    item.get("venue_region"),
                    user_agent=ua,
                    country=(item.get("venue_country") or "US"),
                )
                if coords:
                    item["venue_lat"], item["venue_lon"] = coords
                await asyncio.sleep(1.05)
        dbapi.commit()

    async def _geocode_stored_events_for_artist(
        self,
        cfg: ConfigAdapter,
        session,
        artist_mbid: str,
        *,
        max_lookups: int,
    ) -> None:
        rows = (
            session.query(ArtistEvent)
            .filter(
                ArtistEvent.artist_mbid == artist_mbid,
                or_(ArtistEvent.venue_lat.is_(None), ArtistEvent.venue_lon.is_(None)),
                ArtistEvent.venue_name.isnot(None),
            )
            .limit(max_lookups)
            .all()
        )
        if not rows:
            return
        ua = resolve_cmdarr_user_agent(cfg) or "Cmdarr (artist events geocode)"
        dbapi = session.connection().connection
        cursor = dbapi.cursor()
        async with aiohttp.ClientSession() as http:
            for ev in rows:
                coords = await resolve_venue_coordinates(
                    http,
                    cursor,
                    ev.venue_name,
                    ev.venue_city,
                    ev.venue_region,
                    user_agent=ua,
                    country=(ev.venue_country or "US"),
                )
                if coords:
                    ev.venue_lat, ev.venue_lon = coords
                await asyncio.sleep(1.05)
        dbapi.commit()
