#!/usr/bin/env python3
"""Library Audit services package."""

__all__ = [
    "FlacDetectiveProvider",
    "get_default_provider",
    "run_audit_cycle",
]


def __getattr__(name: str):
    if name in {"FlacDetectiveProvider", "get_default_provider"}:
        from services.library_audit.flac_detective import (
            FlacDetectiveProvider,
            get_default_provider,
        )

        return {
            "FlacDetectiveProvider": FlacDetectiveProvider,
            "get_default_provider": get_default_provider,
        }[name]
    if name == "run_audit_cycle":
        from services.library_audit.service import run_audit_cycle

        return run_audit_cycle
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
