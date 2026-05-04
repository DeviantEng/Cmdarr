"""Tests for Ticketmaster URL selection and festival classification."""

from urllib.parse import urlparse

from utils.tm_event_meta import (
    _hostname_is_domain_or_subdomain,
    classify_ticketmaster_event,
    merge_event_kind,
    pick_best_ticketmaster_url,
    score_ticketmaster_url,
    stable_festival_group_key,
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
    picked = pick_best_ticketmaster_url(ev, "Lorna Shore")
    assert picked
    host = urlparse(picked).hostname or ""
    assert _hostname_is_domain_or_subdomain(host, "ticketmaster.com")


def test_pick_best_single_url():
    ev = {"url": "https://on.fgtix.com/trk/x"}
    assert pick_best_ticketmaster_url(ev, "X") == "https://on.fgtix.com/trk/x"


def test_classify_festival_keyword():
    ev = {
        "id": "abc123",
        "name": "Sonic Temple Music Festival 2026",
        "url": "https://www.ticketmaster.com/event/x",
        "dates": {"start": {"localDate": "2026-05-15"}},
        "_embedded": {
            "attractions": [{"name": "Band"}],
            "venues": [{"id": "KovZVenue1", "name": "Historic Crew Stadium"}],
        },
    }
    kind, key, name = classify_ticketmaster_event(ev)
    assert kind == "festival"
    assert key == "tmfest:KovZVenue1:2026:sonic-temple-music-festival-2026"
    assert "Sonic" in (name or "")


def test_classify_tour_package_many_attractions():
    ev = {
        "id": "vv1",
        "name": "Some Tour",
        "url": "https://www.ticketmaster.com/x",
        "dates": {"start": {"localDate": "2026-04-20"}},
        "_embedded": {
            "attractions": [{"name": f"A{i}"} for i in range(8)],
            "venues": [{"id": "KovZVenue2", "name": "Arena"}],
        },
    }
    kind, key, _ = classify_ticketmaster_event(ev)
    assert kind == "tour_package"
    assert key == "tmfest:KovZVenue2:2026:some-tour"


def test_six_attractions_without_fgtix_is_show():
    """Headliner + openers often yields ~6 TM attractions — not a festival/tour package."""
    ev = {
        "id": "dgd",
        "name": "Dance Gavin Dance with Special Guests",
        "url": "https://www.ticketmaster.com/x",
        "dates": {"start": {"localDate": "2026-04-20"}},
        "_embedded": {
            "attractions": [{"name": f"A{i}"} for i in range(6)],
            "venues": [{"id": "KovZVenue3", "name": "Theater"}],
        },
    }
    kind, key, _ = classify_ticketmaster_event(ev)
    assert kind == "show"
    assert key is None


def test_festival_hint_in_presented_by_tail_only_is_show():
    ev = {
        "id": "es",
        "name": (
            "Enter Shikari: North America 2026 with Boston Manor presented by "
            "Thalia Hall and Riot Fest"
        ),
        "url": "https://www.ticketmaster.com/x",
        "dates": {"start": {"localDate": "2026-04-01"}},
        "_embedded": {
            "attractions": [{"name": "Enter Shikari"}, {"name": "Boston Manor"}],
            "venues": [{"id": "KovZVenue4", "name": "Thalia Hall"}],
        },
    }
    kind, key, _ = classify_ticketmaster_event(ev)
    assert kind == "show"
    assert key is None


def test_riot_fest_in_primary_title_is_festival():
    ev = {
        "id": "rf",
        "name": "Riot Fest 2026: Friday",
        "url": "https://www.ticketmaster.com/x",
        "dates": {"start": {"localDate": "2026-09-18"}},
        "_embedded": {
            "attractions": [{"name": "Band"}],
            "venues": [{"id": "KovZVenue5", "name": "Douglass Park"}],
        },
    }
    kind, key, _ = classify_ticketmaster_event(ev)
    assert kind == "festival"
    assert key is not None


def test_stable_festival_group_key_collapses_headliner_variants():
    base = {
        "dates": {"start": {"localDate": "2026-09-18"}},
        "_embedded": {"venues": [{"id": "KovZ91208", "name": "Highland Festival Grounds"}]},
    }
    ev1 = {**base, "id": "evt-a", "name": "Louder Than Life 2026: Metallica"}
    ev2 = {**base, "id": "evt-b", "name": "Louder Than Life 2026: Tool"}
    assert stable_festival_group_key(ev1) == stable_festival_group_key(ev2)
    assert stable_festival_group_key(ev1).startswith("tmfest:KovZ91208:2026:")


def test_merge_event_kind_prefers_festival():
    assert merge_event_kind("show", "festival") == "festival"
    assert merge_event_kind("festival", "tour_package") == "festival"
    assert merge_event_kind("tour_package", "show") == "tour_package"
