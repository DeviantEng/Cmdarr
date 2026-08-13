#!/usr/bin/env python3
"""Composite analyzer router: pick provider by file extension."""

from __future__ import annotations

from pathlib import Path

from services.library_audit.flac_detective import get_default_provider
from services.library_audit.mp3_probe import get_mp3_provider
from services.library_audit.provider import (
    AnalyzerProvider,
    ProviderAnalysisResult,
    ProviderCapabilities,
    ProviderHealth,
)


class CompositeAnalyzerProvider:
    """Routes analysis to the appropriate provider by extension."""

    def __init__(
        self,
        flac: AnalyzerProvider | None = None,
        mp3: AnalyzerProvider | None = None,
    ):
        self.flac = flac or get_default_provider()
        self.mp3 = mp3 or get_mp3_provider()

    def health(self) -> ProviderHealth:
        flac_h = self.flac.health()
        mp3_h = self.mp3.health()
        healthy = flac_h.healthy and mp3_h.healthy
        parts = []
        parts.append(
            f"flac_detective={'ok' if flac_h.healthy else 'down'}"
            + (f"@{flac_h.provider_version}" if flac_h.provider_version else "")
        )
        parts.append(
            f"mp3_probe={'ok' if mp3_h.healthy else 'down'}"
            + (f"@{mp3_h.provider_version}" if mp3_h.provider_version else "")
        )
        return ProviderHealth(
            healthy=healthy,
            provider="composite",
            provider_version=None,
            message=", ".join(parts),
            details={
                "flac_detective": {
                    "healthy": flac_h.healthy,
                    "version": flac_h.provider_version,
                    "message": flac_h.message,
                },
                "mp3_probe": {
                    "healthy": mp3_h.healthy,
                    "version": mp3_h.provider_version,
                    "message": mp3_h.message,
                },
            },
        )

    def capabilities(self) -> ProviderCapabilities:
        flac_caps = self.flac.capabilities()
        return ProviderCapabilities(
            provider="composite",
            modes=["standard", "deep"],
            extensions=[".flac", ".mp3"],
            supports_spectrum=bool(flac_caps.supports_spectrum),
            supports_spectrogram=False,
        )

    def provider_for_path(self, absolute_path: str) -> AnalyzerProvider:
        ext = Path(absolute_path).suffix.lower()
        if ext == ".mp3":
            return self.mp3
        if ext == ".flac":
            return self.flac
        raise ValueError(f"No analyzer registered for extension {ext or '(none)'}")

    def analyze(self, absolute_path: str, mode: str = "standard") -> ProviderAnalysisResult:
        return self.provider_for_path(absolute_path).analyze(absolute_path, mode=mode)


def get_composite_provider() -> CompositeAnalyzerProvider:
    return CompositeAnalyzerProvider()
