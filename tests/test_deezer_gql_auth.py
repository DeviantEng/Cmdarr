"""Unit tests for Deezer ARL → JWT auth helper."""

import json
import time
from base64 import urlsafe_b64encode

import pytest

from utils.deezer_gql_auth import DeezerGqlAuth


def _fake_jwt(exp: int) -> str:
    header = urlsafe_b64encode(json.dumps({"alg": "none"}).encode()).decode().rstrip("=")
    payload = urlsafe_b64encode(json.dumps({"exp": exp}).encode()).decode().rstrip("=")
    return f"{header}.{payload}.sig"


class _FakeResp:
    def __init__(self, status: int, text: str):
        self.status = status
        self._text = text

    async def text(self):
        return self._text

    async def __aenter__(self):
        return self

    async def __aexit__(self, *a):
        return False


class _FakeSession:
    def __init__(self, jwt: str):
        self.jwt = jwt
        self.post_calls = 0

    def post(self, *_a, **_kw):
        self.post_calls += 1
        return _FakeResp(200, json.dumps({"jwt": self.jwt}))

    async def close(self):
        return None


@pytest.mark.asyncio
async def test_get_bearer_token_acquires_and_reuses_jwt():
    exp = int(time.time()) + 600
    jwt = _fake_jwt(exp)
    session = _FakeSession(jwt)
    auth = DeezerGqlAuth("test-arl", session=session)

    token1 = await auth.get_bearer_token()
    token2 = await auth.get_bearer_token()

    assert token1 == jwt
    assert token2 == jwt
    assert session.post_calls == 1


@pytest.mark.asyncio
async def test_get_bearer_token_empty_arl_returns_none():
    auth = DeezerGqlAuth("")
    assert await auth.get_bearer_token() is None
