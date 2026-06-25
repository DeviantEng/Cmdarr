"""Tests for Plex account helper utilities."""

from utils.plex_user import get_account_name


def test_get_account_name_matches_id():
    accounts = [{"id": "1", "name": "Admin"}, {"id": "2", "name": "Guest"}]
    assert get_account_name(accounts, "2") == "Guest"
    assert get_account_name(accounts, "9") == "9"
