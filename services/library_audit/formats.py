#!/usr/bin/env python3
"""Audio format helpers for Library Audit inventory."""

from __future__ import annotations

# Inventory covers common audio containers. Analysis is separate per extension.
# Non-audio sidecars (.jpg, .nfo, .cue, …) are never inventoried.
DEFAULT_INVENTORY_EXTENSIONS = [
    ".flac",
    ".wav",
    ".aiff",
    ".aif",
    ".alac",
    ".m4a",
    ".ape",
    ".wv",
    ".dsf",
    ".dff",
    ".mp3",
    ".aac",
    ".ogg",
    ".opus",
    ".wma",
    ".m4b",
    # Additional lossless / lossy audio often found in libraries
    ".tak",
    ".mpc",
    ".mp2",
    ".ac3",
    ".dts",
    ".mka",
    ".webm",
    ".oga",
]

# MVP analyzers: FLAC Detective (authenticity) + mutagen MP3 probe (bitrate/CBR-VBR)
DEFAULT_ANALYSIS_EXTENSIONS = [".flac", ".mp3"]

LOSSLESS_EXTENSIONS = frozenset(
    {
        ".flac",
        ".wav",
        ".aiff",
        ".aif",
        ".alac",
        ".ape",
        ".wv",
        ".dsf",
        ".dff",
        ".tak",
    }
)

LOSSY_EXTENSIONS = frozenset(
    {
        ".mp3",
        ".aac",
        ".ogg",
        ".opus",
        ".wma",
        ".m4b",
        ".mpc",
        ".mp2",
        ".ac3",
        ".dts",
        ".webm",
        ".oga",
    }
)

# .m4a / .mka can be ALAC or AAC / various codecs — treat as unknown without probing
UNKNOWN_EXTENSIONS = frozenset({".m4a", ".mka"})


def normalize_extensions(extensions: list[str] | None, fallback: list[str]) -> list[str]:
    if not extensions:
        return list(fallback)
    out: list[str] = []
    seen: set[str] = set()
    for ext in extensions:
        e = str(ext).lower().strip()
        if not e:
            continue
        if not e.startswith("."):
            e = f".{e}"
        if e not in seen:
            seen.add(e)
            out.append(e)
    return out or list(fallback)


def format_kind_for_extension(extension: str | None) -> str:
    ext = (extension or "").lower()
    if not ext.startswith(".") and ext:
        ext = f".{ext}"
    if ext in LOSSLESS_EXTENSIONS:
        return "lossless"
    if ext in LOSSY_EXTENSIONS:
        return "lossy"
    if ext in UNKNOWN_EXTENSIONS:
        return "unknown"
    return "unknown"


def is_analyzable_extension(extension: str | None, analysis_extensions: list[str]) -> bool:
    ext = (extension or "").lower()
    if ext and not ext.startswith("."):
        ext = f".{ext}"
    return ext in {e.lower() for e in analysis_extensions}
