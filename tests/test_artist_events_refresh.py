"""Unit tests for ArtistEventsRefreshCommand._fetch_for_artist error classification."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from typing import Any

import pytest

from commands import artist_events_refresh as aer_module
from commands.artist_events_refresh import ArtistEventsRefreshCommand


class _FakeClient:
    def __init__(self, result: Any):
        self._result = result

    async def __aenter__(self):
        return self

    async def __aexit__(self, *a):
        return False

    async def fetch_upcoming_events(self, *_a, **_kw):
        if isinstance(self._result, Exception):
            raise self._result
        return self._result


class _FakeDeezerClient:
    def __init__(self, result: Any):
        self._result = result

    async def __aenter__(self):
        return self

    async def __aexit__(self, *a):
        return False

    async def fetch_upcoming_events(self, *_a, **_kw):
        if isinstance(self._result, Exception):
            raise self._result
        return self._result


def _install_fake(monkeypatch: pytest.MonkeyPatch, tm: Any, sg: Any, dz: Any) -> None:
    monkeypatch.setattr(
        aer_module, "TicketmasterClient", lambda *_a, **_kw: _FakeClient(tm), raising=True
    )
    monkeypatch.setattr(
        aer_module, "SeatGeekClient", lambda *_a, **_kw: _FakeClient(sg), raising=True
    )
    monkeypatch.setattr(
        aer_module, "DeezerEventsClient", lambda *_a, **_kw: _FakeDeezerClient(dz), raising=True
    )


def _make_event(provider: str = "ticketmaster") -> dict[str, Any]:
    return {
        "provider": provider,
        "external_id": f"{provider}-1",
        "artist_mbid": "mbid",
        "artist_name": "A",
        "starts_at_utc": datetime(2026, 6, 1, tzinfo=UTC),
        "local_date": "2026-06-01",
    }


def _run_fetch(
    cmd: ArtistEventsRefreshCommand,
    *,
    tm_on: bool,
    sg_on: bool,
    dz_on: bool,
) -> tuple[list[dict[str, Any]], list[str], str | None]:
    return asyncio.run(
        cmd._fetch_for_artist(
            cmd.config_adapter,
            "Artist Name",
            "mbid",
            None,
            tm_on,
            "tm-key" if tm_on else "",
            sg_on,
            "sg-id" if sg_on else "",
            dz_on,
            "dz-arl" if dz_on else "",
        )
    )


def test_fetch_parallel_success_no_errors(monkeypatch):
    ev_tm = _make_event("ticketmaster")
    ev_sg = _make_event("seatgeek")
    ev_dz = _make_event("deezer")
    _install_fake(monkeypatch, [ev_tm], [ev_sg], ([ev_dz], "27"))
    cmd = ArtistEventsRefreshCommand()

    merged, errored, dz_id = _run_fetch(cmd, tm_on=True, sg_on=True, dz_on=True)

    assert len(merged) == 3
    assert errored == []
    assert dz_id == "27"


def test_fetch_provider_returning_none_is_reported_as_error(monkeypatch):
    _install_fake(monkeypatch, None, [], ([], None))
    cmd = ArtistEventsRefreshCommand()

    merged, errored, _ = _run_fetch(cmd, tm_on=True, sg_on=True, dz_on=True)

    assert merged == []
    assert errored == ["ticketmaster"]


def test_fetch_deezer_error_reported(monkeypatch):
    _install_fake(monkeypatch, [_make_event()], [], (None, None))
    cmd = ArtistEventsRefreshCommand()

    merged, errored, _ = _run_fetch(cmd, tm_on=True, sg_on=False, dz_on=True)

    assert len(merged) == 1
    assert errored == ["deezer"]


def test_fetch_disabled_providers_are_not_errors(monkeypatch):
    _install_fake(monkeypatch, None, None, (None, None))
    cmd = ArtistEventsRefreshCommand()

    merged, errored, _ = _run_fetch(cmd, tm_on=False, sg_on=False, dz_on=False)

    assert merged == []
    assert errored == []
