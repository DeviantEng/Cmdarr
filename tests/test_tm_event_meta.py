"""Tests for Ticketmaster URL selection and festival classification."""

from utils.tm_event_meta import (
    classify_ticketmaster_event,
    merge_event_kind,
    pick_best_ticketmaster_url,
    score_ticketmaster_url,
)


def test_score_prefers_ticketmaster_event_over_fgtix():
    tm = (
        "https://www.ticketmaster.com/lorna-shore-buffalo-new-york-04-17-2026/event/0000642E9D5670D"
    )
    fgtix = "https://on.fgtix.com/trk/h1wcc"
    assert score_ticketmaster_url(tm, "Lorna Shore") > score_ticketmaster_url(fgtix, "Lorna Shore")


def test_pick_best_prefers_artist_slug():
    ev = {
        "url": "https://on.fgtix.com/trk/h1wcc",
        "outlets": [
            {
                "url": "https://www.ticketmaster.com/lorna-shore-buffalo-new-york-04-17-2026/event/abc"
            }
        ],
    }
    assert "ticketmaster.com" in (pick_best_ticketmaster_url(ev, "Lorna Shore") or "")


def test_pick_best_single_url():
    ev = {"url": "https://on.fgtix.com/trk/x"}
    assert pick_best_ticketmaster_url(ev, "X") == "https://on.fgtix.com/trk/x"


def test_classify_festival_keyword():
    ev = {
        "id": "abc123",
        "name": "Sonic Temple Music Festival 2026",
        "url": "https://www.ticketmaster.com/event/x",
        "_embedded": {"attractions": [{"name": "Band"}]},
    }
    kind, key, name = classify_ticketmaster_event(ev)
    assert kind == "festival"
    assert key == "tm:abc123"
    assert "Sonic" in (name or "")


def test_classify_tour_package_many_attractions():
    ev = {
        "id": "vv1",
        "name": "Some Tour",
        "url": "https://www.ticketmaster.com/x",
        "_embedded": {"attractions": [{"name": f"A{i}"} for i in range(6)]},
    }
    kind, key, _ = classify_ticketmaster_event(ev)
    assert kind == "tour_package"
    assert key == "tm:vv1"


def test_merge_event_kind_prefers_festival():
    assert merge_event_kind("show", "festival") == "festival"
    assert merge_event_kind("festival", "tour_package") == "festival"
    assert merge_event_kind("tour_package", "show") == "tour_package"
