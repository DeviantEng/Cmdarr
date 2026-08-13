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
from services.library_audit.spectrum import compute_spectrum_curve
from utils.logger import get_logger

_logger = None
_PROVIDER_NAME = "flac_detective"

# Flagged verdicts trigger a deeper second pass + spectrum curve embedding.
_FLAGGED_VERDICTS = frozenset({"WARNING", "SUSPICIOUS", "FAKE_CERTAIN"})


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


def _as_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except TypeError, ValueError:
        return None


def _build_result(
    path: Path,
    raw: dict[str, Any],
    *,
    mode: str,
    analysis_pass: str,
    first_pass_verdict: str | None = None,
    first_pass_score: float | None = None,
    spectrum_curve: dict[str, Any] | None = None,
) -> ProviderAnalysisResult:
    verdict = str(raw.get("verdict") or "INCONCLUSIVE").upper()
    hires = raw.get("hires_verdict")
    is_hires_suspect = None
    if isinstance(hires, str):
        is_hires_suspect = hires.upper() in {
            "UPSAMPLED",
            "PADDED_DEPTH",
            "UPSAMPLED_AND_PADDED",
        }

    cutoff_f = _as_float(raw.get("cutoff_freq"))
    score_f = _as_float(raw.get("score"))
    residual = _as_float(raw.get("residual_floor_db"))

    evidence: dict[str, Any] = {
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
        "analysis_pass": analysis_pass,
        "residual_floor_db": residual,
    }
    if first_pass_verdict is not None:
        evidence["first_pass_verdict"] = first_pass_verdict
        evidence["first_pass_score"] = first_pass_score
    if spectrum_curve is not None:
        evidence["spectrum_curve"] = spectrum_curve

    evidence = to_jsonable(evidence)
    if not isinstance(evidence, dict):
        evidence = {}

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

    confidence = raw.get("confidence")
    if confidence is not None:
        confidence = str(confidence)

    summary = raw.get("reason") or raw.get("summary")
    if summary is not None:
        summary = str(summary)

    if first_pass_verdict and first_pass_verdict != verdict and summary is not None:
        summary = f"{summary} | Second pass: {first_pass_verdict} → {verdict}"
    elif first_pass_verdict and first_pass_verdict != verdict:
        summary = f"Second pass: {first_pass_verdict} → {verdict}"

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
        evidence=evidence,
        raw_result=raw if isinstance(raw, dict) else {},
        metadata=metadata if isinstance(metadata, dict) else {},
    )


def _run_analyzer(
    path: Path, *, sample_duration: float = 30.0, deep: bool = False
) -> dict[str, Any]:
    from flac_detective import FLACAnalyzer

    analyzer = FLACAnalyzer(sample_duration=sample_duration, deep=deep)
    raw_in: Any = analyzer.analyze_file(path)
    raw: dict[str, Any] = raw_in if isinstance(raw_in, dict) else {"result": raw_in}
    # FLAC Detective returns numpy scalars (e.g. bool_) that SQLite JSON cannot store.
    cleaned = to_jsonable(raw)
    return cleaned if isinstance(cleaned, dict) else {"result": raw_in}


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
            modes=["standard", "deep"],
            extensions=[".flac"],
            supports_spectrum=True,
            supports_spectrogram=False,
        )

    def analyze(self, absolute_path: str, mode: str = "standard") -> ProviderAnalysisResult:
        """Analyze a FLAC; flagged verdicts get a deeper second pass + spectrum curve.

        Note: FLAC Detective still short-circuits expensive R7/R9/R11 once score ≥ 86.
        ``deep=True`` mainly unlocks Rule 12 on the authentic fast path. The second pass
        still adds a longer sample, optional ML, and a spectrum curve for human review.
        """
        path = Path(absolute_path)
        _ = mode

        raw1 = _run_analyzer(path, sample_duration=30.0, deep=False)
        if not isinstance(raw1, dict):
            raw1 = {"result": raw1}
        verdict1 = str(raw1.get("verdict") or "INCONCLUSIVE").upper()
        score1 = _as_float(raw1.get("score"))

        if verdict1 not in _FLAGGED_VERDICTS:
            return _build_result(path, raw1, mode=mode or "standard", analysis_pass="standard")

        _log().info(f"Flagged {path.name} as {verdict1}; running deep second pass + spectrum curve")
        # Second pass: longer sample + deep (ML). Does not force expensive-rule skip past
        # FAKE_CERTAIN short-circuit — that requires upstream FLAC Detective changes.
        raw2 = _run_analyzer(path, sample_duration=60.0, deep=True)
        if not isinstance(raw2, dict):
            raw2 = raw1

        cutoff = _as_float(raw2.get("cutoff_freq"))
        if cutoff is None:
            cutoff = _as_float(raw1.get("cutoff_freq"))
        curve = compute_spectrum_curve(path, cutoff_hz=cutoff)

        return _build_result(
            path,
            raw2,
            mode="deep",
            analysis_pass="deep",
            first_pass_verdict=verdict1,
            first_pass_score=score1,
            spectrum_curve=curve,
        )


def get_default_provider() -> FlacDetectiveProvider:
    return FlacDetectiveProvider()
