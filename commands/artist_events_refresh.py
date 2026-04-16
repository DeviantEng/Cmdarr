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


class ArtistEventsRefreshCommand(BaseCommand):
    """Fetch upcoming events per Lidarr artist; TTL-driven batches."""

    def __init__(self, config=None):
        super().__init__(config if config else ConfigAdapter())
        self.config_adapter = ConfigAdapter()
        self.last_run_stats: dict[str, Any] = {}

    def get_description(self) -> str:
        return "Refresh artist events for Lidarr library (Bandsintown / Songkick / Ticketmaster)"

    def get_logger_name(self) -> str:
        return "cmdarr.artist_events_refresh"

    async def execute(self) -> bool:
        log = self.logger
        cfg = self.config_adapter
        cj = getattr(self, "config_json", None) or {}
        ttl_days = int(cj.get("refresh_ttl_days", 14))
        artists_per_run = int(cj.get("artists_per_run", 15))

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
            self._delete_past_events(session, now)
            session.commit()

            rows = (
                session.query(LidarrArtist)
                .outerjoin(
                    ArtistEventRefresh,
                    LidarrArtist.artist_mbid == ArtistEventRefresh.artist_mbid,
                )
                .filter(
                    or_(
                        ArtistEventRefresh.next_due_at.is_(None),
                        ArtistEventRefresh.next_due_at < now,
                    )
                )
                .order_by(
                    case((ArtistEventRefresh.next_due_at.is_(None), 0), else_=1),
                    ArtistEventRefresh.next_due_at.asc(),
                )
                .limit(artists_per_run)
                .all()
            )

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

            for la in rows:
                merged = await self._fetch_for_artist(
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
                ar = (
                    session.query(ArtistEventRefresh)
                    .filter(ArtistEventRefresh.artist_mbid == la.artist_mbid)
                    .first()
                )
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
            }
            log.info(
                f"Artist events refresh: {processed} artists, {total_new} new canonical events, {total_sources} new sources"
            )
            return True
        except Exception as e:
            log.exception("Artist events refresh failed: %s", e)
            session.rollback()
            self.last_run_stats = {"error": str(e)}
            return False
        finally:
            session.close()

    def _delete_past_events(self, session, now: datetime) -> None:
        cutoff = now - timedelta(days=1)
        old_ids = [
            r[0]
            for r in session.query(ArtistEvent.id).filter(ArtistEvent.starts_at_utc < cutoff).all()
        ]
        if not old_ids:
            return
        session.query(ArtistEventSource).filter(
            ArtistEventSource.concert_event_id.in_(old_ids)
        ).delete(synchronize_session=False)
        session.query(ArtistEvent).filter(ArtistEvent.id.in_(old_ids)).delete(
            synchronize_session=False
        )

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
    ) -> list[dict[str, Any]]:
        async def run_bit():
            if not bit_on or not bit_app:
                return []
            async with BandsintownClient(cfg, bit_app) as c:
                return await c.fetch_upcoming_events(artist_name, artist_mbid)

        async def run_sk():
            if not sk_on or not sk_key:
                return []
            async with SongkickClient(cfg, sk_key) as c:
                return await c.fetch_upcoming_events(artist_name, artist_mbid)

        async def run_tm():
            if not tm_on or not tm_key:
                return []
            async with TicketmasterClient(cfg, tm_key) as c:
                return await c.fetch_upcoming_events(artist_name, artist_mbid)

        merged: list[dict[str, Any]] = []
        for coro in await asyncio.gather(
            run_bit(),
            run_sk(),
            run_tm(),
            return_exceptions=True,
        ):
            if isinstance(coro, Exception):
                self.logger.warning("Provider fetch failed: %s", coro)
                continue
            merged.extend(coro or [])
        return merged
