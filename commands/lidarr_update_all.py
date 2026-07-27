#!/usr/bin/env python3
"""Trigger Lidarr Update All (RefreshArtist for the whole library)."""

from __future__ import annotations

from typing import Any

from clients.client_lidarr import LidarrClient
from commands.command_base import BaseCommand
from commands.config_adapter import ConfigAdapter


class LidarrUpdateAllCommand(BaseCommand):
    """Queue Lidarr RefreshArtist with no artist filter (UI: Update All)."""

    def __init__(self, config=None):
        super().__init__(config if config else ConfigAdapter())
        self.config_adapter = ConfigAdapter()
        self.last_run_stats: dict[str, Any] = {}

    def get_description(self) -> str:
        return "Trigger Lidarr Update All (refresh metadata for every artist)"

    def get_logger_name(self) -> str:
        return "cmdarr.lidarr_update_all"

    async def execute(self) -> bool:
        cfg = self.config_adapter
        if not cfg.LIDARR_API_KEY or not cfg.LIDARR_URL:
            self.last_run_stats = {"error": "Lidarr not configured"}
            self.logger.error("Lidarr not configured")
            return False

        client = LidarrClient(cfg)
        try:
            # Fire-and-forget: Update All can run for hours in Lidarr.
            result = await client.post_command("RefreshArtist")
            if not result:
                self.last_run_stats = {"error": "Lidarr returned no response for RefreshArtist"}
                return False

            command_id = result.get("id")
            status = result.get("status")
            self.logger.info(
                "Queued Lidarr Update All (RefreshArtist) id=%s status=%s",
                command_id,
                status,
            )

            self.last_run_stats = {
                "lidarr_command_id": command_id,
                "lidarr_command_name": "RefreshArtist",
                "lidarr_status": status,
            }
            if str(status or "").lower() == "failed":
                self.last_run_stats["error"] = "Lidarr RefreshArtist reported failed"
                return False
            return True
        except Exception as e:
            self.logger.error("Lidarr Update All failed: %s", e)
            self.last_run_stats = {"error": str(e)}
            return False
        finally:
            session = getattr(client, "session", None)
            if session and not session.closed:
                await session.close()
