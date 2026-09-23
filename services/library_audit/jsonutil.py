#!/usr/bin/env python3
"""JSON-safe conversion for Library Audit persistence."""

from __future__ import annotations

from typing import Any


def to_jsonable(value: Any) -> Any:
    """Convert provider results (incl. numpy scalars) into JSON-serializable values."""
    if value is None or isinstance(value, (str, int, float, bool)):
        return value

    # numpy scalars / bool_ expose item()
    item = getattr(value, "item", None)
    if callable(item):
        try:
            return to_jsonable(item())
        except Exception:
            pass

    if isinstance(value, dict):
        return {str(k): to_jsonable(v) for k, v in value.items()}

    if isinstance(value, (list, tuple, set)):
        return [to_jsonable(v) for v in value]

    # numpy arrays
    tolist = getattr(value, "tolist", None)
    if callable(tolist):
        try:
            return to_jsonable(tolist())
        except Exception:
            pass

    # Fallback: stringify unknown objects rather than failing the whole analysis
    return str(value)
