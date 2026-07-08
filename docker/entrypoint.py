#!/usr/bin/env python3
"""Container entrypoint for Wolfi/distroless images (replaces entrypoint.sh)."""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path


def log(message: str) -> None:
    print(f"[entrypoint] {message}", flush=True)


def _validate_config_from_database() -> tuple[bool, str]:
    project_root = Path("/app")
    sys.path.insert(0, str(project_root))

    from utils.logger import CmdarrLogger

    class MinimalConfig:
        LOG_LEVEL = "INFO"
        LOG_FILE = "/app/data/logs/cmdarr.log"
        LOG_RETENTION_DAYS = 7

    CmdarrLogger.setup_logging(MinimalConfig())

    from services.config_service import config_service

    try:
        missing = config_service.validate_required_settings()
        if not missing:
            return True, "Configuration is ready"
        return False, f"Missing required settings: {missing}"
    except Exception as exc:
        return False, f"Error checking configuration: {exc}"


def check_config_ready() -> bool:
    if os.environ.get("LIDARR_API_KEY") and os.environ.get("LASTFM_API_KEY"):
        log("Required environment variables detected, configuration ready")
        return True

    db_path = Path("/app/data/cmdarr.db")
    if db_path.is_file():
        log("Database exists, checking configuration...")
        ready, message = _validate_config_from_database()
        log(message)
        return ready

    return False


def wait_for_config() -> None:
    max_attempts = 5
    for attempt in range(1, max_attempts + 1):
        log(f"Checking configuration readiness (attempt {attempt}/{max_attempts})...")
        if check_config_ready():
            log("Configuration is ready, starting application...")
            return

        if attempt == 1:
            log("Configuration not ready. Please either:")
            log("  1. Set environment variables: LIDARR_API_KEY, LASTFM_API_KEY, etc.")
            log("  2. Access the web interface at http://localhost:8080/config to configure")
            log("")
            log("Will check again in 60 seconds...")
        else:
            log(
                f"Configuration still not ready, waiting 60 seconds... "
                f"(attempt {attempt}/{max_attempts})"
            )
        time.sleep(60)

    log(f"Configuration not ready after {max_attempts} attempts.")
    log("Container will continue checking every 60 seconds.")
    log("Set environment variables or access the web interface to configure.")

    while True:
        time.sleep(60)
        if check_config_ready():
            log("Configuration is now ready, starting application...")
            return
        log("Still waiting for configuration... (checking every 60 seconds)")


def _chown_tree(path: Path, uid: int, gid: int) -> None:
    if not path.exists():
        return
    os.chown(path, uid, gid)
    if not path.is_dir():
        return
    for root, dirs, files in os.walk(path):
        os.chown(root, uid, gid)
        for name in dirs:
            os.chown(os.path.join(root, name), uid, gid)
        for name in files:
            os.chown(os.path.join(root, name), uid, gid)


def adjust_ownership(puid: int, pgid: int) -> None:
    if puid == 1000 and pgid == 1000:
        log("Using default UID:GID (1000:1000)")
        return

    log(f"Setting ownership for UID:{puid} GID:{pgid}")
    log("Updating file ownership...")
    _chown_tree(Path("/app/data"), puid, pgid)
    if os.stat("/app").st_uid != puid:
        os.chown("/app", puid, pgid)


def main() -> None:
    puid = int(os.environ.get("PUID", "1000"))
    pgid = int(os.environ.get("PGID", "1000"))

    adjust_ownership(puid, pgid)
    wait_for_config()

    cmd = sys.argv[1:] if len(sys.argv) > 1 else ["python", "run_fastapi.py"]
    log(f"Starting application as UID:{puid} GID:{pgid}")
    os.execvp("/usr/bin/gosu", ["gosu", f"{puid}:{pgid}", *cmd])


if __name__ == "__main__":
    main()
