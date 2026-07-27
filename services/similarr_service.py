"""In-memory Similarr interactive similar-artist discovery sessions."""

from __future__ import annotations

import asyncio
import logging
import time
import uuid
from dataclasses import dataclass, field
from typing import Any

from clients.client_lastfm import LastFMClient
from clients.client_lidarr import LidarrClient
from commands.config_adapter import ConfigAdapter
from utils.discovery import DiscoveryUtils

logger = logging.getLogger("cmdarr.similarr")

# Per-seed Last.fm similar fetch size (discovery_lastfm uses a tiny default).
_SIMILAR_PER_SEED = 50


@dataclass
class SimilarrResult:
    mbid: str
    name: str
    match_score: float
    seed_count: int
    seed_names: list[str]
    url: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "mbid": self.mbid,
            "name": self.name,
            "match_score": self.match_score,
            "seed_count": self.seed_count,
            "seed_names": list(self.seed_names),
            "url": self.url,
        }


@dataclass
class SimilarrSession:
    session_id: str
    seeds: list[dict[str, str]]  # {mbid, name}
    status: str = "running"  # running | stopped | timed_out | exhausted | error
    started_at: float = field(default_factory=time.monotonic)
    error: str | None = None
    results: dict[str, SimilarrResult] = field(default_factory=dict)
    result_order: list[str] = field(default_factory=list)
    stop_requested: bool = False
    task: asyncio.Task | None = None

    def elapsed_seconds(self) -> float:
        return max(0.0, time.monotonic() - self.started_at)

    def to_dict(self) -> dict[str, Any]:
        return {
            "session_id": self.session_id,
            "status": self.status,
            "elapsed_seconds": round(self.elapsed_seconds(), 1),
            "seed_count": len(self.seeds),
            "result_count": len(self.result_order),
            "results": [self.results[k].to_dict() for k in self.result_order if k in self.results],
            "error": self.error,
        }


class SimilarrService:
    """Single active interactive discovery session per process."""

    def __init__(self) -> None:
        self._lock = asyncio.Lock()
        self._session: SimilarrSession | None = None

    def get_session(self, session_id: str | None = None) -> SimilarrSession | None:
        if self._session is None:
            return None
        if session_id is not None and self._session.session_id != session_id:
            return None
        return self._session

    async def start_session(self, seeds: list[dict[str, str]]) -> SimilarrSession:
        cleaned: list[dict[str, str]] = []
        seen: set[str] = set()
        for s in seeds:
            mbid = (s.get("mbid") or "").strip()
            name = (s.get("name") or "").strip()
            if not mbid or mbid in seen:
                continue
            seen.add(mbid)
            cleaned.append({"mbid": mbid, "name": name or mbid})

        if not cleaned:
            raise ValueError("At least one seed artist with an MBID is required")

        async with self._lock:
            if self._session and self._session.status == "running":
                raise RuntimeError("A Similarr search is already running")

            session = SimilarrSession(session_id=str(uuid.uuid4()), seeds=cleaned)
            self._session = session
            session.task = asyncio.create_task(
                self._run_session(session), name=f"similarr-{session.session_id}"
            )
            return session

    async def stop_session(self, session_id: str) -> SimilarrSession:
        async with self._lock:
            session = self._session
            if session is None or session.session_id != session_id:
                raise KeyError("Session not found")
            if session.status == "running":
                session.stop_requested = True
            return session

    async def _run_session(self, session: SimilarrSession) -> None:
        config = ConfigAdapter()
        timeout = float(config.SIMILARR_SEARCH_TIMEOUT_SECONDS)

        try:
            async with LidarrClient(config) as lidarr, LastFMClient(config) as lastfm:
                discovery = DiscoveryUtils(config, lidarr)
                (
                    existing_mbids,
                    existing_names,
                    excluded_mbids,
                ) = await discovery.get_lidarr_context()
                # Never recommend the seeds themselves.
                for seed in session.seeds:
                    existing_mbids.add(seed["mbid"])
                    existing_names.add(seed["name"].lower())

                while True:
                    if session.stop_requested:
                        session.status = "stopped"
                        return
                    if session.elapsed_seconds() >= timeout:
                        session.status = "timed_out"
                        return

                    found_this_pass = 0
                    for seed in session.seeds:
                        if session.stop_requested:
                            session.status = "stopped"
                            return
                        if session.elapsed_seconds() >= timeout:
                            session.status = "timed_out"
                            return

                        remaining = timeout - session.elapsed_seconds()
                        if remaining <= 0:
                            session.status = "timed_out"
                            return

                        try:
                            similar, _skipped = await asyncio.wait_for(
                                lastfm.get_similar_artists(
                                    mbid=seed["mbid"],
                                    artist_name=seed["name"],
                                    limit=_SIMILAR_PER_SEED,
                                    include_similar_without_mbid=False,
                                ),
                                timeout=max(1.0, remaining),
                            )
                        except TimeoutError:
                            session.status = "timed_out"
                            return
                        except Exception as e:
                            logger.warning(
                                "Similarr similar lookup failed for %s: %s",
                                seed["name"],
                                e,
                            )
                            continue

                        for row in similar:
                            if session.stop_requested:
                                session.status = "stopped"
                                return
                            if session.elapsed_seconds() >= timeout:
                                session.status = "timed_out"
                                return

                            mbid = (row.get("mbid") or "").strip()
                            name = (row.get("name") or "").strip()
                            if not mbid or not name:
                                continue

                            try:
                                match_score = float(row.get("match") or 0)
                            except TypeError, ValueError:
                                match_score = 0.0

                            if mbid in session.results:
                                existing = session.results[mbid]
                                if seed["name"] not in existing.seed_names:
                                    existing.seed_names.append(seed["name"])
                                    existing.seed_count = len(existing.seed_names)
                                if match_score > existing.match_score:
                                    existing.match_score = match_score
                                continue

                            ok, _reason = discovery.filter_artist_candidate(
                                mbid,
                                name,
                                existing_mbids,
                                existing_names,
                                excluded_mbids,
                            )
                            if not ok:
                                continue

                            session.results[mbid] = SimilarrResult(
                                mbid=mbid,
                                name=name,
                                match_score=match_score,
                                seed_count=1,
                                seed_names=[seed["name"]],
                                url=(row.get("url") or ""),
                            )
                            session.result_order.append(mbid)
                            # Prevent re-adding if later seeds suggest same name/mbid.
                            existing_mbids.add(mbid)
                            existing_names.add(name.lower())
                            found_this_pass += 1

                    if found_this_pass == 0:
                        session.status = "exhausted"
                        return

        except asyncio.CancelledError:
            session.status = "stopped"
            raise
        except Exception as e:
            logger.exception("Similarr session failed: %s", e)
            session.status = "error"
            session.error = str(e)


similarr_service = SimilarrService()
