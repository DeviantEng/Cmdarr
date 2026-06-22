"""Tests for diagnose_event_dedupe analysis logic."""

import sqlite3
from pathlib import Path

from tools.diagnose_event_dedupe import _load_events, analyze


def _seed_db(path: Path) -> None:
    conn = sqlite3.connect(path)
    cur = conn.cursor()
    cur.executescript(
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
            dedupe_key TEXT
        );
        CREATE TABLE concert_event_source (
            id INTEGER PRIMARY KEY,
            concert_event_id INTEGER,
            provider TEXT,
            external_id TEXT
        );
        INSERT INTO concert_event VALUES
          (1, 'mbid-a', 'Autumn Kings', '2026-09-18', 'Brooklyn Bowl', 'Nashville', 'TN',
           36.16251, -86.77148, 'old-tm-key'),
          (2, 'mbid-a', 'Autumn Kings', '2026-09-18', 'Brooklyn Bowl', 'Nashville', NULL,
           NULL, NULL, 'old-dz-key');
        INSERT INTO concert_event_source VALUES
          (1, 1, 'ticketmaster', 'tm-1'),
          (2, 2, 'deezer', 'dz-1');
        """
    )
    conn.commit()
    conn.close()


def test_analyze_finds_region_split_pair(tmp_path):
    db = tmp_path / "test.db"
    _seed_db(db)
    conn = sqlite3.connect(db)
    events = _load_events(conn)
    conn.close()

    stats = analyze(events)
    assert stats["tm_only"] == 1
    assert stats["dz_only"] == 1
    assert stats["tm_and_dz"] == 0
    assert len(stats["split_tm_dz_pairs"]) == 1
    pair = stats["split_tm_dz_pairs"][0]
    assert pair["tm_region"] == "TN"
    assert pair["dz_region"] is None
    assert pair["old_tm_key"] != pair["old_dz_key"]
    assert pair["new_key"]
