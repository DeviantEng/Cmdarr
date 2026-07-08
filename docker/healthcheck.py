#!/usr/bin/env python3
"""Probe /health for Docker HEALTHCHECK (stdlib only — no curl binary required)."""
import sys
import urllib.error
import urllib.request

HEALTH_URL = "http://127.0.0.1:8080/health"
TIMEOUT_SEC = 8


def main() -> int:
    try:
        with urllib.request.urlopen(HEALTH_URL, timeout=TIMEOUT_SEC) as resp:
            return 0 if resp.status == 200 else 1
    except (urllib.error.URLError, OSError, TimeoutError):
        return 1


if __name__ == "__main__":
    sys.exit(main())
