#!/usr/bin/env python3
"""Content hashing helpers for Library Audit."""

from __future__ import annotations

import hashlib
from pathlib import Path


def sha256_file(path: str | Path, chunk_size: int = 1024 * 1024) -> str:
    """Compute SHA-256 of a file's full contents."""
    digest = hashlib.sha256()
    with open(path, "rb") as fh:
        while True:
            chunk = fh.read(chunk_size)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()
