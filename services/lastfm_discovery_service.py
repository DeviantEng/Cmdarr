"""In-memory Last.fm Discovery interactive similar-artist discovery sessions."""

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

logger = logging.getLogger("cmdarr.discovery.lastfm")

# Per-seed Last.fm similar fetch size (discovery_lastfm uses a tiny default).
_SIMILAR_PER_SEED = 50
# Hard failsafe only — not a user-facing setting. One-shot jobs normally finish far sooner.
_SESSION_FAILSAFE_SECONDS = 600.0
_DEEZER_IMAGE_CONCURRENCY = 5
_DEFAULT_BATCH_SIZE = 12


def _as_optional_int(value: Any) -> int | None:
    if value is None or value == "":
        return None
    try:
        return int(value)
    except TypeError, ValueError:
        return None


def _clamp_min_match_score(value: float | None) -> float:
    try:
        score = float(value if value is not None else 0.0)
    except TypeError, ValueError:
        score = 0.0
    return max(0.0, min(1.0, score))


@dataclass
class LastfmDiscoveryResult:
    mbid: str
    name: str
    match_score: float
    seed_count: int
    seed_names: list[str]
    url: str = ""
    image_url: str | None = None
    listeners: int | None = None
    playcount: int | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "mbid": self.mbid,
            "name": self.name,
            "match_score": self.match_score,
            "seed_count": self.seed_count,
            "seed_names": list(self.seed_names),
            "url": self.url,
            "image_url": self.image_url,
            "listeners": self.listeners,
            "playcount": self.playcount,
        }


@dataclass
class LastfmDiscoverySession:
    session_id: str
    seeds: list[dict[str, str]]  # {mbid, name}
    status: str = "running"  # running | completed | stopped | timed_out | error
    started_at: float = field(default_factory=time.monotonic)
    error: str | None = None
    results: dict[str, LastfmDiscoveryResult] = field(default_factory=dict)
    candidate_order: list[str] = field(default_factory=list)
    visible_count: int = 0
    min_match_score: float = 0.0
    batch_size: int = _DEFAULT_BATCH_SIZE
    stop_requested: bool = False
    task: asyncio.Task | None = None

    def elapsed_seconds(self) -> float:
        return max(0.0, time.monotonic() - self.started_at)

    @property
    def has_more(self) -> bool:
        return self.visible_count < len(self.candidate_order)

    def visible_results(self) -> list[LastfmDiscoveryResult]:
        out: list[LastfmDiscoveryResult] = []
        for mbid in self.candidate_order[: self.visible_count]:
            result = self.results.get(mbid)
            if result is not None:
                out.append(result)
        return out

    def to_dict(self) -> dict[str, Any]:
        # While collecting, do not stream unsorted partial results.
        results = self.visible_results() if self.status != "running" else []
        return {
            "session_id": self.session_id,
            "status": self.status,
            "elapsed_seconds": round(self.elapsed_seconds(), 1),
            "seed_count": len(self.seeds),
            "result_count": len(self.candidate_order),
            "visible_count": 0 if self.status == "running" else self.visible_count,
            "has_more": False if self.status == "running" else self.has_more,
            "min_match_score": self.min_match_score,
            "batch_size": self.batch_size,
            "results": [r.to_dict() for r in results],
            "error": self.error,
        }


class LastfmDiscoveryService:
    """Single active interactive discovery session per process."""

    def __init__(self) -> None:
        self._lock = asyncio.Lock()
        self._session: LastfmDiscoverySession | None = None

    def get_session(self, session_id: str | None = None) -> LastfmDiscoverySession | None:
        if self._session is None:
            return None
        if session_id is not None and self._session.session_id != session_id:
            return None
        return self._session

    async def start_session(
        self,
        seeds: list[dict[str, str]],
        min_match_score: float = 0.0,
        batch_size: int = _DEFAULT_BATCH_SIZE,
    ) -> LastfmDiscoverySession:
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

        score = _clamp_min_match_score(min_match_score)
        try:
            size = int(batch_size)
        except TypeError, ValueError:
            size = _DEFAULT_BATCH_SIZE
        size = max(1, min(100, size))

        async with self._lock:
            if self._session and self._session.status == "running":
                raise RuntimeError("A Last.fm Discovery search is already running")

            session = LastfmDiscoverySession(
                session_id=str(uuid.uuid4()),
                seeds=cleaned,
                min_match_score=score,
                batch_size=size,
            )
            self._session = session
            session.task = asyncio.create_task(
                self._run_session(session), name=f"lastfm-discovery-{session.session_id}"
            )
            return session

    async def stop_session(self, session_id: str) -> LastfmDiscoverySession:
        async with self._lock:
            session = self._session
            if session is None or session.session_id != session_id:
                raise KeyError("Session not found")
            if session.status == "running":
                session.stop_requested = True
            return session

    async def load_more(self, session_id: str) -> LastfmDiscoverySession:
        async with self._lock:
            session = self._session
            if session is None or session.session_id != session_id:
                raise KeyError("Session not found")
            if session.status == "running":
                raise RuntimeError("Search is still running")
            if session.status not in {"completed", "stopped"}:
                raise RuntimeError(f"Cannot load more from session status '{session.status}'")
            if not session.has_more:
                raise RuntimeError("No more artists to load")

        await self._enrich_next_batch(session)
        return session

    async def _run_session(self, session: LastfmDiscoverySession) -> None:
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
            logger.exception("Last.fm Discovery session failed: %s", e)
            session.status = "error"
            session.error = str(e)

    def _rank_candidate_order(self, session: LastfmDiscoverySession) -> list[str]:
        ranked = sorted(
            session.results.values(),
            key=lambda r: (-r.seed_count, -r.match_score, r.name.lower()),
        )
        return [r.mbid for r in ranked]

    async def _fill_missing_images(
        self,
        session: LastfmDiscoverySession,
        config,
        targets: list[LastfmDiscoveryResult] | None = None,
    ) -> None:
        missing = [
            r
            for r in (targets if targets is not None else list(session.results.values()))
            if not r.image_url
        ]
        if not missing:
            return

        sem = asyncio.Semaphore(_DEEZER_IMAGE_CONCURRENCY)

        async with DeezerClient(config) as deezer:

            async def _one(result: LastfmDiscoveryResult) -> None:
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

    async def _fill_lastfm_stats(
        self,
        session: LastfmDiscoverySession,
        lastfm: LastFMClient,
        config,
        targets: list[LastfmDiscoveryResult] | None = None,
    ) -> None:
        """Attach listeners/playcount via artist.getInfo (not present on getsimilar)."""
        results = [
            r
            for r in (targets if targets is not None else list(session.results.values()))
            if r.listeners is None or r.playcount is None
        ]
        if not results:
            return

        concurrency = max(1, int(getattr(config, "LASTFM_FETCH_CONCURRENCY", 3) or 3))
        sem = asyncio.Semaphore(concurrency)

        async def _one(result: LastfmDiscoveryResult) -> None:
            if session.stop_requested:
                return
            async with sem:
                try:
                    info = await lastfm.get_artist_info(
                        mbid=result.mbid,
                        artist_name=result.name,
                    )
                    if not info:
                        return
                    listeners = _as_optional_int(info.get("listeners"))
                    playcount = _as_optional_int(info.get("playcount"))
                    if listeners is not None:
                        result.listeners = listeners
                    if playcount is not None:
                        result.playcount = playcount
                except Exception as e:
                    logger.debug(
                        "Last.fm stats lookup failed for %s: %s",
                        result.name,
                        e,
                    )

        await asyncio.gather(*[_one(r) for r in results])

    async def _enrich_slice(
        self,
        session: LastfmDiscoverySession,
        start: int,
        end: int,
        *,
        lastfm: LastFMClient | None = None,
        config=None,
    ) -> None:
        slice_mbids = session.candidate_order[start:end]
        targets = [session.results[m] for m in slice_mbids if m in session.results]
        if not targets:
            session.visible_count = max(session.visible_count, end)
            return

        cfg = config or ConfigAdapter()
        if lastfm is not None:
            await self._fill_lastfm_stats(session, lastfm, cfg, targets)
            if session.stop_requested:
                return
            await self._fill_missing_images(session, cfg, targets)
        else:
            async with LastFMClient(cfg) as lf:
                await self._fill_lastfm_stats(session, lf, cfg, targets)
                if session.stop_requested:
                    return
                await self._fill_missing_images(session, cfg, targets)

        session.visible_count = max(session.visible_count, end)

    async def _enrich_next_batch(self, session: LastfmDiscoverySession) -> None:
        start = session.visible_count
        end = min(len(session.candidate_order), start + session.batch_size)
        if end <= start:
            return
        await self._enrich_slice(session, start, end)

    async def _run_one_shot(self, session: LastfmDiscoverySession) -> None:
        config = ConfigAdapter()

        async with LidarrClient(config) as lidarr, LastFMClient(config) as lastfm:
            discovery = DiscoveryUtils(config, lidarr)
            (
                existing_mbids,
                existing_names,
                excluded_mbids,
            ) = await discovery.get_lidarr_context(force_refresh=True)
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
                        "Last.fm Discovery similar lookup failed for %s: %s",
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

                    session.results[mbid] = LastfmDiscoveryResult(
                        mbid=mbid,
                        name=name,
                        match_score=match_score,
                        seed_count=1,
                        seed_names=[seed["name"]],
                        url=(row.get("url") or ""),
                        image_url=image_url,
                    )
                    existing_mbids.add(mbid)
                    existing_names.add(name.lower())

            if session.stop_requested:
                session.status = "stopped"
                return

            # Drop weak matches, then rank by consensus then match score.
            if session.min_match_score > 0:
                session.results = {
                    mbid: result
                    for mbid, result in session.results.items()
                    if result.match_score >= session.min_match_score
                }

            session.candidate_order = self._rank_candidate_order(session)
            session.visible_count = 0

            if session.candidate_order:
                end = min(len(session.candidate_order), session.batch_size)
                await self._enrich_slice(session, 0, end, lastfm=lastfm, config=config)

            if session.stop_requested:
                session.status = "stopped"
            else:
                session.status = "completed"


lastfm_discovery_service = LastfmDiscoveryService()
