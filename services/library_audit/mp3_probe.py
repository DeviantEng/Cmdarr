#!/usr/bin/env python3
"""Mutagen-based MP3 probe analyzer for Library Audit."""

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

_PROVIDER_NAME = "mp3_probe"
_PROVIDER_VERSION = "1.0.0"

# Soft quality thresholds (kbps). Tunable later via command config.
_WARNING_BELOW_KBPS = 128
_SUSPICIOUS_BELOW_KBPS = 96


def _log():
    return get_logger("cmdarr.library_audit.mp3_probe")


def _bitrate_mode_name(mode: Any) -> str:
    try:
        from mutagen.mp3 import BitrateMode

        mapping = {
            BitrateMode.UNKNOWN: "UNKNOWN",
            BitrateMode.CBR: "CBR",
            BitrateMode.VBR: "VBR",
            BitrateMode.ABR: "ABR",
        }
        return mapping.get(mode, str(mode))
    except Exception:
        return str(mode)


class Mp3ProbeProvider:
    """Probe MP3 container/stream metadata (bitrate, CBR/VBR, basic tags)."""

    def health(self) -> ProviderHealth:
        try:
            from mutagen.mp3 import MP3  # noqa: F401

            return ProviderHealth(
                healthy=True,
                provider=_PROVIDER_NAME,
                provider_version=_PROVIDER_VERSION,
                message="MP3 probe (mutagen) available",
            )
        except Exception as exc:
            return ProviderHealth(
                healthy=False,
                provider=_PROVIDER_NAME,
                provider_version=_PROVIDER_VERSION,
                message=f"MP3 probe unavailable: {exc}",
            )

    def capabilities(self) -> ProviderCapabilities:
        return ProviderCapabilities(
            provider=_PROVIDER_NAME,
            modes=["standard"],
            extensions=[".mp3"],
            supports_spectrum=False,
            supports_spectrogram=False,
        )

    def analyze(self, absolute_path: str, mode: str = "standard") -> ProviderAnalysisResult:
        from mutagen.mp3 import MP3

        _ = mode
        path = Path(absolute_path)
        audio = MP3(path)
        info = audio.info
        if info is None:
            raise ValueError("MP3 has no stream info")

        bitrate = getattr(info, "bitrate", None)
        try:
            bitrate_kbps = int(round(float(bitrate) / 1000.0)) if bitrate else None
        except TypeError, ValueError:
            bitrate_kbps = None

        sample_rate = getattr(info, "sample_rate", None)
        try:
            sample_rate_i = int(sample_rate) if sample_rate else None
        except TypeError, ValueError:
            sample_rate_i = None

        channels = getattr(info, "channels", None)
        try:
            channels_i = int(channels) if channels is not None else None
        except TypeError, ValueError:
            channels_i = None

        length = getattr(info, "length", None)
        try:
            duration = float(length) if length is not None else None
        except TypeError, ValueError:
            duration = None

        bitrate_mode = _bitrate_mode_name(getattr(info, "bitrate_mode", None))
        layer = getattr(info, "layer", None)
        version = getattr(info, "version", None)
        encoder_info = getattr(info, "encoder_info", None) or getattr(
            info, "encoder_settings", None
        )

        tags = audio.tags
        title = artist = album = track_number = disc_number = None
        if tags is not None:

            def _first(*keys: str) -> str | None:
                for key in keys:
                    if key in tags:
                        val = tags.get(key)
                        if val is None:
                            continue
                        # mutagen frames often list-like
                        try:
                            text = val.text[0] if hasattr(val, "text") and val.text else str(val)
                        except Exception:
                            text = str(val)
                        text = str(text).strip()
                        if text:
                            return text
                return None

            title = _first("TIT2", "TITLE")
            artist = _first("TPE1", "ARTIST")
            album = _first("TALB", "ALBUM")
            track_number = _first("TRCK", "TRACKNUMBER")
            disc_number = _first("TPOS", "DISCNUMBER")

        verdict = "AUTHENTIC"
        summary_parts = []
        if bitrate_kbps is None:
            verdict = "INCONCLUSIVE"
            summary_parts.append("Could not determine MP3 bitrate")
        elif bitrate_kbps < _SUSPICIOUS_BELOW_KBPS:
            verdict = "SUSPICIOUS"
            summary_parts.append(f"Very low bitrate ({bitrate_kbps} kbps {bitrate_mode})")
        elif bitrate_kbps < _WARNING_BELOW_KBPS:
            verdict = "WARNING"
            summary_parts.append(f"Low bitrate ({bitrate_kbps} kbps {bitrate_mode})")
        else:
            summary_parts.append(f"{bitrate_kbps} kbps {bitrate_mode}")

        if sample_rate_i:
            summary_parts.append(f"{sample_rate_i} Hz")
        if channels_i:
            summary_parts.append(f"{channels_i}ch")

        evidence = to_jsonable(
            {
                "bitrate_kbps": bitrate_kbps,
                "bitrate_mode": bitrate_mode,
                "container_bitrate_kbps": bitrate_kbps,
                "estimated_mp3_bitrate": bitrate_kbps,
                "sample_rate": sample_rate_i,
                "channels": channels_i,
                "duration_seconds": duration,
                "mpeg_layer": layer,
                "mpeg_version": version,
                "encoder_info": str(encoder_info) if encoder_info else None,
                "warning_below_kbps": _WARNING_BELOW_KBPS,
                "suspicious_below_kbps": _SUSPICIOUS_BELOW_KBPS,
                "analysis_pass": (mode or "standard").lower(),
                "needs_deep": False,
                "integrity": {
                    "duration_mismatch": False,
                    "is_corrupted": False,
                    "duration_real": duration,
                    "duration_metadata": duration,
                },
            }
        )
        metadata = to_jsonable(
            {
                "sample_rate": sample_rate_i,
                "bits_per_sample": None,
                "channels": channels_i,
                "duration_seconds": duration,
                "filename": path.name,
                "title": title,
                "artist": artist,
                "album": album,
                "track_number": track_number,
                "disc_number": disc_number,
                "bitrate_kbps": bitrate_kbps,
                "bitrate_mode": bitrate_mode,
            }
        )
        raw = to_jsonable(
            {
                "bitrate": bitrate,
                "bitrate_kbps": bitrate_kbps,
                "bitrate_mode": bitrate_mode,
                "sample_rate": sample_rate_i,
                "channels": channels_i,
                "length": duration,
                "layer": layer,
                "version": version,
                "encoder_info": str(encoder_info) if encoder_info else None,
            }
        )

        return ProviderAnalysisResult(
            provider=_PROVIDER_NAME,
            provider_version=_PROVIDER_VERSION,
            provider_mode=mode or "standard",
            verdict=verdict,
            score=float(bitrate_kbps) if bitrate_kbps is not None else None,
            confidence=bitrate_mode,
            summary="; ".join(summary_parts),
            cutoff_hz=None,
            is_hires_suspect=None,
            evidence=evidence if isinstance(evidence, dict) else {},
            raw_result=raw if isinstance(raw, dict) else {},
            metadata=metadata if isinstance(metadata, dict) else {},
        )


def get_mp3_provider() -> Mp3ProbeProvider:
    return Mp3ProbeProvider()
