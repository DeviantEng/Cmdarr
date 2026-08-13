#!/usr/bin/env python3
"""Library Audit command — inventory + batched FLAC authenticity analysis."""

from __future__ import annotations

from typing import Any

from commands.command_base import BaseCommand
from commands.config_adapter import Config as ConfigAdapter
from database.database import get_database_manager
from services.config_service import config_service
from services.library_audit.flac_detective import get_default_provider
from services.library_audit.service import (
    get_music_root,
    is_feature_enabled,
    run_audit_cycle,
    validate_root,
)
from utils.logger import get_logger


class LibraryAuditCommand(BaseCommand):
    """Scheduled/manual Library Audit: inventory due files and analyze a batch."""

    def __init__(self, config=None):
        super().__init__(config if config else ConfigAdapter())
        self.last_run_stats: dict[str, Any] = {}

    def get_description(self) -> str:
        return "Inventory music files and analyze pending FLACs for authenticity issues"

    def get_logger_name(self) -> str:
        return "cmdarr.commands.library_audit"

    def _get_config_json(self) -> dict[str, Any]:
        cfg = getattr(self, "config_json", None) or {}
        return dict(cfg) if isinstance(cfg, dict) else {}

    async def execute(self) -> bool:
        logger = get_logger(self.get_logger_name())
        self.last_run_stats = {}

        if not is_feature_enabled(config_service.get):
            self.last_run_stats = {
                "error": "Library Audit is disabled (LIBRARY_AUDIT_ENABLED=false)"
            }
            logger.error(self.last_run_stats["error"])
            return False

        provider = get_default_provider()
        health = provider.health()
        if not health.healthy:
            self.last_run_stats = {
                "error": health.message or "Analyzer provider unhealthy",
                "provider": health.provider,
            }
            logger.error(self.last_run_stats["error"])
            return False

        root = get_music_root(config_service.get)
        ok, msg = validate_root(root)
        if not ok:
            self.last_run_stats = {"error": msg}
            logger.error(msg)
            return False

        cj = self._get_config_json()
        batch_size = max(1, min(500, int(cj.get("analysis_batch_size", 25))))
        inventory_hours = max(1, min(168, int(cj.get("inventory_interval_hours", 24))))
        extensions = cj.get("extensions") or [".flac"]
        if isinstance(extensions, str):
            extensions = [e.strip() for e in extensions.split(",") if e.strip()]
        retention = max(1, min(3650, int(cj.get("missing_retention_days", 90))))
        mode = str(cj.get("provider_mode") or "standard")

        manager = get_database_manager()
        session = manager.get_library_audit_session_sync()
        try:
            summary = run_audit_cycle(
                session,
                root,
                analysis_batch_size=batch_size,
                inventory_interval_hours=inventory_hours,
                extensions=list(extensions),
                missing_retention_days=retention,
                provider_mode=mode,
                provider=provider,
            )
            inv = summary.inventory
            an = summary.analysis
            self.last_run_stats = {
                "inventory_skipped": summary.inventory_skipped,
                "inventory": None
                if inv is None
                else {
                    "status": inv.status,
                    "files_seen": inv.files_seen,
                    "eligible_files_seen": inv.eligible_files_seen,
                    "new_files": inv.new_files,
                    "changed_files": inv.changed_files,
                    "missing_files": inv.missing_files,
                    "errors": inv.errors,
                },
                "analysis": {
                    "attempted": an.attempted,
                    "completed": an.completed,
                    "authentic": an.authentic,
                    "warning": an.warning,
                    "suspicious": an.suspicious,
                    "fake_certain": an.fake_certain,
                    "inconclusive": an.inconclusive,
                    "errors": an.errors,
                },
                "retention_deleted": summary.retention_deleted,
                "pending_queue": summary.pending_queue,
                "needs_review": summary.needs_review,
                "provider": health.provider,
                "provider_version": health.provider_version,
            }
            if inv is not None and inv.status == "FAILED":
                logger.error(f"Inventory failed: {inv.error_message}")
                return False
            logger.info(
                "Library Audit completed: "
                f"analyzed {an.completed}/{an.attempted}, "
                f"pending={summary.pending_queue}, needs_review={summary.needs_review}"
            )
            return True
        except Exception as exc:
            logger.error(f"Library Audit failed: {exc}", exc_info=True)
            self.last_run_stats = {"error": str(exc)}
            return False
        finally:
            session.close()
