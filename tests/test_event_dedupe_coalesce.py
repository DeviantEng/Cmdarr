"""Tests for concert event dedupe coalescing."""

import sqlite3

from utils.event_dedupe_coalesce import (
    coalesce_concert_event_duplicates,
    normalize_concert_event_place_fields,
)


def _create_concert_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE concert_event (
            id INTEGER PRIMARY KEY,
            artist_mbid TEXT,
            artist_name TEXT,
            local_date TEXT,
            venue_name TEXT,
            venue_city TEXT,
            venue_region TEXT,
            venue_lat REAL,
            venue_lon REAL,
            dedupe_key TEXT,
            user_interested INTEGER DEFAULT 0
        );
        CREATE TABLE concert_event_source (
            id INTEGER PRIMARY KEY,
            concert_event_id INTEGER,
            provider TEXT,
            external_id TEXT
        );
        """
    )


def test_coalesce_merges_duplicate_events_and_sources():
    conn = sqlite3.connect(":memory:")
    _create_concert_schema(conn)
    cur = conn.cursor()
    cur.executescript(
        """
        INSERT INTO concert_event VALUES
          (1, 'mbid-a', 'Artist', '2026-09-18', 'Brooklyn Bowl', 'Nashville', 'TN',
           36.16, -86.77, 'old-key-1', 0),
          (2, 'mbid-a', 'Artist', '2026-09-18', 'Brooklyn Bowl', 'Nashville', NULL,
           NULL, NULL, 'old-key-2', 1);
        INSERT INTO concert_event_source VALUES
          (1, 1, 'ticketmaster', 'tm-1'),
          (2, 2, 'deezer', 'dz-1');
        """
    )

    coalesce_concert_event_duplicates(cur)
    conn.commit()

    cur.execute("SELECT COUNT(*) FROM concert_event")
    assert cur.fetchone()[0] == 1
    cur.execute("SELECT user_interested, venue_lat, venue_region FROM concert_event")
    interested, lat, region = cur.fetchone()
    assert interested == 1
    assert lat == 36.16
    assert region == "TN"
    cur.execute("SELECT provider FROM concert_event_source ORDER BY provider")
    assert [row[0] for row in cur.fetchall()] == ["deezer", "ticketmaster"]
    cur.execute("SELECT dedupe_key FROM concert_event")
    assert cur.fetchone()[0]


def test_normalize_concert_event_place_fields_splits_comma_city():
    conn = sqlite3.connect(":memory:")
    _create_concert_schema(conn)
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO concert_event (
            artist_mbid, artist_name, local_date, venue_name, venue_city, venue_region
        ) VALUES ('mbid', 'Artist', '2026-01-01', 'Venue', 'Nashville, TN', NULL)
        """
    )

    normalize_concert_event_place_fields(cur)
    conn.commit()

    cur.execute("SELECT venue_city, venue_region FROM concert_event")
    city, region = cur.fetchone()
    assert city == "Nashville"
    assert region == "TN"
