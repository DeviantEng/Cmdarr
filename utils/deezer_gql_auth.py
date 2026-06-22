"""Deezer Pipe GraphQL JWT acquisition from an ARL cookie."""

from __future__ import annotations

import json
import logging
import time
from base64 import urlsafe_b64decode

import aiohttp

logger = logging.getLogger("cmdarr.deezer_gql_auth")

AUTH_URL = "https://auth.deezer.com/login/arl"
JWT_REFRESH_MARGIN_SECONDS = 30


class DeezerGqlAuth:
    """Exchange a Deezer ARL cookie for short-lived JWT bearer tokens."""

    def __init__(self, arl: str, session: aiohttp.ClientSession | None = None) -> None:
        self._arl = (arl or "").strip()
        self._session = session
        self._owns_session = session is None
        self._jwt: str | None = None
        self._jwt_expires_at: float = 0.0

    def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None:
            self._session = aiohttp.ClientSession()
            self._owns_session = True
        return self._session

    async def close(self) -> None:
        if self._owns_session and self._session is not None:
            await self._session.close()
            self._session = None

    async def get_bearer_token(self) -> str | None:
        if not self._arl:
            return None
        now = time.time()
        if self._jwt and now < (self._jwt_expires_at - JWT_REFRESH_MARGIN_SECONDS):
            return self._jwt
        session = self._get_session()
        try:
            async with session.post(
                AUTH_URL,
                params={"jo": "p", "rto": "c", "i": "c"},
                cookies={"arl": self._arl},
                timeout=aiohttp.ClientTimeout(total=10),
            ) as resp:
                if resp.status != 200:
                    logger.warning("Deezer ARL auth failed with HTTP %s", resp.status)
                    return None
                text = await resp.text()
        except Exception as exc:
            logger.warning("Deezer ARL auth request failed: %s", exc)
            return None
        try:
            data = json.loads(text)
            jwt = data["jwt"]
        except (json.JSONDecodeError, KeyError, TypeError) as exc:
            logger.warning("Deezer ARL auth returned invalid payload: %s", exc)
            return None
        try:
            payload_segment = jwt.split(".")[1]
            padded = payload_segment + "=" * (-len(payload_segment) % 4)
            payload = json.loads(urlsafe_b64decode(padded))
            self._jwt_expires_at = float(payload["exp"])
        except IndexError, json.JSONDecodeError, KeyError, TypeError, ValueError:
            self._jwt_expires_at = now + 300
        self._jwt = jwt
        return self._jwt
