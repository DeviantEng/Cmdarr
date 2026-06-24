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


def test_public_spa_paths_do_not_require_auth():
    from app.auth_middleware import _requires_auth

    assert _requires_auth("/") is False
    assert _requires_auth("/commands") is False
    assert _requires_auth("/commands/add") is False
    assert _requires_auth("/commands/history") is False
    assert _requires_auth("/settings/application") is False
    assert _requires_auth("/system/status") is False


def test_api_and_import_list_paths_require_auth():
    from app.auth_middleware import _requires_auth

    assert _requires_auth("/api/commands") is True
    assert _requires_auth("/api/auth/status") is False
    assert _requires_auth("/import_lists/discovery_lastfm") is False
    assert _requires_auth("/import_lists/metrics") is True


def test_api_auth_routes_registered_before_spa_catchall():
    """Regression: SPA catch-all must not shadow /api/auth/* registered after it."""
    from pathlib import Path

    main_source = (Path(__file__).resolve().parents[1] / "app" / "main.py").read_text()
    auth_marker = 'app.include_router(auth_routes.router, prefix="/api/auth"'
    commands_marker = 'app.include_router(commands.router, prefix="/api/commands"'
    catchall_marker = "async def react_spa_fallback"

    assert auth_marker in main_source
    assert commands_marker in main_source
    assert catchall_marker in main_source
    assert main_source.index(auth_marker) < main_source.index(catchall_marker)
    assert main_source.index(commands_marker) < main_source.index(catchall_marker)

    lifespan_block = main_source.split("async def lifespan", 1)[1].split("\n\n    yield", 1)[0]
    assert auth_marker not in lifespan_block
    assert commands_marker not in lifespan_block
