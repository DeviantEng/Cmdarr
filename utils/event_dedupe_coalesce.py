"""Merge duplicate concert_event rows after dedupe-key recomputation."""

from __future__ import annotations

import sqlite3
from collections import defaultdict

from utils.event_geo import coerce_location_str, make_dedupe_key, venue_fingerprint


def coalesce_concert_event_duplicates(cursor: sqlite3.Cursor) -> None:
    """
    Recompute venue fingerprints, merge duplicate concert_event rows that share the
    same dedupe key — preserving per-source links, user-interested state, and per-event
    hides — then refresh dedupe_key for all remaining rows.
    """
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='concert_event'")
    if not cursor.fetchone():
        return

    cursor.execute(
        """
        SELECT id, artist_mbid, artist_name, venue_name, venue_city, venue_region,
               venue_lat, venue_lon, local_date, user_interested
        FROM concert_event
        """
    )
    rows = cursor.fetchall()
    if not rows:
        return

    def compute_dedupe_key(
        artist_mbid: str,
        local_date: str,
        venue_name,
        venue_city,
        venue_region,
        venue_lat,
        venue_lon,
    ) -> str:
        v_name = coerce_location_str(venue_name)
        v_city = coerce_location_str(venue_city)
        v_region = coerce_location_str(venue_region)
        fp = venue_fingerprint(v_name, v_city, v_region, venue_lat, venue_lon)
        return make_dedupe_key(artist_mbid, local_date, fp)

    groups: dict[str, list[int]] = defaultdict(list)
    for row in rows:
        _id, artist_mbid, _an, vn, vc, vr, vlat, vlon, local_date, _ui = row
        dk = compute_dedupe_key(artist_mbid, local_date, vn, vc, vr, vlat, vlon)
        groups[dk].append(_id)

    for _dk, ids in groups.items():
        ids.sort()
        if len(ids) <= 1:
            continue
        winner = ids[0]
        for loser in ids[1:]:
            cursor.execute(
                "SELECT id, provider, external_id FROM concert_event_source WHERE concert_event_id = ?",
                (loser,),
            )
            for src_id, prov, ext in cursor.fetchall():
                cursor.execute(
                    """
                    SELECT 1 FROM concert_event_source
                    WHERE concert_event_id = ?
                      AND provider = ?
                      AND IFNULL(external_id, '') = IFNULL(?, '')
                    """,
                    (winner, prov, ext),
                )
                if cursor.fetchone():
                    cursor.execute("DELETE FROM concert_event_source WHERE id = ?", (src_id,))
                else:
                    cursor.execute(
                        "UPDATE concert_event_source SET concert_event_id = ? WHERE id = ?",
                        (winner, src_id),
                    )

            cursor.execute("SELECT user_interested FROM concert_event WHERE id = ?", (loser,))
            urow = cursor.fetchone()
            if urow and urow[0]:
                cursor.execute(
                    "UPDATE concert_event SET user_interested = 1 WHERE id = ?", (winner,)
                )

            cursor.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='artist_concert_hidden_event'"
            )
            if cursor.fetchone():
                cursor.execute(
                    "SELECT hidden_at FROM artist_concert_hidden_event WHERE event_id = ?",
                    (loser,),
                )
                hr = cursor.fetchone()
                if hr:
                    cursor.execute(
                        """
                        INSERT OR IGNORE INTO artist_concert_hidden_event (event_id, hidden_at)
                        VALUES (?, ?)
                        """,
                        (winner, hr[0]),
                    )

            cursor.execute("DELETE FROM concert_event WHERE id = ?", (loser,))

    cursor.execute(
        """
        SELECT id, artist_mbid, venue_name, venue_city, venue_region,
               venue_lat, venue_lon, local_date
        FROM concert_event
        """
    )
    for row in cursor.fetchall():
        eid, artist_mbid, vn, vc, vr, vlat, vlon, local_date = row
        new_dk = compute_dedupe_key(artist_mbid, local_date, vn, vc, vr, vlat, vlon)
        cursor.execute(
            "UPDATE concert_event SET dedupe_key = ? WHERE id = ?",
            (new_dk, eid),
        )
