#!/usr/bin/env python3
"""Path safety helpers for Library Audit."""

from __future__ import annotations

from pathlib import Path


class UnsafePathError(ValueError):
    """Raised when a relative path escapes the configured music root."""


def resolve_under_root(root: str | Path, relative_path: str) -> Path:
    """Resolve relative_path under root; reject absolute paths, .., and symlink escapes."""
    if not relative_path or relative_path.strip() == "":
        raise UnsafePathError("empty relative path")
    # Normalize separators but reject absolute / drive paths and .. segments early
    candidate = relative_path.replace("\\", "/")
    if candidate.startswith("/") or candidate.startswith("~"):
        raise UnsafePathError("absolute paths are not allowed")
    if Path(candidate).is_absolute():
        raise UnsafePathError("absolute paths are not allowed")
    parts = Path(candidate).parts
    if any(p == ".." for p in parts):
        raise UnsafePathError("path traversal is not allowed")

    root_path = Path(root).resolve()
    full = (root_path / candidate).resolve()
    try:
        full.relative_to(root_path)
    except ValueError as exc:
        raise UnsafePathError("path escapes configured root") from exc
    return full


def to_relative_posix(root: str | Path, absolute_path: str | Path) -> str:
    root_path = Path(root).resolve()
    abs_path = Path(absolute_path).resolve()
    return abs_path.relative_to(root_path).as_posix()
