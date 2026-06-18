"""Merge duplicate concert_event rows after dedupe-key recomputation."""

from __future__ import annotations

import sqlite3
from collections import defaultdict

from utils.event_geo import compute_event_dedupe_key, parse_place_city_region


def _row_coords(lat, lon) -> bool:
    return lat is not None and lon is not None


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

    by_id: dict[int, tuple] = {row[0]: row for row in rows}

    def winner_sort_key(event_id: int) -> tuple:
        row = by_id[event_id]
        _id, _mbid, _an, vn, vc, vr, vlat, vlon, _ld, _ui = row
        has_coords = 0 if _row_coords(vlat, vlon) else 1
        has_region = 0 if (parse_place_city_region(vc, vr)[1]) else 1
        return (has_coords, has_region, event_id)

    groups: dict[str, list[int]] = defaultdict(list)
    for row in rows:
        _id, artist_mbid, _an, vn, vc, vr, vlat, vlon, local_date, _ui = row
        dk = compute_event_dedupe_key(artist_mbid, local_date, vn, vc, vr, vlat, vlon)
        groups[dk].append(_id)

    for _dk, ids in groups.items():
        ids.sort(key=winner_sort_key)
        if len(ids) <= 1:
            continue
        winner = ids[0]
        winner_row = by_id[winner]
        w_id, w_mbid, w_an, w_vn, w_vc, w_vr, w_vlat, w_vlon, w_ld, w_ui = winner_row

        for loser in ids[1:]:
            loser_row = by_id[loser]
            _lid, _lmbid, _lan, l_vn, l_vc, l_vr, l_vlat, l_vlon, _lld, _lui = loser_row

            if not _row_coords(w_vlat, w_vlon) and _row_coords(l_vlat, l_vlon):
                w_vlat, w_vlon = l_vlat, l_vlon
                cursor.execute(
                    "UPDATE concert_event SET venue_lat = ?, venue_lon = ? WHERE id = ?",
                    (w_vlat, w_vlon, winner),
                )
                by_id[winner] = (
                    w_id,
                    w_mbid,
                    w_an,
                    w_vn,
                    w_vc,
                    w_vr,
                    w_vlat,
                    w_vlon,
                    w_ld,
                    w_ui,
                )

            w_city, w_region = parse_place_city_region(w_vc, w_vr)
            l_city, l_region = parse_place_city_region(l_vc, l_vr)
            if not w_region and l_region:
                w_vc, w_vr = l_city or w_vc, l_region
                cursor.execute(
                    """
                    UPDATE concert_event SET venue_city = ?, venue_region = ?
                    WHERE id = ?
                    """,
                    (w_vc, w_vr, winner),
                )
                by_id[winner] = (
                    w_id,
                    w_mbid,
                    w_an,
                    w_vn,
                    w_vc,
                    w_vr,
                    w_vlat,
                    w_vlon,
                    w_ld,
                    w_ui,
                )

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
            del by_id[loser]

    cursor.execute(
        """
        SELECT id, artist_mbid, venue_name, venue_city, venue_region,
               venue_lat, venue_lon, local_date
        FROM concert_event
        """
    )
    for row in cursor.fetchall():
        eid, artist_mbid, vn, vc, vr, vlat, vlon, local_date = row
        new_dk = compute_event_dedupe_key(artist_mbid, local_date, vn, vc, vr, vlat, vlon)
        cursor.execute(
            "UPDATE concert_event SET dedupe_key = ? WHERE id = ?",
            (new_dk, eid),
        )


def normalize_concert_event_place_fields(cursor: sqlite3.Cursor) -> None:
    """Rewrite comma-separated venue_city values into city + region columns."""
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='concert_event'")
    if not cursor.fetchone():
        return
    cursor.execute(
        """
        SELECT id, venue_city, venue_region
        FROM concert_event
        WHERE venue_city LIKE '%,%'
          AND (venue_region IS NULL OR TRIM(venue_region) = '')
        """
    )
    for eid, city, region in cursor.fetchall():
        new_city, new_region = parse_place_city_region(city, region)
        if new_city != city or new_region != region:
            cursor.execute(
                """
                UPDATE concert_event
                SET venue_city = ?, venue_region = ?
                WHERE id = ?
                """,
                (new_city, new_region, eid),
            )
