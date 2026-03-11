"""Middleware to protect API routes when auth is configured."""

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

from app.auth import is_setup_required
from services.config_service import config_service


def _is_authenticated(request: Request) -> bool:
    """Check if request has valid session or API key."""
    if is_setup_required():
        return True  # No auth until setup

    # Check API key
    api_key = request.headers.get("X-API-Key") or request.headers.get("Authorization", "").replace(
        "Bearer ", ""
    )
    if api_key:
        from app.auth import _verify_api_key

        stored_hash = config_service.get("CMDARR_API_KEY_HASH", "")
        if _verify_api_key(api_key, stored_hash):
            return True

    # Check session
    session_id = request.cookies.get("cmdarr_session")
    if session_id and hasattr(request.app.state, "sessions"):
        if session_id in request.app.state.sessions:
            return True
    return False


def _is_public_path(path: str) -> bool:
    """Paths that don't require auth."""
    if path == "/health":
        return True
    if path.startswith("/api/auth/"):
        return True
    if path.startswith("/assets/"):
        return True
    # Frontend SPA routes - must be public so users can reach the login screen
    if path in ("/", "/config", "/status", "/import-lists", "/new-releases"):
        return True
    return False


class AuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if _is_public_path(request.url.path):
            return await call_next(request)
        if _is_authenticated(request):
            return await call_next(request)
        return JSONResponse(
            status_code=401,
            content={"detail": "Authentication required"},
            headers={"WWW-Authenticate": "Bearer"},
        )
