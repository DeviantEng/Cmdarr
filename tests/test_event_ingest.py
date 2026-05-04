"""Unit tests for persist_normalized_events (artist events ingest + dedupe)."""

from datetime import UTC, datetime

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from database.config_models import ArtistEvent, ArtistEventSource, ConfigBase
from utils.event_ingest import persist_normalized_events


@pytest.fixture()
def session():
    """In-memory sqlite Session bound to the config models metadata."""
    engine = create_engine("sqlite://")
    ConfigBase.metadata.create_all(engine)
    TestSession = sessionmaker(bind=engine)
    s = TestSession()
    try:
        yield s
    finally:
        s.close()
        engine.dispose()


def _item(**overrides):
    base = {
        "provider": "ticketmaster",
        "external_id": "tm-1",
        "source_url": "https://example.com/tm-1",
        "artist_mbid": "mbid-pierce",
        "artist_name": "Pierce the Veil",
        "venue_name": "Nissan Stadium",
        "venue_city": "Nashville",
        "venue_region": "TN",
        "venue_country": "US",
        "venue_lat": 36.16251,
        "venue_lon": -86.77148,
        "starts_at_utc": datetime(2026, 8, 13, 23, 0, tzinfo=UTC),
        "local_date": "2026-08-13",
    }
    base.update(overrides)
    return base


def test_persist_inserts_new_canonical_event_and_source(session):
    new_events, sources_added = persist_normalized_events(session, [_item()])
    session.commit()

    assert new_events == 1
    assert sources_added == 1
    assert session.query(ArtistEvent).count() == 1
    assert session.query(ArtistEventSource).count() == 1


def test_persist_merges_duplicate_rows_across_providers_with_noisy_coords(session):
    tm = _item(provider="ticketmaster", external_id="tm-1")
    bit = _item(
        provider="bandsintown",
        external_id="bit-xyz",
        source_url="https://bandsintown.example/bit-xyz",
        venue_lat=36.16284,
        venue_lon=-86.77112,
    )

    n1, s1 = persist_normalized_events(session, [tm])
    session.commit()
    n2, s2 = persist_normalized_events(session, [bit])
    session.commit()

    assert (n1, s1) == (1, 1)
    assert n2 == 0
    assert s2 == 1
    assert session.query(ArtistEvent).count() == 1
    providers = sorted(r.provider for r in session.query(ArtistEventSource).all())
    assert providers == ["bandsintown", "ticketmaster"]


def test_persist_is_idempotent_for_same_provider_external_id(session):
    item = _item(provider="ticketmaster", external_id="tm-1")

    persist_normalized_events(session, [item])
    session.commit()
    n2, s2 = persist_normalized_events(session, [item])
    session.commit()

    assert n2 == 0
    assert s2 == 0
    assert session.query(ArtistEvent).count() == 1
    assert session.query(ArtistEventSource).count() == 1


def test_persist_keeps_events_on_different_dates_separate(session):
    a = _item(local_date="2026-08-13", starts_at_utc=datetime(2026, 8, 13, 23, 0, tzinfo=UTC))
    b = _item(
        local_date="2026-08-14",
        starts_at_utc=datetime(2026, 8, 14, 23, 0, tzinfo=UTC),
        external_id="tm-2",
    )
    persist_normalized_events(session, [a, b])
    session.commit()

    assert session.query(ArtistEvent).count() == 2
    assert session.query(ArtistEventSource).count() == 2


def test_persist_keeps_events_for_different_artists_separate(session):
    a = _item(artist_mbid="mbid-pierce", artist_name="Pierce the Veil", external_id="tm-1")
    b = _item(artist_mbid="mbid-other", artist_name="Other Artist", external_id="tm-2")
    persist_normalized_events(session, [a, b])
    session.commit()

    assert session.query(ArtistEvent).count() == 2


def test_persist_upgrades_festival_key_from_tm_id_to_tmfest(session):
    old = _item(
        festival_key="tm:legacyevt",
        event_kind="festival",
        tm_event_name="Louder Than Life: Band",
    )
    persist_normalized_events(session, [old])
    session.commit()
    row = session.query(ArtistEvent).one()
    assert row.festival_key == "tm:legacyevt"

    newer = _item(
        festival_key="tmfest:venue1:2026:louder-than-life-2026",
        event_kind="festival",
        tm_event_name="Louder Than Life: Band",
    )
    persist_normalized_events(session, [newer])
    session.commit()
    row = session.query(ArtistEvent).one()
    assert row.festival_key == "tmfest:venue1:2026:louder-than-life-2026"
