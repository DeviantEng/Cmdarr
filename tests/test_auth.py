"""Unit tests for auth utilities"""

from unittest.mock import patch

from app.auth import (
    _hash_api_key,
    _verify_api_key,
    is_setup_required,
)


def test_hash_api_key_deterministic():
    key = "test-api-key-123"
    h1 = _hash_api_key(key)
    h2 = _hash_api_key(key)
    assert h1 == h2
    assert len(h1) == 64
    assert all(c in "0123456789abcdef" for c in h1)


def test_verify_api_key_match():
    plain = "my-secret-key"
    hashed = _hash_api_key(plain)
    assert _verify_api_key(plain, hashed) is True


def test_verify_api_key_mismatch():
    hashed = _hash_api_key("correct-key")
    assert _verify_api_key("wrong-key", hashed) is False


def test_verify_api_key_empty_hash():
    assert not _verify_api_key("any", "")


@patch("app.auth.config_service")
def test_is_setup_required_when_empty(mock_config):
    mock_config.get.side_effect = lambda k, d="": "" if "USERNAME" in k or "PASSWORD" in k else d
    assert is_setup_required() is True


@patch("app.auth.config_service")
def test_is_setup_required_when_configured(mock_config):
    mock_config.get.side_effect = lambda k, d="": (
        "user" if "USERNAME" in k else ("hash" if "PASSWORD" in k else d)
    )
    assert is_setup_required() is False
