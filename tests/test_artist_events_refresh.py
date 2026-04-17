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


def _install_fake(monkeypatch: pytest.MonkeyPatch, bit: Any, sk: Any, tm: Any) -> None:
    monkeypatch.setattr(
        aer_module, "BandsintownClient", lambda *_a, **_kw: _FakeClient(bit), raising=True
    )
    monkeypatch.setattr(
        aer_module, "SongkickClient", lambda *_a, **_kw: _FakeClient(sk), raising=True
    )
    monkeypatch.setattr(
        aer_module, "TicketmasterClient", lambda *_a, **_kw: _FakeClient(tm), raising=True
    )


def _make_event() -> dict[str, Any]:
    return {
        "provider": "ticketmaster",
        "external_id": "tm-1",
        "artist_mbid": "mbid",
        "artist_name": "A",
        "starts_at_utc": datetime(2026, 6, 1, tzinfo=UTC),
        "local_date": "2026-06-01",
    }


def _run_fetch(
    cmd: ArtistEventsRefreshCommand,
    *,
    bit_on: bool,
    sk_on: bool,
    tm_on: bool,
) -> tuple[list[dict[str, Any]], list[str]]:
    return asyncio.run(
        cmd._fetch_for_artist(
            cmd.config_adapter,
            "Artist Name",
            "mbid",
            bit_on,
            "app-id" if bit_on else "",
            sk_on,
            "sk-key" if sk_on else "",
            tm_on,
            "tm-key" if tm_on else "",
        )
    )


def test_fetch_all_success_no_errors(monkeypatch):
    ev = _make_event()
    _install_fake(monkeypatch, bit=[ev], sk=[], tm=[ev, ev])
    cmd = ArtistEventsRefreshCommand()

    merged, errored = _run_fetch(cmd, bit_on=True, sk_on=True, tm_on=True)

    assert len(merged) == 3
    assert errored == []


def test_fetch_provider_returning_none_is_reported_as_error(monkeypatch):
    _install_fake(monkeypatch, bit=None, sk=[], tm=[_make_event()])
    cmd = ArtistEventsRefreshCommand()

    merged, errored = _run_fetch(cmd, bit_on=True, sk_on=True, tm_on=True)

    assert len(merged) == 1
    assert errored == ["bandsintown"]


def test_fetch_raising_provider_is_reported_as_error(monkeypatch):
    _install_fake(monkeypatch, bit=[], sk=RuntimeError("boom"), tm=[_make_event()])
    cmd = ArtistEventsRefreshCommand()

    merged, errored = _run_fetch(cmd, bit_on=True, sk_on=True, tm_on=True)

    assert len(merged) == 1
    assert errored == ["songkick"]


def test_fetch_empty_list_is_not_an_error(monkeypatch):
    _install_fake(monkeypatch, bit=[], sk=[], tm=[])
    cmd = ArtistEventsRefreshCommand()

    merged, errored = _run_fetch(cmd, bit_on=True, sk_on=True, tm_on=True)

    assert merged == []
    assert errored == []


def test_fetch_disabled_providers_are_not_errors(monkeypatch):
    _install_fake(monkeypatch, bit=None, sk=None, tm=[_make_event()])
    cmd = ArtistEventsRefreshCommand()

    merged, errored = _run_fetch(cmd, bit_on=False, sk_on=False, tm_on=True)

    assert len(merged) == 1
    assert errored == []


def test_fetch_multiple_providers_can_error_in_one_pass(monkeypatch):
    _install_fake(monkeypatch, bit=None, sk=None, tm=[_make_event()])
    cmd = ArtistEventsRefreshCommand()

    merged, errored = _run_fetch(cmd, bit_on=True, sk_on=True, tm_on=True)

    assert len(merged) == 1
    assert sorted(errored) == ["bandsintown", "songkick"]
