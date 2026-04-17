"""Unit tests for the TicketmasterClient._event_matches_artist heuristic.

These exercise the MBID-first rejection logic and the whole-phrase, token-aligned
name fallback, which together should block the category of false positives we saw
after 0.3.14-dev (e.g. TM returning an unrelated event whose attraction name was a
substring of 'Pop Evil' or contained the word 'Unprocessed' for unrelated reasons).
"""

from clients.client_ticketmaster import TicketmasterClient


def _match(ev, name, mbid=""):
    return TicketmasterClient._event_matches_artist(ev, name, mbid)


def test_mbid_match_accepts_event():
    ev = {
        "name": "Some Tour",
        "_embedded": {
            "attractions": [
                {
                    "name": "Pop Evil",
                    "externalLinks": {
                        "musicbrainz": [{"id": "0cc92e7d-09b6-49b7-92eb-6cfa6a7d2579"}]
                    },
                }
            ]
        },
    }
    assert _match(ev, "Pop Evil", "0cc92e7d-09b6-49b7-92eb-6cfa6a7d2579") is True


def test_mbid_mismatch_rejects_event_even_if_name_would_match():
    """TM-provided MBIDs are authoritative; name similarity does not rescue a wrong MBID."""
    ev = {
        "name": "Pop Evil - US Tour",
        "_embedded": {
            "attractions": [
                {
                    "name": "Pop Evil",
                    "externalLinks": {
                        "musicbrainz": [{"id": "deadbeef-0000-0000-0000-000000000000"}]
                    },
                }
            ]
        },
    }
    assert _match(ev, "Pop Evil", "0cc92e7d-09b6-49b7-92eb-6cfa6a7d2579") is False


def test_no_mbid_on_event_falls_back_to_whole_phrase_match():
    ev = {
        "name": "Pop Evil - US Tour",
        "_embedded": {"attractions": [{"name": "Pop Evil"}]},
    }
    assert _match(ev, "Pop Evil") is True
    assert _match(ev, "Pop Evil", "0cc92e7d-09b6-49b7-92eb-6cfa6a7d2579") is True


def test_attraction_name_substring_of_artist_is_rejected():
    """Previously `"pop" in "pop evil"` accepted an unrelated attraction. No longer."""
    ev = {
        "name": "Pop Extravaganza",
        "_embedded": {"attractions": [{"name": "Pop"}]},
    }
    assert _match(ev, "Pop Evil") is False


def test_partial_word_in_longer_attraction_name_is_rejected():
    """`unprocessed` as a substring of a longer attraction name must not match."""
    ev = {
        "name": "DJ Night",
        "_embedded": {"attractions": [{"name": "Unprocessedish Collective"}]},
    }
    assert _match(ev, "Unprocessed") is False


def test_whole_phrase_in_attraction_list_matches():
    ev = {
        "name": "Various - Night at the Club",
        "_embedded": {
            "attractions": [
                {"name": "Opening Act"},
                {"name": "Unprocessed"},
                {"name": "Headliner Extraordinaire"},
            ]
        },
    }
    assert _match(ev, "Unprocessed") is True


def test_event_with_no_attractions_falls_back_to_event_name_phrase():
    ev = {"name": "Unprocessed - Live in Chicago", "_embedded": {}}
    assert _match(ev, "Unprocessed") is True


def test_event_with_attractions_but_no_match_is_rejected_even_if_event_name_contains_artist():
    """Attractions are authoritative when present."""
    ev = {
        "name": "Unprocessed — Midwest Leg",
        "_embedded": {"attractions": [{"name": "Completely Different Band"}]},
    }
    assert _match(ev, "Unprocessed") is False


def test_empty_artist_name_rejects():
    ev = {"name": "Whatever", "_embedded": {}}
    assert _match(ev, "") is False
    assert _match(ev, "   ") is False


def test_multi_word_artist_name_must_match_as_contiguous_phrase():
    ev = {
        "name": "Pop and Evil Night",
        "_embedded": {"attractions": [{"name": "Pop and Evil Cover Band"}]},
    }
    assert _match(ev, "Pop Evil") is False
