"""Tests for scheduler timezone helpers."""

from datetime import UTC
from unittest.mock import patch

from utils.timezone import get_scheduler_timezone, get_utc_now


def test_get_scheduler_timezone_prefers_tz_env(monkeypatch):
    monkeypatch.setenv("TZ", "America/New_York")
    assert get_scheduler_timezone().key == "America/New_York"

    monkeypatch.delenv("TZ", raising=False)
    with patch("services.config_service.config_service.get", return_value="UTC"):
        assert get_scheduler_timezone().key == "UTC"


def test_get_scheduler_timezone_invalid_zone_falls_back_to_utc(monkeypatch):
    monkeypatch.delenv("TZ", raising=False)
    with patch("services.config_service.config_service.get", return_value="Not/A/Real/Zone"):
        assert get_scheduler_timezone() is UTC


def test_get_utc_now_is_timezone_aware():
    now = get_utc_now()
    assert now.tzinfo is not None
