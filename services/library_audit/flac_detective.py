#!/usr/bin/env python3
"""In-process FLAC Detective analyzer provider."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from services.library_audit.jsonutil import to_jsonable
from services.library_audit.provider import (
    ProviderAnalysisResult,
    ProviderCapabilities,
    ProviderHealth,
)
from utils.logger import get_logger

_logger = None
_PROVIDER_NAME = "flac_detective"


def _log():
    global _logger
    if _logger is None:
        _logger = get_logger("cmdarr.library_audit.flac_detective")
    return _logger


def _provider_version() -> str | None:
    try:
        from flac_detective import __version__

        return str(__version__)
    except Exception:
        try:
            import importlib.metadata

            return importlib.metadata.version("flac-detective")
        except Exception:
            return None


class FlacDetectiveProvider:
    """Wraps FLAC Detective's FLACAnalyzer behind the Library Audit provider contract."""

    def health(self) -> ProviderHealth:
        try:
            from flac_detective import FLACAnalyzer  # noqa: F401

            return ProviderHealth(
                healthy=True,
                provider=_PROVIDER_NAME,
                provider_version=_provider_version(),
                message="FLAC Detective available",
            )
        except Exception as exc:
            return ProviderHealth(
                healthy=False,
                provider=_PROVIDER_NAME,
                provider_version=_provider_version(),
                message=f"FLAC Detective unavailable: {exc}",
            )

    def capabilities(self) -> ProviderCapabilities:
        return ProviderCapabilities(
            provider=_PROVIDER_NAME,
            modes=["standard"],
            extensions=[".flac"],
            supports_spectrum=False,
            supports_spectrogram=False,
        )

    def analyze(self, absolute_path: str, mode: str = "standard") -> ProviderAnalysisResult:
        from flac_detective import FLACAnalyzer

        path = Path(absolute_path)
        analyzer = FLACAnalyzer()
        # Mode reserved for future deep/ML; MVP uses standard defaults.
        _ = mode
        raw_in: Any = analyzer.analyze_file(path)
        raw: dict[str, Any] = raw_in if isinstance(raw_in, dict) else {"result": raw_in}
        # FLAC Detective returns numpy scalars (e.g. bool_) that SQLite JSON cannot store.
        raw = to_jsonable(raw)

        verdict = str(raw.get("verdict") or "INCONCLUSIVE").upper()
        hires = raw.get("hires_verdict")
        is_hires_suspect = None
        if isinstance(hires, str):
            is_hires_suspect = hires.upper() in {
                "UPSAMPLED",
                "PADDED_DEPTH",
                "UPSAMPLED_AND_PADDED",
            }

        evidence = to_jsonable(
            {
                "cutoff_freq": raw.get("cutoff_freq"),
                "estimated_mp3_bitrate": raw.get("estimated_mp3_bitrate"),
                "has_clipping": raw.get("has_clipping"),
                "has_dc_offset": raw.get("has_dc_offset"),
                "is_corrupted": raw.get("is_corrupted"),
                "is_fake_high_res": raw.get("is_fake_high_res"),
                "is_upsampled": raw.get("is_upsampled"),
                "hires_verdict": hires,
                "hires_reason": raw.get("hires_reason"),
                "encoder": raw.get("encoder"),
                "partial_analysis": raw.get("partial_analysis") or raw.get("is_partial_analysis"),
            }
        )

        metadata = to_jsonable(
            {
                "sample_rate": raw.get("sample_rate"),
                "bits_per_sample": raw.get("bit_depth") or raw.get("bits_per_sample"),
                "channels": raw.get("channels"),
                "duration_seconds": raw.get("duration_real")
                or raw.get("duration_metadata")
                or raw.get("duration"),
                "filename": raw.get("filename") or path.name,
                "title": raw.get("title"),
                "artist": raw.get("artist"),
                "album": raw.get("album"),
                "track_number": raw.get("track_number") or raw.get("tracknumber"),
                "disc_number": raw.get("disc_number") or raw.get("discnumber"),
            }
        )

        score = raw.get("score")
        try:
            score_f = float(score) if score is not None else None
        except TypeError, ValueError:
            score_f = None

        cutoff = raw.get("cutoff_freq")
        try:
            cutoff_f = float(cutoff) if cutoff is not None else None
        except TypeError, ValueError:
            cutoff_f = None

        confidence = raw.get("confidence")
        if confidence is not None:
            confidence = str(confidence)

        summary = raw.get("reason") or raw.get("summary")
        if summary is not None:
            summary = str(summary)

        return ProviderAnalysisResult(
            provider=_PROVIDER_NAME,
            provider_version=_provider_version(),
            provider_mode=mode or "standard",
            verdict=verdict,
            score=score_f,
            confidence=confidence,
            summary=summary,
            cutoff_hz=cutoff_f,
            is_hires_suspect=is_hires_suspect,
            evidence=evidence if isinstance(evidence, dict) else {},
            raw_result=raw if isinstance(raw, dict) else {},
            metadata=metadata if isinstance(metadata, dict) else {},
        )


def get_default_provider() -> FlacDetectiveProvider:
    return FlacDetectiveProvider()
