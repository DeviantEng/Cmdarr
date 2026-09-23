#!/usr/bin/env python3
"""Library Audit analyzer provider protocol and result types."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol

NORMALIZED_VERDICTS = frozenset(
    {
        "AUTHENTIC",
        "WARNING",
        "SUSPICIOUS",
        "FAKE_CERTAIN",
        "INCONCLUSIVE",
        "ERROR",
    }
)

REVIEW_THRESHOLD_ORDER = {
    "AUTHENTIC": 0,
    "WARNING": 1,
    "SUSPICIOUS": 2,
    "FAKE_CERTAIN": 3,
    "INCONCLUSIVE": 1,
    "ERROR": 1,
}


@dataclass
class ProviderHealth:
    healthy: bool
    provider: str
    provider_version: str | None = None
    message: str | None = None
    details: dict[str, Any] = field(default_factory=dict)


@dataclass
class ProviderCapabilities:
    provider: str
    modes: list[str] = field(default_factory=lambda: ["standard"])
    extensions: list[str] = field(default_factory=lambda: [".flac"])
    supports_spectrum: bool = False
    supports_spectrogram: bool = False


@dataclass
class ProviderAnalysisResult:
    provider: str
    verdict: str
    provider_version: str | None = None
    provider_mode: str | None = None
    score: float | None = None
    confidence: str | None = None
    summary: str | None = None
    cutoff_hz: float | None = None
    is_hires_suspect: bool | None = None
    evidence: dict[str, Any] = field(default_factory=dict)
    raw_result: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)

    def normalized_verdict(self) -> str:
        v = (self.verdict or "INCONCLUSIVE").upper()
        if v not in NORMALIZED_VERDICTS:
            return "INCONCLUSIVE"
        return v


class AnalyzerProvider(Protocol):
    def health(self) -> ProviderHealth: ...

    def capabilities(self) -> ProviderCapabilities: ...

    def analyze(self, absolute_path: str, mode: str = "standard") -> ProviderAnalysisResult: ...
