#!/usr/bin/env python3
"""
XM Playlist (xmplaylist.com) — SiriusXM newest / most-heard → Plex or Jellyfin playlist.
"""

from __future__ import annotations

from typing import Any

from clients.client_jellyfin import JellyfinClient
from clients.client_plex import PlexClient
from clients.client_xmplaylist import MOST_HEARD_DAYS, XmplaylistClient
from commands.playlist_sync import PlaylistSyncCommand
from utils.library_cache_manager import get_library_cache_manager
from utils.text_normalizer import normalize_text

from .command_base import BaseCommand


def _dedupe_tracks(tracks: list[dict[str, str]]) -> list[dict[str, str]]:
    seen: set[tuple[str, str]] = set()
    out: list[dict[str, str]] = []
    for t in tracks:
        a = (t.get("artist") or "").strip()
        n = (t.get("track") or "").strip()
        if not a or not n:
            continue
        key = (normalize_text(a.lower()), normalize_text(n.lower()))
        if key in seen:
            continue
        seen.add(key)
        out.append({"artist": a, "track": n, "album": (t.get("album") or "").strip()})
    return out


def _build_playlist_title(cfg: dict[str, Any]) -> str:
    """Playlist / display title: [Cmdarr] [user] SXM - Station - Mode → Target"""
    station = (cfg.get("station_display_name") or cfg.get("station_deeplink") or "Station").strip()
    target = str(cfg.get("target", "plex")).lower()
    target_label = "Jellyfin" if target == "jellyfin" else "Plex"
    kind = str(cfg.get("playlist_kind", "newest")).lower()
    if kind == "most_heard":
        days = int(cfg.get("most_heard_days", 30))
        mode = f"Most Played ({days}d)"
    else:
        mode = "Newest"

    user_bracket = ""
    acc_id = cfg.get("plex_playlist_account_id")
    if acc_id and target == "plex":
        from clients.client_plex import PlexClient
        from commands.config_adapter import Config

        pc = PlexClient(Config())
        accounts = pc.get_accounts()
        acc = next((a for a in accounts if str(a.get("id", "")) == str(acc_id)), None)
        name = (acc.get("name") if acc else None) or str(acc_id)
        user_bracket = f" [{name}]"

    return f"[Cmdarr]{user_bracket} SXM - {station} - {mode} → {target_label}"


class PlaylistGeneratorXmplaylistCommand(BaseCommand):
    """Fetch xmplaylist.com track list and sync to Plex/Jellyfin."""

    def __init__(self, config=None):
        self.config_json = {}
        super().__init__(config)
        self.plex_client = PlexClient(self.config)
        self.library_cache_manager = get_library_cache_manager(self.config)
        self.last_run_stats: dict[str, Any] = {}

    def get_description(self) -> str:
        return "SiriusXM history via xmplaylist.com → Plex or Jellyfin playlist."

    def get_logger_name(self) -> str:
        return f"playlist_generator.{self.config_json.get('command_name', 'xmplaylist')}"

    def _get_target_client(self) -> tuple[PlexClient | JellyfinClient, str]:
        target = str((self.config_json or {}).get("target", "plex")).lower()
        if target == "jellyfin":
            return JellyfinClient(self.config), "jellyfin"
        return self.plex_client, "plex"

    def _delete_playlist_by_name(
        self, target_client: PlexClient | JellyfinClient, playlist_title: str
    ) -> None:
        try:
            pl = target_client.find_playlist_by_name(playlist_title)
            if not pl:
                return
            if isinstance(target_client, PlexClient):
                rk = pl.get("ratingKey")
                if rk:
                    target_client.delete_playlist(rk)
            else:
                pid = pl.get("Id")
                if pid:
                    target_client.delete_playlist(pid)
        except Exception as e:
            self.logger.warning(f"Could not delete old playlist '{playlist_title}': {e}")

    def _persist_after_success(self, playlist_title: str) -> None:
        try:
            from database.config_models import CommandConfig
            from database.database import get_database_manager

            cmd_name = self.config_json.get("command_name", "")
            if not cmd_name or not cmd_name.startswith("xmplaylist_"):
                return
            db = get_database_manager()
            session = db.get_config_session_sync()
            try:
                cmd = (
                    session.query(CommandConfig)
                    .filter(CommandConfig.command_name == cmd_name)
                    .first()
                )
                if cmd:
                    cfg = dict(cmd.config_json or {})
                    cfg["last_playlist_title"] = playlist_title
                    cmd.config_json = cfg
                    cmd.display_name = playlist_title
                    session.commit()
            finally:
                session.close()
        except Exception as e:
            self.logger.warning(f"Could not persist after success: {e}")

    async def execute(self) -> bool:
        self.last_run_stats = {}
        try:
            cfg = self.config_json or {}
            deeplink = (cfg.get("station_deeplink") or "").strip().lower()
            if not deeplink:
                self.logger.error("station_deeplink is required")
                self.last_run_stats = {"error": "station_deeplink is required"}
                return False

            max_tracks = int(cfg.get("max_tracks", 50))
            max_tracks = max(1, min(50, max_tracks))
            kind = str(cfg.get("playlist_kind", "newest")).lower()
            if kind not in ("newest", "most_heard"):
                kind = "newest"

            most_days = int(cfg.get("most_heard_days", 30))
            if most_days not in MOST_HEARD_DAYS:
                most_days = 30

            target_client, target_key = self._get_target_client()
            target_name = "Jellyfin" if target_key == "jellyfin" else "Plex"

            library_key = None
            if hasattr(target_client, "get_resolved_library_key"):
                library_key = target_client.get_resolved_library_key()
            if not library_key:
                self.logger.error("Could not resolve music library for target")
                self.last_run_stats = {"error": "No target library"}
                return False

            token_override = None
            if target_key == "plex":
                acc_id = cfg.get("plex_playlist_account_id")
                if acc_id:
                    token_override = self.plex_client.get_token_for_user(str(acc_id))
                    if not token_override:
                        self.logger.warning(
                            "Could not resolve Plex user token; using server token for playlist ops"
                        )

            if token_override:
                target_client = PlexClient(self.config, token_override=token_override)

            async with XmplaylistClient(self.config) as xm:
                if kind == "most_heard":
                    raw_tracks = await xm.fetch_tracks_most_heard(
                        deeplink, most_days, max_tracks=max_tracks
                    )
                else:
                    raw_tracks = await xm.fetch_tracks_newest(deeplink, max_tracks=max_tracks)

            tracks = _dedupe_tracks(raw_tracks)
            source_count = len(tracks)

            if not tracks:
                self.logger.warning("No tracks returned from xmplaylist for this station/mode")
                self.last_run_stats = {
                    "source_tracks": 0,
                    "matched_tracks": 0,
                    "added_tracks": 0,
                    "missing_tracks": 0,
                    "missing_sample": [],
                    "station_deeplink": deeplink,
                    "playlist_kind": kind,
                    "most_heard_days": most_days if kind == "most_heard" else None,
                    "target": target_name.lower(),
                }
                return True

            playlist_title = _build_playlist_title(cfg)
            last_title = cfg.get("last_playlist_title")
            if last_title and last_title != playlist_title:
                self._delete_playlist_by_name(target_client, last_title)

            if kind == "most_heard":
                summary = f"SiriusXM via xmplaylist.com — most played ({most_days}d)"
            else:
                summary = "SiriusXM via xmplaylist.com — newest tracks"

            cached_data = None
            if self.library_cache_manager:
                cached_data = self.library_cache_manager.get_library_cache(
                    target_key, str(library_key)
                )

            if hasattr(target_client, "_cached_library"):
                target_client._cached_library = cached_data

            result = target_client.sync_playlist(
                title=playlist_title,
                tracks=tracks,
                summary=summary,
                library_cache_manager=self.library_cache_manager,
                library_key=library_key,
            )

            success = bool(result.get("success"))
            found = int(result.get("found_tracks", 0))
            total = int(result.get("total_tracks", len(tracks)))
            unmatched = result.get("unmatched_tracks") or []
            if isinstance(unmatched, list):
                missing_sample = [str(x) for x in unmatched[:10]]
            else:
                missing_sample = []

            unmatched_set = set(unmatched) if isinstance(unmatched, list) else set()
            unmatched_dicts: list[dict[str, Any]] = []
            for t in tracks:
                line = f"{t.get('artist', '')} - {t.get('track', '')}"
                if line in unmatched_set:
                    unmatched_dicts.append(
                        {
                            "artist": t.get("artist", ""),
                            "track": t.get("track", ""),
                            "album": t.get("album", ""),
                        }
                    )

            discovery_sample: list[str] = []
            artists_sent = 0
            if (
                cfg.get("enable_artist_discovery")
                and unmatched_dicts
                and self.config.MUSICBRAINZ_ENABLED
            ):
                helper = PlaylistSyncCommand(self.config)
                helper.config_json = {
                    **cfg,
                    "playlist_name": f"SXM {cfg.get('station_display_name') or deeplink}",
                    "enable_artist_discovery": True,
                }
                d_stats = await helper._discover_and_add_artists(unmatched_dicts, cached_data)
                artists_sent = int(d_stats.get("artists_added", 0) or 0)
                for entry in d_stats.get("added_artists") or []:
                    if isinstance(entry, dict):
                        discovery_sample.append(
                            entry.get("resolved_name") or entry.get("name") or ""
                        )
                    else:
                        discovery_sample.append(str(entry))
                discovery_sample = [x for x in discovery_sample if x][:10]

            self.last_run_stats = {
                "source_tracks": source_count,
                "matched_tracks": found,
                "added_tracks": found,
                "missing_tracks": max(0, total - found),
                "missing_sample": missing_sample,
                "artists_sent_to_import_list": artists_sent,
                "discovery_sample": discovery_sample,
                "station_deeplink": deeplink,
                "station_display_name": cfg.get("station_display_name") or deeplink,
                "playlist_kind": kind,
                "most_heard_days": most_days if kind == "most_heard" else None,
                "target": target_name.lower(),
            }

            if success:
                self.logger.info(f"XM playlist '{playlist_title}': {found}/{total} tracks matched")
                self._persist_after_success(playlist_title)
            else:
                self.last_run_stats["error"] = result.get("message") or "sync_playlist failed"

            return success

        except Exception as e:
            self.logger.error(f"XM playlist generator error: {e}")
            self.last_run_stats = {"error": str(e)}
            raise
