"""Persist normalized artist-event rows with dedupe and source links."""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from database.config_models import ArtistEvent, ArtistEventSource
from utils.event_geo import coerce_location_str, make_dedupe_key, venue_fingerprint
from utils.tm_event_meta import merge_event_kind


def persist_normalized_events(session: Session, items: list[dict[str, Any]]) -> tuple[int, int]:
    """
    Insert or merge events. Returns (new_canonical_events, sources_added).
    """
    new_events = 0
    sources_added = 0
    for item in items:
        v_name = coerce_location_str(item.get("venue_name"))
        v_city = coerce_location_str(item.get("venue_city"))
        v_region = coerce_location_str(item.get("venue_region"))
        v_country = coerce_location_str(item.get("venue_country"))
        fp = venue_fingerprint(
            v_name,
            v_city,
            v_region,
            item.get("venue_lat"),
            item.get("venue_lon"),
        )
        dk = make_dedupe_key(item["artist_mbid"], item["local_date"], fp)
        existing = session.query(ArtistEvent).filter(ArtistEvent.dedupe_key == dk).first()
        if not existing:
            ek = (item.get("event_kind") or "show").strip() or "show"
            existing = ArtistEvent(
                artist_mbid=item["artist_mbid"],
                artist_name=item["artist_name"],
                venue_name=v_name,
                venue_city=v_city,
                venue_region=v_region,
                venue_country=v_country,
                venue_lat=item.get("venue_lat"),
                venue_lon=item.get("venue_lon"),
                starts_at_utc=item["starts_at_utc"],
                local_date=item["local_date"],
                dedupe_key=dk,
                event_kind=ek,
                festival_key=item.get("festival_key"),
                tm_event_name=(item.get("tm_event_name") or None),
            )
            session.add(existing)
            session.flush()
            new_events += 1
        else:
            if (existing.venue_lat is None or existing.venue_lon is None) and item.get(
                "venue_lat"
            ) is not None:
                existing.venue_lat = item.get("venue_lat")
                existing.venue_lon = item.get("venue_lon")
            if item.get("event_kind"):
                existing.event_kind = merge_event_kind(existing.event_kind, item.get("event_kind"))
            if item.get("festival_key") and not existing.festival_key:
                existing.festival_key = item["festival_key"]
            if item.get("tm_event_name") and not existing.tm_event_name:
                existing.tm_event_name = (item["tm_event_name"] or "")[:500]

        ext = (item.get("external_id") or "")[:256]
        prov = item["provider"]
        src = (
            session.query(ArtistEventSource)
            .filter(
                ArtistEventSource.concert_event_id == existing.id,
                ArtistEventSource.provider == prov,
                ArtistEventSource.external_id == ext,
            )
            .first()
        )
        if not src:
            session.add(
                ArtistEventSource(
                    concert_event_id=existing.id,
                    provider=prov,
                    external_id=ext,
                    source_url=item.get("source_url"),
                )
            )
            sources_added += 1

    return new_events, sources_added
