"""Unit tests for Similarr image helpers and Plex ranking."""

from datetime import datetime
from unittest.mock import patch
from zoneinfo import ZoneInfo

from utils.similarr_images import pick_deezer_image_url, pick_lastfm_image_url
from utils.similarr_plex import rank_plex_top_artists


def test_pick_lastfm_image_rejects_placeholder():
    images = [
        {
            "#text": "https://lastfm.freetls.fastly.net/i/u/300x300/2a96cbd8b46e442fc41c2b86b821562f.png",
            "size": "extralarge",
        }
    ]
    assert pick_lastfm_image_url(images) is None


def test_pick_lastfm_image_prefers_largest_real():
    images = [
        {"#text": "https://cdn.example/small.jpg", "size": "small"},
        {"#text": "https://cdn.example/mega.jpg", "size": "mega"},
        {"#text": "https://cdn.example/large.jpg", "size": "large"},
    ]
    assert pick_lastfm_image_url(images) == "https://cdn.example/mega.jpg"


def test_pick_deezer_image_prefers_xl():
    assert (
        pick_deezer_image_url(
            {
                "picture_medium": "https://cdn.example/m.jpg",
                "picture_xl": "https://cdn.example/xl.jpg",
            }
        )
        == "https://cdn.example/xl.jpg"
    )


def test_rank_plex_top_artists():
    tz = ZoneInfo("UTC")
    now = datetime(2026, 7, 27, 12, 0, tzinfo=tz)
    viewed = int(datetime(2026, 7, 17, 12, 0, tzinfo=tz).timestamp())
    history = [
        {"type": "track", "grandparentTitle": "Alpha", "viewedAt": viewed},
        {"type": "track", "grandparentTitle": "Alpha", "viewedAt": viewed},
        {"type": "track", "grandparentTitle": "Beta", "viewedAt": viewed},
        {"type": "album", "grandparentTitle": "Gamma", "viewedAt": viewed},
    ]
    with patch("utils.similarr_plex.get_scheduler_timezone", return_value=tz):
        ranked = rank_plex_top_artists(history, lookback_days=90, limit=10, now=now)
    assert ranked == [("Alpha", 2), ("Beta", 1)]
