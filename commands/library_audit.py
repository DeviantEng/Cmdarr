#!/usr/bin/env python3
"""Library Audit command — inventory audio files + triage/deep FLAC/MP3 analysis."""

from __future__ import annotations

from typing import Any

from commands.command_base import BaseCommand
from commands.config_adapter import Config as ConfigAdapter
from database.database import get_database_manager
from services.config_service import config_service
from services.library_audit.flac_detective import FlacAnalysisOptions
from services.library_audit.formats import (
    DEFAULT_ANALYSIS_EXTENSIONS,
    DEFAULT_INVENTORY_EXTENSIONS,
    normalize_extensions,
)
from services.library_audit.router import get_composite_provider
from services.library_audit.service import (
    get_music_root,
    run_audit_cycle,
    validate_root,
)
from utils.logger import get_logger


def _parse_ext_list(value: Any, fallback: list[str]) -> list[str]:
    if value is None:
        return list(fallback)
    if isinstance(value, str):
        items = [e.strip() for e in value.split(",") if e.strip()]
        return normalize_extensions(items, fallback)
    if isinstance(value, list):
        return normalize_extensions([str(e) for e in value], fallback)
    return list(fallback)


def _float_cfg(value: Any, default: float, lo: float, hi: float) -> float:
    try:
        return max(lo, min(hi, float(value)))
    except TypeError, ValueError:
        return default


def _int_cfg(value: Any, default: int, lo: int, hi: int) -> int:
    try:
        return max(lo, min(hi, int(value)))
    except TypeError, ValueError:
        return default


class LibraryAuditCommand(BaseCommand):
    """Scheduled/manual Library Audit: inventory due files and analyze a FLAC/MP3 batch."""

    def __init__(self, config=None):
        super().__init__(config if config else ConfigAdapter())
        self.last_run_stats: dict[str, Any] = {}

    def get_description(self) -> str:
        return (
            "Inventory audio files; triage then deep-analyze FLACs (authenticity) and MP3s "
            "(bitrate/CBR-VBR); other formats are inventoried only until analyzers exist"
        )

    def get_logger_name(self) -> str:
        return "cmdarr.commands.library_audit"

    def _get_config_json(self) -> dict[str, Any]:
        cfg = getattr(self, "config_json", None) or {}
        return dict(cfg) if isinstance(cfg, dict) else {}

    async def execute(self) -> bool:
        logger = get_logger(self.get_logger_name())
        self.last_run_stats = {}

        cj = self._get_config_json()
        flac_options = FlacAnalysisOptions(
            triage_sample_seconds=_float_cfg(cj.get("triage_sample_seconds"), 20.0, 5.0, 120.0),
            deep_sample_seconds=_float_cfg(cj.get("deep_sample_seconds"), 60.0, 15.0, 180.0),
            short_track_seconds=_float_cfg(cj.get("short_track_seconds"), 10.0, 1.0, 60.0),
            require_deep_for_fake_certain=bool(cj.get("require_deep_for_fake_certain", True)),
        )
        provider = get_composite_provider(flac_options=flac_options)
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

        # Prefer split batch sizes; legacy analysis_batch_size maps to triage.
        triage_batch = _int_cfg(
            cj.get("triage_batch_size", cj.get("analysis_batch_size", 150)),
            150,
            25,
            500,
        )
        deep_batch = _int_cfg(cj.get("deep_batch_size", 10), 10, 0, 50)
        prefer_triage_first = bool(cj.get("prefer_triage_first", True))
        deep_after_triage_pct = _float_cfg(cj.get("deep_after_triage_pct"), 80.0, 0.0, 100.0)
        inventory_hours = _int_cfg(cj.get("inventory_interval_hours", 24), 24, 1, 168)
        # Prefer inventory_extensions. Legacy "extensions": [".flac"] was the old
        # default — expand to all inventory formats. Custom legacy lists are kept.
        if "inventory_extensions" in cj:
            inventory_extensions = _parse_ext_list(
                cj.get("inventory_extensions"), DEFAULT_INVENTORY_EXTENSIONS
            )
        else:
            legacy = cj.get("extensions")
            legacy_norm = _parse_ext_list(legacy, DEFAULT_ANALYSIS_EXTENSIONS) if legacy else None
            if legacy_norm is None or legacy_norm == [".flac"]:
                inventory_extensions = list(DEFAULT_INVENTORY_EXTENSIONS)
            else:
                inventory_extensions = legacy_norm
        if "analysis_extensions" in cj:
            analysis_extensions = _parse_ext_list(
                cj.get("analysis_extensions"), DEFAULT_ANALYSIS_EXTENSIONS
            )
            # Seeded MVP was FLAC-only; expand to FLAC+MP3 unless customized.
            if analysis_extensions == [".flac"]:
                analysis_extensions = list(DEFAULT_ANALYSIS_EXTENSIONS)
        else:
            analysis_extensions = list(DEFAULT_ANALYSIS_EXTENSIONS)
        retention = _int_cfg(cj.get("missing_retention_days", 90), 90, 1, 3650)
        mode = str(cj.get("provider_mode") or "triage")

        manager = get_database_manager()
        session = manager.get_library_audit_session_sync()
        try:
            summary = run_audit_cycle(
                session,
                root,
                triage_batch_size=triage_batch,
                deep_batch_size=deep_batch,
                inventory_interval_hours=inventory_hours,
                inventory_extensions=inventory_extensions,
                analysis_extensions=analysis_extensions,
                missing_retention_days=retention,
                provider_mode=mode,
                provider=provider,
                triage_sample_seconds=flac_options.triage_sample_seconds,
                deep_sample_seconds=flac_options.deep_sample_seconds,
                short_track_seconds=flac_options.short_track_seconds,
                require_deep_for_fake_certain=flac_options.require_deep_for_fake_certain,
                prefer_triage_first=prefer_triage_first,
                deep_after_triage_pct=deep_after_triage_pct,
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
                "triage": {
                    "attempted": summary.triage.attempted,
                    "completed": summary.triage.completed,
                },
                "deep": {
                    "attempted": summary.deep.attempted,
                    "completed": summary.deep.completed,
                    "fake_certain": summary.deep.fake_certain,
                    "skipped": summary.deep_skipped,
                    "skip_reason": summary.deep_skip_reason,
                },
                "triage_progress_pct": summary.triage_progress_pct,
                "prefer_triage_first": prefer_triage_first,
                "retention_deleted": summary.retention_deleted,
                "pending_queue": summary.pending_queue,
                "pending_deep": summary.pending_deep,
                "needs_review": summary.needs_review,
                "provider": health.provider,
                "provider_version": health.provider_version,
            }
            if inv is not None and inv.status == "FAILED":
                logger.error(f"Inventory failed: {inv.error_message}")
                return False
            deep_msg = (
                f"deep skipped ({summary.deep_skip_reason})"
                if summary.deep_skipped
                else f"deep {summary.deep.completed}/{summary.deep.attempted}"
            )
            logger.info(
                "Library Audit completed: "
                f"triage {summary.triage.completed}/{summary.triage.attempted}, "
                f"{deep_msg}, "
                f"triage_progress={summary.triage_progress_pct:.1f}%, "
                f"pending={summary.pending_queue}, pending_deep={summary.pending_deep}, "
                f"needs_review={summary.needs_review}"
            )
            return True
        except Exception as exc:
            logger.error(f"Library Audit failed: {exc}", exc_info=True)
            self.last_run_stats = {"error": str(exc)}
            return False
        finally:
            session.close()
