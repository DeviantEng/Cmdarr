#!/usr/bin/env python3
"""
Compare concert_event dedupe keys (old vs new fingerprint) against a live Cmdarr DB.

Use this before/after the Deezer merge fix to verify split TM+DZ rows would coalesce.

Example (on the host with cmdarr_config.db):
  python tools/diagnose_event_dedupe.py /opt/docker/music/cmdarr-data/cmdarr_config.db
  python tools/diagnose_event_dedupe.py /opt/docker/music/cmdarr-data/cmdarr_config.db --examples 15

From inside the Cmdarr container (repo mounted or copied):
  python tools/diagnose_event_dedupe.py /app/data/cmdarr_config.db
"""

from __future__ import annotations

import argparse
import sqlite3
import sys
from collections import defaultdict
from pathlib import Path

# Allow imports from repo root when run as `python tools/diagnose_event_dedupe.py`
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from utils.event_geo import compute_event_dedupe_key  # noqa: E402


def _load_events(conn: sqlite3.Connection) -> list[dict]:
    cur = conn.cursor()
    cur.execute(
        """
        SELECT ce.id, ce.artist_mbid, ce.artist_name, ce.local_date,
               ce.venue_name, ce.venue_city, ce.venue_region,
               ce.venue_lat, ce.venue_lon, ce.dedupe_key,
               GROUP_CONCAT(s.provider) AS providers
        FROM concert_event ce
        JOIN concert_event_source s ON s.concert_event_id = ce.id
        GROUP BY ce.id
        """
    )
    rows = []
    for r in cur.fetchall():
        providers = sorted(set((r[10] or "").split(",")))
        rows.append(
            {
                "id": r[0],
                "artist_mbid": r[1],
                "artist_name": r[2],
                "local_date": r[3],
                "venue_name": r[4],
                "venue_city": r[5],
                "venue_region": r[6],
                "venue_lat": r[7],
                "venue_lon": r[8],
                "stored_dedupe_key": r[9],
                "providers": providers,
            }
        )
    return rows


def analyze(events: list[dict]) -> dict:
    tm_only = dz_only = both = other = 0
    for ev in events:
        ps = set(ev["providers"])
        if ps == {"ticketmaster"}:
            tm_only += 1
        elif ps == {"deezer"}:
            dz_only += 1
        elif "ticketmaster" in ps and "deezer" in ps:
            both += 1
        else:
            other += 1

    split_pairs: list[dict] = []
    by_slot: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for ev in events:
        by_slot[(ev["artist_mbid"], ev["local_date"])].append(ev)

    for (_mbid, _date), group in by_slot.items():
        tm_rows = [e for e in group if e["providers"] == ["ticketmaster"]]
        dz_rows = [e for e in group if e["providers"] == ["deezer"]]
        if not tm_rows or not dz_rows:
            continue
        for tm in tm_rows:
            for dz in dz_rows:
                old_tm = compute_event_dedupe_key(
                    tm["artist_mbid"],
                    tm["local_date"],
                    tm["venue_name"],
                    tm["venue_city"],
                    tm["venue_region"],
                    tm["venue_lat"],
                    tm["venue_lon"],
                    legacy_fingerprint=True,
                )
                old_dz = compute_event_dedupe_key(
                    dz["artist_mbid"],
                    dz["local_date"],
                    dz["venue_name"],
                    dz["venue_city"],
                    dz["venue_region"],
                    dz["venue_lat"],
                    dz["venue_lon"],
                    legacy_fingerprint=True,
                )
                new_tm = compute_event_dedupe_key(
                    tm["artist_mbid"],
                    tm["local_date"],
                    tm["venue_name"],
                    tm["venue_city"],
                    tm["venue_region"],
                    tm["venue_lat"],
                    tm["venue_lon"],
                )
                new_dz = compute_event_dedupe_key(
                    dz["artist_mbid"],
                    dz["local_date"],
                    dz["venue_name"],
                    dz["venue_city"],
                    dz["venue_region"],
                    dz["venue_lat"],
                    dz["venue_lon"],
                )
                if old_tm != old_dz and new_tm == new_dz:
                    split_pairs.append(
                        {
                            "artist_name": tm["artist_name"],
                            "local_date": tm["local_date"],
                            "tm_id": tm["id"],
                            "dz_id": dz["id"],
                            "tm_venue": tm["venue_name"],
                            "tm_city": tm["venue_city"],
                            "tm_region": tm["venue_region"],
                            "tm_lat": tm["venue_lat"],
                            "dz_venue": dz["venue_name"],
                            "dz_city": dz["venue_city"],
                            "dz_region": dz["venue_region"],
                            "old_tm_key": old_tm[:16],
                            "old_dz_key": old_dz[:16],
                            "new_key": new_tm[:16],
                        }
                    )

    new_groups: dict[str, list[int]] = defaultdict(list)
    for ev in events:
        nk = compute_event_dedupe_key(
            ev["artist_mbid"],
            ev["local_date"],
            ev["venue_name"],
            ev["venue_city"],
            ev["venue_region"],
            ev["venue_lat"],
            ev["venue_lon"],
        )
        new_groups[nk].append(ev["id"])

    mergeable_new = sum(1 for ids in new_groups.values() if len(ids) > 1)
    rows_in_mergeable = sum(len(ids) for ids in new_groups.values() if len(ids) > 1)

    return {
        "total_events": len(events),
        "tm_only": tm_only,
        "dz_only": dz_only,
        "tm_and_dz": both,
        "other_provider_mix": other,
        "split_tm_dz_pairs": split_pairs,
        "mergeable_new_key_groups": mergeable_new,
        "rows_in_mergeable_groups": rows_in_mergeable,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("db_path", help="Path to cmdarr_config.db")
    parser.add_argument(
        "--examples",
        type=int,
        default=10,
        help="Number of split TM+DZ pair examples to print (default 10)",
    )
    args = parser.parse_args()

    db_path = Path(args.db_path)
    if not db_path.is_file():
        print(f"Database not found: {db_path}", file=sys.stderr)
        return 1

    conn = sqlite3.connect(str(db_path))
    try:
        events = _load_events(conn)
    finally:
        conn.close()

    if not events:
        print("No concert_event rows with sources found.")
        return 0

    stats = analyze(events)
    pairs = stats["split_tm_dz_pairs"]

    print("=== Provider mix (canonical rows) ===")
    print(f"  Total events with sources: {stats['total_events']}")
    print(f"  Ticketmaster only:         {stats['tm_only']}")
    print(f"  Deezer only:               {stats['dz_only']}")
    print(f"  Ticketmaster + Deezer:     {stats['tm_and_dz']}")
    print(f"  Other mixes:               {stats['other_provider_mix']}")
    print()
    print("=== Dedupe analysis ===")
    print(
        f"  TM-only + DZ-only pairs same show under NEW fingerprint, split under OLD: {len(pairs)}"
    )
    print(
        f"  New-key groups with 2+ rows (would coalesce on migration): "
        f"{stats['mergeable_new_key_groups']} groups / {stats['rows_in_mergeable_groups']} rows"
    )
    print()

    if not pairs:
        print("No TM/DZ split pairs matched the expected old-split / new-merge pattern.")
        print(
            "Either data is already merged, or splits are due to venue/date mismatch (not region)."
        )
        return 0

    print(f"=== Examples (up to {args.examples}) ===")
    for i, p in enumerate(pairs[: args.examples], 1):
        print(f"\n--- Example {i}: {p['artist_name']} @ {p['local_date']} ---")
        print(
            f"  TM row {p['tm_id']}: {p['tm_venue']!r}, {p['tm_city']!r}, region={p['tm_region']!r}, "
            f"lat={p['tm_lat']}"
        )
        print(
            f"  DZ row {p['dz_id']}: {p['dz_venue']!r}, {p['dz_city']!r}, region={p['dz_region']!r}"
        )
        print(f"  OLD keys: TM={p['old_tm_key']}…  DZ={p['old_dz_key']}…  (different → split)")
        print(f"  NEW key:  {p['new_key']}…  (same → merge)")

    if len(pairs) > args.examples:
        print(f"\n… and {len(pairs) - args.examples} more pair(s).")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
