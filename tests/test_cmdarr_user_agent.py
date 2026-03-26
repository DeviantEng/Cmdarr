"""Unit tests for utils/cmdarr_user_agent.py."""

from __version__ import __version__
from services.config_service import _CONFIG_KEYS_SKIP_ENV
from utils.cmdarr_user_agent import (
    DEFAULT_CMDARR_USER_AGENT,
    resolve_cmdarr_user_agent,
)


def test_default_constant_matches_version():
    assert __version__ in DEFAULT_CMDARR_USER_AGENT
    assert "github.com/DeviantEng/Cmdarr" in DEFAULT_CMDARR_USER_AGENT


def test_resolve_empty_config_attribute():
    class C:
        CMDARR_USER_AGENT = ""

    assert resolve_cmdarr_user_agent(C()) == DEFAULT_CMDARR_USER_AGENT


def test_resolve_custom_string():
    class C:
        CMDARR_USER_AGENT = "Cmdarr (https://github.com/DeviantEng/Cmdarr)"

    assert resolve_cmdarr_user_agent(C()) == "Cmdarr (https://github.com/DeviantEng/Cmdarr)"


def test_resolve_dict():
    assert (
        resolve_cmdarr_user_agent({"CMDARR_USER_AGENT": "Custom/1 (+https://x)"})
        == "Custom/1 (+https://x)"
    )
    assert resolve_cmdarr_user_agent({}) == DEFAULT_CMDARR_USER_AGENT


def test_cmdarr_user_agent_not_env_driven():
    """Docker/OS env must not override CMDARR_USER_AGENT (identity stays consistent per install)."""
    assert "CMDARR_USER_AGENT" in _CONFIG_KEYS_SKIP_ENV
