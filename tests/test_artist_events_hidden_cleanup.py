"""Per-event hide cleanup tied to artist_events_refresh."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from commands.artist_events_refresh import ArtistEventsRefreshCommand
from database.config_models import (
    ArtistConcertHiddenEvent,
    ArtistEvent,
    ConfigBase,
)


@pytest.fixture()
def session():
    engine = create_engine("sqlite://")
    ConfigBase.metadata.create_all(engine)
    TestSession = sessionmaker(bind=engine)
    s = TestSession()
    try:
        yield s
    finally:
        s.close()
        engine.dispose()


def test_prune_removes_hide_when_show_is_in_the_past(session):
    now = datetime(2026, 6, 15, 12, 0, tzinfo=UTC)
    past_ev = ArtistEvent(
        artist_mbid="m1",
        artist_name="A",
        venue_name="V",
        venue_city="C",
        venue_region=None,
        venue_country="US",
        starts_at_utc=now - timedelta(days=2),
        local_date="2026-06-13",
        dedupe_key="k1",
    )
    session.add(past_ev)
    session.commit()
    session.refresh(past_ev)
    session.add(ArtistConcertHiddenEvent(event_id=past_ev.id))
    session.commit()

    cmd = ArtistEventsRefreshCommand()
    n_past, n_orphan = cmd._prune_stale_hidden_single_events(session, now)
    session.commit()

    assert n_past == 1
    assert n_orphan == 0
    assert session.query(ArtistConcertHiddenEvent).count() == 0


def test_prune_removes_orphan_hide(session):
    now = datetime(2026, 6, 15, 12, 0, tzinfo=UTC)
    # Simulate a stray row left when FK enforcement was off during a parent delete.
    session.execute(text("PRAGMA foreign_keys = OFF"))
    session.execute(text("INSERT INTO artist_concert_hidden_event (event_id) VALUES (99999)"))
    session.execute(text("PRAGMA foreign_keys = ON"))
    session.commit()

    cmd = ArtistEventsRefreshCommand()
    n_past, n_orphan = cmd._prune_stale_hidden_single_events(session, now)
    session.commit()

    assert n_past == 0
    assert n_orphan == 1
    assert session.query(ArtistConcertHiddenEvent).count() == 0


def test_prune_keeps_hide_within_24h_after_start(session):
    now = datetime(2026, 6, 15, 12, 0, tzinfo=UTC)
    recent_past = ArtistEvent(
        artist_mbid="m3",
        artist_name="C",
        venue_name="V",
        venue_city="C",
        venue_region=None,
        venue_country="US",
        starts_at_utc=now - timedelta(hours=12),
        local_date="2026-06-15",
        dedupe_key="k3",
    )
    session.add(recent_past)
    session.commit()
    session.refresh(recent_past)
    session.add(ArtistConcertHiddenEvent(event_id=recent_past.id))
    session.commit()

    cmd = ArtistEventsRefreshCommand()
    n_past, n_orphan = cmd._prune_stale_hidden_single_events(session, now)
    session.commit()

    assert n_past == 0
    assert n_orphan == 0
    assert session.query(ArtistConcertHiddenEvent).count() == 1


def test_prune_removes_hide_after_24h_from_start(session):
    now = datetime(2026, 6, 15, 12, 0, tzinfo=UTC)
    old_past = ArtistEvent(
        artist_mbid="m4",
        artist_name="D",
        venue_name="V",
        venue_city="C",
        venue_region=None,
        venue_country="US",
        starts_at_utc=now - timedelta(hours=30),
        local_date="2026-06-14",
        dedupe_key="k4",
    )
    session.add(old_past)
    session.commit()
    session.refresh(old_past)
    session.add(ArtistConcertHiddenEvent(event_id=old_past.id))
    session.commit()

    cmd = ArtistEventsRefreshCommand()
    n_past, n_orphan = cmd._prune_stale_hidden_single_events(session, now)
    session.commit()

    assert n_past == 1
    assert n_orphan == 0
    assert session.query(ArtistConcertHiddenEvent).count() == 0


def test_prune_keeps_hide_for_future_show(session):
    now = datetime(2026, 6, 15, 12, 0, tzinfo=UTC)
    fut = ArtistEvent(
        artist_mbid="m2",
        artist_name="B",
        venue_name="V",
        venue_city="C",
        venue_region=None,
        venue_country="US",
        starts_at_utc=now + timedelta(days=7),
        local_date="2026-06-22",
        dedupe_key="k2",
    )
    session.add(fut)
    session.commit()
    session.refresh(fut)
    session.add(ArtistConcertHiddenEvent(event_id=fut.id))
    session.commit()

    cmd = ArtistEventsRefreshCommand()
    n_past, n_orphan = cmd._prune_stale_hidden_single_events(session, now)
    session.commit()

    assert n_past == 0
    assert n_orphan == 0
    assert session.query(ArtistConcertHiddenEvent).count() == 1
