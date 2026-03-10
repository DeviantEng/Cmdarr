"""
Access control: single user + API key.
- UI: session-based (cookie) after username/password login
- API: X-API-Key or Authorization: Bearer <api_key>
"""

import hashlib
import os
import secrets

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import APIKeyHeader, HTTPAuthorizationCredentials, HTTPBearer

from services.config_service import config_service

api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)
bearer_scheme = HTTPBearer(auto_error=False)


def _hash_password(password: str) -> str:
    from passlib.context import CryptContext

    pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
    return pwd_context.hash(password)


def _verify_password(plain: str, hashed: str) -> bool:
    from passlib.context import CryptContext

    pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
    return pwd_context.verify(plain, hashed)


def _hash_api_key(key: str) -> str:
    return hashlib.sha256(key.encode()).hexdigest()


def _verify_api_key(plain: str, hashed: str) -> bool:
    return hashed and _hash_api_key(plain) == hashed


def is_setup_required() -> bool:
    """True if no user has been configured (first run)."""
    username = config_service.get("CMDARR_AUTH_USERNAME", "")
    password_hash = config_service.get("CMDARR_AUTH_PASSWORD_HASH", "")
    return not (username and password_hash)


def apply_env_override():
    """
    If CMDARR_AUTH_USERNAME, CMDARR_AUTH_PASSWORD, or CMDARR_API_KEY env vars
    are set, overwrite DB. Enables password reset via docker env.
    """
    username = os.environ.get("CMDARR_AUTH_USERNAME", "").strip()
    password = os.environ.get("CMDARR_AUTH_PASSWORD", "").strip()
    api_key = os.environ.get("CMDARR_API_KEY", "").strip()

    if username:
        config_service.set("CMDARR_AUTH_USERNAME", username)
    if password:
        config_service.set("CMDARR_AUTH_PASSWORD_HASH", _hash_password(password))
    if api_key:
        config_service.set("CMDARR_API_KEY_HASH", _hash_api_key(api_key))


def verify_login(username: str, password: str) -> bool:
    """Verify username and password against stored credentials."""
    stored_user = config_service.get("CMDARR_AUTH_USERNAME", "")
    stored_hash = config_service.get("CMDARR_AUTH_PASSWORD_HASH", "")
    return (
        stored_user
        and stored_hash
        and username == stored_user
        and _verify_password(password, stored_hash)
    )


def generate_api_key() -> str:
    """Generate a new API key (plain). Caller hashes and stores it."""
    return secrets.token_urlsafe(32)


def set_api_key_from_plain(plain_key: str) -> None:
    """Store hashed API key from plain key."""
    config_service.set("CMDARR_API_KEY_HASH", _hash_api_key(plain_key))


async def get_current_user_from_session_or_api(
    request: Request,
    api_key: str | None = Depends(api_key_header),
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
) -> str | None:
    """
    Dependency: returns username if authenticated (session or API key), else None.
    Use for protected routes. Public routes (e.g. /health, /api/auth/*) skip this.
    """
    if is_setup_required():
        return None  # No auth required until setup

    # Check API key
    key_to_check = api_key or (credentials.credentials if credentials else None)
    if key_to_check:
        stored_hash = config_service.get("CMDARR_API_KEY_HASH", "")
        if _verify_api_key(key_to_check, stored_hash):
            return config_service.get("CMDARR_AUTH_USERNAME", "api")

    # Check session cookie
    session_id = request.cookies.get("cmdarr_session")
    if session_id and hasattr(request.app.state, "sessions"):
        sessions = getattr(request.app.state, "sessions", {})
        if session_id in sessions:
            return sessions[session_id]

    return None


async def require_auth(
    request: Request,
    api_key: str | None = Depends(api_key_header),
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
) -> str:
    """
    Dependency: raises 401 if not authenticated. Returns username.
    """
    user = await get_current_user_from_session_or_api(request, api_key, credentials)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user
