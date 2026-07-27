"""In-memory Similarr interactive similar-artist discovery sessions."""

from __future__ import annotations

import asyncio
import logging
import time
import uuid
from dataclasses import dataclass, field
from typing import Any

from clients.client_deezer import DeezerClient
from clients.client_lastfm import LastFMClient
from clients.client_lidarr import LidarrClient
from commands.config_adapter import ConfigAdapter
from utils.discovery import DiscoveryUtils

logger = logging.getLogger("cmdarr.similarr")

# Per-seed Last.fm similar fetch size (discovery_lastfm uses a tiny default).
_SIMILAR_PER_SEED = 50
# Hard failsafe only — not a user-facing setting. One-shot jobs normally finish far sooner.
_SESSION_FAILSAFE_SECONDS = 600.0
_DEEZER_IMAGE_CONCURRENCY = 5


@dataclass
class SimilarrResult:
    mbid: str
    name: str
    match_score: float
    seed_count: int
    seed_names: list[str]
    url: str = ""
    image_url: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "mbid": self.mbid,
            "name": self.name,
            "match_score": self.match_score,
            "seed_count": self.seed_count,
            "seed_names": list(self.seed_names),
            "url": self.url,
            "image_url": self.image_url,
        }


@dataclass
class SimilarrSession:
    session_id: str
    seeds: list[dict[str, str]]  # {mbid, name}
    status: str = "running"  # running | completed | stopped | timed_out | error
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
        """One-shot: query each selected seed once, then complete."""
        try:
            await asyncio.wait_for(
                self._run_one_shot(session),
                timeout=_SESSION_FAILSAFE_SECONDS,
            )
        except TimeoutError:
            if session.status == "running":
                session.status = "timed_out"
                session.error = (
                    f"Search exceeded internal failsafe ({int(_SESSION_FAILSAFE_SECONDS)}s)"
                )
        except asyncio.CancelledError:
            session.status = "stopped"
            raise
        except Exception as e:
            logger.exception("Similarr session failed: %s", e)
            session.status = "error"
            session.error = str(e)

    async def _fill_missing_images(self, session: SimilarrSession, config) -> None:
        missing = [r for r in session.results.values() if not r.image_url]
        if not missing:
            return

        sem = asyncio.Semaphore(_DEEZER_IMAGE_CONCURRENCY)

        async with DeezerClient(config) as deezer:

            async def _one(result: SimilarrResult) -> None:
                if session.stop_requested:
                    return
                async with sem:
                    try:
                        res = await deezer.search_artists(result.name, limit=1)
                        artists = res.get("artists") or []
                        if artists:
                            image_url = (artists[0].get("image_url") or "").strip()
                            if image_url:
                                result.image_url = image_url
                    except Exception as e:
                        logger.debug("Deezer image lookup failed for %s: %s", result.name, e)

            await asyncio.gather(*[_one(r) for r in missing])

    async def _run_one_shot(self, session: SimilarrSession) -> None:
        config = ConfigAdapter()

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

            for seed in session.seeds:
                if session.stop_requested:
                    session.status = "stopped"
                    return

                try:
                    similar, _skipped = await lastfm.get_similar_artists(
                        mbid=seed["mbid"],
                        artist_name=seed["name"],
                        limit=_SIMILAR_PER_SEED,
                        include_similar_without_mbid=False,
                    )
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

                    mbid = (row.get("mbid") or "").strip()
                    name = (row.get("name") or "").strip()
                    if not mbid or not name:
                        continue

                    try:
                        match_score = float(row.get("match") or 0)
                    except TypeError, ValueError:
                        match_score = 0.0

                    image_url = (row.get("image_url") or "").strip() or None

                    if mbid in session.results:
                        existing = session.results[mbid]
                        if seed["name"] not in existing.seed_names:
                            existing.seed_names.append(seed["name"])
                            existing.seed_count = len(existing.seed_names)
                        if match_score > existing.match_score:
                            existing.match_score = match_score
                        if image_url and not existing.image_url:
                            existing.image_url = image_url
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
                        image_url=image_url,
                    )
                    session.result_order.append(mbid)
                    existing_mbids.add(mbid)
                    existing_names.add(name.lower())

            if session.stop_requested:
                session.status = "stopped"
                return

            await self._fill_missing_images(session, config)

            if session.stop_requested:
                session.status = "stopped"
            else:
                session.status = "completed"


similarr_service = SimilarrService()
