#!/usr/bin/env python3
"""In-process FLAC Detective analyzer provider."""

from __future__ import annotations

from dataclasses import dataclass
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

# Flagged verdicts need deep confirmation before Fake Certain is user-facing.
_FLAGGED_VERDICTS = frozenset({"WARNING", "SUSPICIOUS", "FAKE_CERTAIN"})


@dataclass
class FlacAnalysisOptions:
    """Tunables for triage vs deep FLAC analysis."""

    triage_sample_seconds: float = 20.0
    deep_sample_seconds: float = 60.0
    short_track_seconds: float = 10.0
    require_deep_for_fake_certain: bool = True


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


def _duration_seconds(raw: dict[str, Any]) -> float | None:
    for key in ("duration_real", "duration_metadata", "duration"):
        val = _as_float(raw.get(key))
        if val is not None:
            return val
    return None


def _integrity_evidence(raw: dict[str, Any]) -> dict[str, Any]:
    meta = _as_float(raw.get("duration_metadata"))
    real = _as_float(raw.get("duration_real"))
    mismatch = False
    delta = None
    if meta is not None and real is not None and meta > 0:
        delta = abs(meta - real)
        # >2s or >5% — header vs decode disagreement
        mismatch = delta > 2.0 and delta > (0.05 * meta)
    return {
        "duration_metadata": meta,
        "duration_real": real,
        "duration_delta_seconds": delta,
        "duration_mismatch": mismatch,
        "is_corrupted": bool(raw.get("is_corrupted")),
    }


def _text_blob(raw: dict[str, Any]) -> str:
    parts: list[str] = []
    for key in ("reason", "summary", "details", "message"):
        val = raw.get(key)
        if val is not None:
            parts.append(str(val))
    return " ".join(parts).lower()


def _cassette_alone_without_transcode_support(raw: dict[str, Any]) -> bool:
    """True when cassette heuristics dominate without MP3/hard-cliff support.

    Addresses modern digital masters with cutoff < 19 kHz that trigger early R11.
    """
    text = _text_blob(raw)
    cassette = (
        "cassette" in text
        or bool(raw.get("is_cassette"))
        or bool(raw.get("cassette_detected"))
        or bool(raw.get("cassette_protection"))
    )
    if not cassette:
        return False
    has_mp3 = (
        raw.get("estimated_mp3_bitrate") is not None
        or "mp3" in text
        or "transcode" in text
        or "lame" in text
    )
    residual = _as_float(raw.get("residual_floor_db"))
    # Very low residual floor supports a hard digital cliff (transcode-like).
    hard_cliff = residual is not None and residual <= -60.0
    return cassette and not has_mp3 and not hard_cliff


def apply_fake_certain_policy(
    verdict: str,
    raw: dict[str, Any],
    *,
    analysis_pass: str,
    short_track_seconds: float,
    require_deep_for_fake_certain: bool,
) -> tuple[str, dict[str, Any]]:
    """Demote or gate Fake Certain so Phase-1 short-circuits are never user-facing."""
    extras: dict[str, Any] = {
        "fake_certain_promoted": False,
        "fake_certain_blocked_reason": None,
    }
    if verdict != "FAKE_CERTAIN":
        return verdict, extras

    duration = _duration_seconds(raw)
    if duration is not None and duration < short_track_seconds:
        extras["fake_certain_blocked_reason"] = "short_track"
        return "WARNING", extras

    if _cassette_alone_without_transcode_support(raw):
        extras["fake_certain_blocked_reason"] = "cassette_alone"
        return "WARNING", extras

    if analysis_pass != "deep":
        extras["fake_certain_blocked_reason"] = "requires_deep"
        return "WARNING", extras

    # Deep pass completed; promote only when policy allows Fake Certain at all.
    if not require_deep_for_fake_certain:
        # Operator disabled the deep gate — still apply short-track/cassette demotions above.
        extras["fake_certain_promoted"] = True
        return "FAKE_CERTAIN", extras

    extras["fake_certain_promoted"] = True
    return "FAKE_CERTAIN", extras


def _build_result(
    path: Path,
    raw: dict[str, Any],
    *,
    mode: str,
    analysis_pass: str,
    verdict_override: str | None = None,
    first_pass_verdict: str | None = None,
    first_pass_score: float | None = None,
    spectrum_curve: dict[str, Any] | None = None,
    evidence_extras: dict[str, Any] | None = None,
    needs_deep: bool = False,
) -> ProviderAnalysisResult:
    raw_verdict = str(raw.get("verdict") or "INCONCLUSIVE").upper()
    verdict = (verdict_override or raw_verdict).upper()
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
        "container_bitrate_kbps": raw.get("bitrate")
        or raw.get("container_bitrate")
        or raw.get("bitrate_kbps"),
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
        "integrity": _integrity_evidence(raw),
        "needs_deep": needs_deep,
        "triage_verdict": None,
        "deep_verdict": None,
    }
    if first_pass_verdict is not None:
        evidence["first_pass_verdict"] = first_pass_verdict
        evidence["first_pass_score"] = first_pass_score
        evidence["triage_verdict"] = first_pass_verdict
    if analysis_pass == "triage":
        evidence["triage_verdict"] = raw_verdict
    if analysis_pass == "deep":
        evidence["deep_verdict"] = raw_verdict
    if spectrum_curve is not None:
        evidence["spectrum_curve"] = spectrum_curve
    if evidence_extras:
        evidence.update(evidence_extras)

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

    blocked = evidence.get("fake_certain_blocked_reason")
    if blocked and verdict != "FAKE_CERTAIN":
        note = f"Fake Certain held ({blocked})"
        summary = f"{summary} | {note}" if summary else note

    if first_pass_verdict and first_pass_verdict != verdict and summary is not None:
        summary = f"{summary} | Deep pass: {first_pass_verdict} → {verdict}"
    elif first_pass_verdict and first_pass_verdict != verdict:
        summary = f"Deep pass: {first_pass_verdict} → {verdict}"

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

    def __init__(self, options: FlacAnalysisOptions | None = None):
        self.options = options or FlacAnalysisOptions()

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
            modes=["triage", "deep", "standard"],
            extensions=[".flac"],
            supports_spectrum=True,
            supports_spectrogram=False,
        )

    def analyze(self, absolute_path: str, mode: str = "standard") -> ProviderAnalysisResult:
        """Analyze a FLAC.

        Modes:
        - ``triage``: shorter sample, no spectrum; flagged → needs_deep (no Fake Certain).
        - ``deep`` / ``standard``: long sample + ML; Fake Certain only after promotion gate.
        """
        path = Path(absolute_path)
        mode_l = (mode or "standard").lower()
        if mode_l == "triage":
            return self._analyze_triage(path)
        return self._analyze_deep(path, mode=mode_l)

    def _analyze_triage(self, path: Path) -> ProviderAnalysisResult:
        opts = self.options
        sample = max(5.0, float(opts.triage_sample_seconds))
        raw = _run_analyzer(path, sample_duration=sample, deep=False)
        if not isinstance(raw, dict):
            raw = {"result": raw}
        raw_verdict = str(raw.get("verdict") or "INCONCLUSIVE").upper()

        if raw_verdict not in _FLAGGED_VERDICTS:
            return _build_result(
                path,
                raw,
                mode="triage",
                analysis_pass="triage",
                needs_deep=False,
            )

        # Never surface Fake Certain from triage — queue for deep.
        verdict, extras = apply_fake_certain_policy(
            raw_verdict,
            raw,
            analysis_pass="triage",
            short_track_seconds=opts.short_track_seconds,
            require_deep_for_fake_certain=True,
        )
        _log().info(
            f"Triage flagged {path.name} as {raw_verdict} → {verdict}; queuing deep analysis"
        )
        return _build_result(
            path,
            raw,
            mode="triage",
            analysis_pass="triage",
            verdict_override=verdict,
            evidence_extras=extras,
            needs_deep=True,
        )

    def _analyze_deep(self, path: Path, *, mode: str) -> ProviderAnalysisResult:
        opts = self.options
        sample = max(15.0, float(opts.deep_sample_seconds))
        raw = _run_analyzer(path, sample_duration=sample, deep=True)
        if not isinstance(raw, dict):
            raw = {"result": raw}
        raw_verdict = str(raw.get("verdict") or "INCONCLUSIVE").upper()
        score = _as_float(raw.get("score"))

        verdict, extras = apply_fake_certain_policy(
            raw_verdict,
            raw,
            analysis_pass="deep",
            short_track_seconds=opts.short_track_seconds,
            require_deep_for_fake_certain=opts.require_deep_for_fake_certain,
        )

        curve = None
        if verdict in _FLAGGED_VERDICTS or raw_verdict in _FLAGGED_VERDICTS:
            cutoff = _as_float(raw.get("cutoff_freq"))
            curve = compute_spectrum_curve(path, cutoff_hz=cutoff)

        return _build_result(
            path,
            raw,
            mode=mode if mode in {"deep", "standard"} else "deep",
            analysis_pass="deep",
            verdict_override=verdict,
            first_pass_verdict=None,
            first_pass_score=score,
            spectrum_curve=curve,
            evidence_extras=extras,
            needs_deep=False,
        )


def get_default_provider(
    options: FlacAnalysisOptions | None = None,
) -> FlacDetectiveProvider:
    return FlacDetectiveProvider(options=options)
