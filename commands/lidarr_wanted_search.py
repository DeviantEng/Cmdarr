#!/usr/bin/env python3
"""Search top X Lidarr Wanted albums; cooldown grabs and empty results."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy.orm.attributes import flag_modified

from clients.client_lidarr import LidarrClient
from commands.command_base import BaseCommand
from commands.config_adapter import ConfigAdapter
from database.config_models import CommandConfig, LidarrWantedSearchIgnore
from database.database import get_database_manager
from utils.lidarr_maintenance import (
    DEFAULT_IGNORE_DAYS,
    DEFAULT_SETTLE_SECONDS,
    DEFAULT_SORT,
    DEFAULT_TOP_X,
    album_matches_types,
    extract_album_ids_from_history,
    extract_album_ids_from_queue,
    normalize_album_types,
    normalize_wanted_record,
    resolve_sort,
)


class LidarrWantedSearchCommand(BaseCommand):
    """Select top X Wanted/Missing albums and trigger AlbumSearch; ignore misses."""

    def __init__(self, config=None):
        super().__init__(config if config else ConfigAdapter())
        self.config_adapter = ConfigAdapter()
        self.last_run_stats: dict[str, Any] = {}

    def get_description(self) -> str:
        return "Search top X Lidarr Wanted albums and temporarily ignore empty results"

    def get_logger_name(self) -> str:
        return "cmdarr.lidarr_wanted_search"

    async def execute(self) -> bool:
        cfg = self.config_adapter
        if not cfg.LIDARR_API_KEY or not cfg.LIDARR_URL:
            self.last_run_stats = {"error": "Lidarr not configured"}
            self.logger.error("Lidarr not configured")
            return False

        cj = getattr(self, "config_json", None) or {}
        top_x = max(1, min(50, int(cj.get("top_x", DEFAULT_TOP_X))))
        ignore_days = max(1, min(365, int(cj.get("ignore_days", DEFAULT_IGNORE_DAYS))))
        settle_seconds = max(0, min(300, int(cj.get("settle_seconds", DEFAULT_SETTLE_SECONDS))))
        album_types = normalize_album_types(cj.get("album_types", "album"))
        sort_option = str(cj.get("sort_by", DEFAULT_SORT) or DEFAULT_SORT)
        lidarr_sort_key, lidarr_sort_dir = resolve_sort(sort_option)
        command_name = str(cj.get("command_name") or "lidarr_wanted_search")

        client = LidarrClient(cfg)
        db = get_database_manager()
        session = db.get_config_session_sync()
        now = datetime.now(UTC)

        try:
            expired = self._purge_expired_ignores(session, now)
            if expired:
                self.logger.info("Purged %s expired Wanted-search ignore(s)", expired)

            active_ignored = self._active_ignored_album_ids(session, now)
            self.logger.info(
                "Wanted search: top_x=%s types=%s sort=%s ignore_days=%s active_ignores=%s",
                top_x,
                ",".join(sorted(album_types)),
                sort_option,
                ignore_days,
                len(active_ignored),
            )

            selected = await self._select_wanted_albums(
                client,
                top_x=top_x,
                album_types=album_types,
                sort_key=lidarr_sort_key,
                sort_direction=lidarr_sort_dir,
                ignored_ids=active_ignored,
            )
            if not selected:
                self.logger.info("No Wanted albums matched filters (after ignore list)")
                self.last_run_stats = {
                    "albums_selected": 0,
                    "albums_searched": 0,
                    "downloads_found": 0,
                    "ignored_added": 0,
                    "ignores_expired_purged": expired,
                    "active_ignores": len(active_ignored),
                    "album_types": sorted(album_types),
                    "sort_by": sort_option,
                    "message": "No matching Wanted albums to search",
                }
                self._bump_lifetime_counters(session, command_name, searched=0, found=0, ignored=0)
                session.commit()
                return True

            album_ids = [a["lidarr_album_id"] for a in selected if a.get("lidarr_album_id")]
            self.logger.info(
                "Searching %s Wanted album(s): %s",
                len(album_ids),
                ", ".join(
                    f"{a.get('artist_name') or '?'} – {a.get('album_title')}" for a in selected[:10]
                ),
            )

            cmd_result = await client.post_command("AlbumSearch", albumIds=album_ids)
            if not cmd_result:
                self.last_run_stats = {"error": "Lidarr returned no response for AlbumSearch"}
                return False

            lidarr_cmd_id = cmd_result.get("id")
            if lidarr_cmd_id is not None:
                finished = await client.wait_for_command(
                    int(lidarr_cmd_id),
                    poll_interval=2.0,
                    timeout_seconds=max(120.0, settle_seconds + 180.0),
                )
                status = (finished or {}).get("status") if finished else cmd_result.get("status")
                if str(status or "").lower() == "failed":
                    self.last_run_stats = {
                        "error": "Lidarr AlbumSearch reported failed",
                        "lidarr_command_id": lidarr_cmd_id,
                    }
                    return False

            if settle_seconds:
                self.logger.info("Waiting %ss for grabs to appear in queue", settle_seconds)
                await asyncio.sleep(settle_seconds)

            queue = await client.get_queue()
            queued_ids = extract_album_ids_from_queue(queue)
            history = await client.get_history_for_albums(album_ids, event_type=1)
            grabbed_ids = extract_album_ids_from_history(history)
            found_ids = queued_ids | grabbed_ids

            ignored_until = now + timedelta(days=ignore_days)
            downloads_found = 0
            ignored_added = 0
            grabbed_cooled = 0
            found_titles: list[str] = []
            ignored_titles: list[str] = []

            for album in selected:
                aid = album.get("lidarr_album_id")
                if aid is None:
                    continue
                label = f"{album.get('artist_name') or '?'} – {album.get('album_title')}"
                if aid in found_ids:
                    downloads_found += 1
                    found_titles.append(label)
                    self._upsert_ignore(
                        session,
                        album,
                        command_name=command_name,
                        now=now,
                        ignored_until=ignored_until,
                        reason="grabbed",
                    )
                    grabbed_cooled += 1
                    self.logger.info(
                        "Download activity for Wanted album: %s — cooling down until %s",
                        label,
                        ignored_until.date().isoformat(),
                    )
                    continue

                self._upsert_ignore(
                    session,
                    album,
                    command_name=command_name,
                    now=now,
                    ignored_until=ignored_until,
                    reason="no_release_found",
                )
                ignored_added += 1
                ignored_titles.append(label)
                self.logger.info(
                    "No release found for %s — ignoring until %s",
                    label,
                    ignored_until.date().isoformat(),
                )

            self._bump_lifetime_counters(
                session,
                command_name,
                searched=len(album_ids),
                found=downloads_found,
                ignored=ignored_added,
            )
            session.commit()

            active_after = len(self._active_ignored_album_ids(session, now))
            self.last_run_stats = {
                "albums_selected": len(album_ids),
                "albums_searched": len(album_ids),
                "downloads_found": downloads_found,
                "grabbed_cooled": grabbed_cooled,
                "ignored_added": ignored_added,
                "ignores_expired_purged": expired,
                "active_ignores": active_after,
                "album_types": sorted(album_types),
                "sort_by": sort_option,
                "top_x": top_x,
                "ignore_days": ignore_days,
                "lidarr_command_id": lidarr_cmd_id,
                "found_sample": found_titles[:10],
                "ignored_sample": ignored_titles[:10],
            }
            return True
        except Exception as e:
            session.rollback()
            self.logger.error("Lidarr Wanted search failed: %s", e)
            self.last_run_stats = {"error": str(e)}
            return False
        finally:
            session.close()
            session_obj = getattr(client, "session", None)
            if session_obj and not session_obj.closed:
                await session_obj.close()

    def _upsert_ignore(
        self,
        session,
        album: dict[str, Any],
        *,
        command_name: str,
        now: datetime,
        ignored_until: datetime,
        reason: str,
    ) -> None:
        """Put/refresh an album on the temporary skip list (no release or already grabbed)."""
        aid = album.get("lidarr_album_id")
        if aid is None:
            return
        existing = (
            session.query(LidarrWantedSearchIgnore)
            .filter(LidarrWantedSearchIgnore.lidarr_album_id == aid)
            .first()
        )
        if existing:
            existing.ignored_until = ignored_until
            existing.ignored_at = now
            existing.reason = reason
            existing.command_name = command_name
            existing.search_count = int(existing.search_count or 0) + 1
            existing.album_title = album.get("album_title") or existing.album_title
            existing.artist_name = album.get("artist_name") or existing.artist_name
            existing.album_type = album.get("album_type") or existing.album_type
            existing.release_date = album.get("release_date") or existing.release_date
            return
        session.add(
            LidarrWantedSearchIgnore(
                lidarr_album_id=aid,
                foreign_album_id=album.get("foreign_album_id"),
                artist_name=album.get("artist_name"),
                album_title=album.get("album_title") or "",
                album_type=album.get("album_type"),
                release_date=album.get("release_date"),
                ignored_at=now,
                ignored_until=ignored_until,
                reason=reason,
                command_name=command_name,
                search_count=1,
            )
        )

    async def _select_wanted_albums(
        self,
        client: LidarrClient,
        *,
        top_x: int,
        album_types: set[str],
        sort_key: str,
        sort_direction: str,
        ignored_ids: set[int],
    ) -> list[dict[str, Any]]:
        """Page through Wanted/Missing until top_x matching albums are collected."""
        selected: list[dict[str, Any]] = []
        page = 1
        page_size = 50
        total_records: int | None = None
        scanned = 0
        max_pages = 40  # safety cap (2000 records)

        while len(selected) < top_x and page <= max_pages:
            payload = await client.get_wanted_missing(
                page=page,
                page_size=page_size,
                sort_key=sort_key,
                sort_direction=sort_direction,
                monitored=True,
                include_artist=True,
            )
            records = payload.get("records") or []
            if total_records is None:
                try:
                    total_records = int(payload.get("totalRecords") or 0)
                except TypeError, ValueError:
                    total_records = 0
            if not records:
                break

            for record in records:
                scanned += 1
                normalized = normalize_wanted_record(record)
                aid = normalized.get("lidarr_album_id")
                if aid is None or aid in ignored_ids:
                    continue
                if not album_matches_types(record.get("albumType"), album_types):
                    continue
                selected.append(normalized)
                if len(selected) >= top_x:
                    break

            if total_records is not None and page * page_size >= total_records:
                break
            if len(records) < page_size:
                break
            page += 1

        self.logger.debug(
            "Wanted scan: pages=%s scanned=%s matched=%s totalRecords=%s",
            page,
            scanned,
            len(selected),
            total_records,
        )
        return selected

    def _purge_expired_ignores(self, session, now: datetime) -> int:
        q = session.query(LidarrWantedSearchIgnore).filter(
            LidarrWantedSearchIgnore.ignored_until <= now
        )
        count = q.count()
        if count:
            q.delete(synchronize_session=False)
        return count

    def _active_ignored_album_ids(self, session, now: datetime) -> set[int]:
        rows = (
            session.query(LidarrWantedSearchIgnore.lidarr_album_id)
            .filter(LidarrWantedSearchIgnore.ignored_until > now)
            .all()
        )
        return {int(r[0]) for r in rows if r[0] is not None}

    def _bump_lifetime_counters(
        self,
        session,
        command_name: str,
        *,
        searched: int,
        found: int,
        ignored: int,
    ) -> None:
        """Persist cumulative counters on the command's config_json."""
        row = (
            session.query(CommandConfig)
            .filter(CommandConfig.command_name == command_name)
            .filter(CommandConfig.deleted_at.is_(None))
            .first()
        )
        if not row:
            return
        cfg = dict(row.config_json or {})
        cfg["lifetime_searched"] = int(cfg.get("lifetime_searched") or 0) + searched
        cfg["lifetime_downloads_found"] = int(cfg.get("lifetime_downloads_found") or 0) + found
        cfg["lifetime_ignored"] = int(cfg.get("lifetime_ignored") or 0) + ignored
        row.config_json = cfg
        flag_modified(row, "config_json")
