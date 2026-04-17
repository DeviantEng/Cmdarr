"""Middleware to add security headers to all responses.

Production CSP matches the Vite build (external scripts, no ``https:`` host wildcard).
For local dev with ``npm run dev`` (Vite HMR), set ``CMDARR_RELAXED_CSP=1`` so scripts may
use ``unsafe-inline`` / ``unsafe-eval`` and ``connect-src`` allows ``ws:`` / ``wss:``.

We omit ``upgrade-insecure-requests`` so plain-HTTP LAN access does not force HTTPS subresources
(ERR_SSL_PROTOCOL_ERROR). Terminate TLS at a reverse proxy for HTTPS when needed.
"""

import os

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request


def _trustworthy_origin_for_coop(request: Request) -> bool:
    """COOP is ignored on non-trustworthy origins (plain HTTP except localhost)."""
    if request.url.scheme == "https":
        return True
    host = (request.url.hostname or "").lower()
    if host in ("localhost", "127.0.0.1", "::1"):
        return True
    forwarded = (request.headers.get("x-forwarded-proto") or "").split(",")[0].strip().lower()
    if forwarded == "https":
        return True
    return False


def _relaxed_csp() -> str:
    """CSP for local dev (Vite HMR needs ws/wss, inline/eval). Set CMDARR_RELAXED_CSP=1."""
    return (
        "default-src 'self'; "
        "base-uri 'self'; "
        "form-action 'self'; "
        "frame-ancestors 'none'; "
        "object-src 'none'; "
        "script-src 'self' 'unsafe-inline' 'unsafe-eval'; "
        "style-src 'self' 'unsafe-inline'; "
        "img-src 'self' data: blob:; "
        "font-src 'self' data:; "
        "connect-src 'self' ws: wss:; "
        "worker-src 'self'; "
        "manifest-src 'self'; "
        "media-src 'self'; "
        "frame-src 'none'"
    )


def _strict_csp() -> str:
    """Default CSP for production builds (Vite emits external script + CSS only)."""
    return (
        "default-src 'self'; "
        "base-uri 'self'; "
        "form-action 'self'; "
        "frame-ancestors 'none'; "
        "object-src 'none'; "
        "script-src 'self'; "
        "style-src 'self' 'unsafe-inline'; "
        "img-src 'self' data: blob:; "
        "font-src 'self' data:; "
        "connect-src 'self'; "
        "worker-src 'self'; "
        "manifest-src 'self'; "
        "media-src 'self'; "
        "frame-src 'none'"
    )


def build_content_security_policy() -> str:
    relaxed = os.getenv("CMDARR_RELAXED_CSP", "").strip().lower() in (
        "1",
        "true",
        "yes",
        "on",
    )
    return _relaxed_csp() if relaxed else _strict_csp()


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Add X-Content-Type-Options, X-Frame-Options, Permissions-Policy, CSP, COOP/COEP/CORP."""

    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
        response.headers["Content-Security-Policy"] = build_content_security_policy()
        if _trustworthy_origin_for_coop(request):
            response.headers["Cross-Origin-Opener-Policy"] = "same-origin"
        response.headers["Cross-Origin-Embedder-Policy"] = "unsafe-none"
        # Allow cross-origin API use (e.g. Vite dev on :5173 → API :8080); header still present
        response.headers["Cross-Origin-Resource-Policy"] = "cross-origin"
        return response
