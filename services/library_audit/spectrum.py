#!/usr/bin/env python3
"""Magnitude spectrum curve helper for Library Audit (JSON points, no image files)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from services.library_audit.jsonutil import to_jsonable
from utils.logger import get_logger

_CURVE_SECONDS = 10.0
_CURVE_POINTS = 256
_DB_FLOOR = -80.0


def _log():
    return get_logger("cmdarr.library_audit.spectrum")


def compute_spectrum_curve(
    absolute_path: str | Path,
    cutoff_hz: float | None = None,
) -> dict[str, Any] | None:
    """Compute a downsampled, peak-normalised magnitude spectrum for UI SVG rendering.

    Same approach as FLAC Detective's HTML report curve: middle segment, Hann window,
    rfft → dB, max-per-bin downsample, peak-normalise. Returns JSON-safe floats or None.
    """
    path = Path(absolute_path)
    if not path.is_file():
        return None
    try:
        import numpy as np
        import soundfile as sf

        info = sf.info(str(path))
        sr = int(info.samplerate)
        total_frames = int(info.frames)
        if sr <= 0 or total_frames <= 0:
            return None

        seg_frames = min(int(_CURVE_SECONDS * sr), total_frames)
        start = max(0, (total_frames - seg_frames) // 2)
        data, sr = sf.read(str(path), start=start, frames=seg_frames, always_2d=True)
        if data.size == 0:
            return None

        mono = data.mean(axis=1)
        window = np.hanning(len(mono))
        mag = np.abs(np.fft.rfft(mono * window))
        freqs = np.fft.rfftfreq(len(mono), 1.0 / sr)
        mag_db = 20.0 * np.log10(mag + 1e-10)

        n = min(_CURVE_POINTS, len(mag_db))
        if n < 2:
            return None
        idx = np.linspace(0, len(mag_db), n + 1).astype(int)
        ds_db = np.array([mag_db[idx[i] : max(idx[i] + 1, idx[i + 1])].max() for i in range(n)])
        ds_freq = np.array([float(freqs[min(idx[i], len(freqs) - 1)]) for i in range(n)])

        peak = float(ds_db.max())
        norm = (ds_db - peak - _DB_FLOOR) / (-_DB_FLOOR)
        norm = np.clip(norm, 0.0, 1.0)

        cutoff_f: float | None
        try:
            cutoff_f = float(cutoff_hz) if cutoff_hz is not None else None
        except TypeError, ValueError:
            cutoff_f = None

        payload = {
            "freqs_hz": [float(x) for x in ds_freq.tolist()],
            "norm": [float(x) for x in norm.tolist()],
            "nyquist_hz": float(sr) / 2.0,
            "cutoff_hz": cutoff_f,
            "segment_seconds": float(seg_frames) / float(sr),
        }
        out = to_jsonable(payload)
        return out if isinstance(out, dict) else None
    except Exception as exc:
        _log().debug(f"Spectrum curve unavailable for {path}: {exc}")
        return None
