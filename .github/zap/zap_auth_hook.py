"""
ZAP scan hook: run setup flow before spidering so ZAP gets an authenticated session.

Cmdarr requires setup (create first user) before any authenticated routes are
accessible. This hook POSTs to /api/auth/setup with dummy credentials; the
response sets cmdarr_session cookie which ZAP stores and uses for subsequent
requests.
"""

import logging

logger = logging.getLogger(__name__)


def zap_started(zap, target):
    """Run setup request through ZAP so it captures the session cookie."""
    # Ensure target has no trailing slash for path concatenation
    base = target.rstrip("/")
    body = '{"username":"zap_user","password":"zap12345678"}'

    # Raw HTTP request - must use \\r\\n for line endings
    request = (
        f"POST /api/auth/setup HTTP/1.1\r\n"
        f"Host: {base.split('//')[1]}\r\n"
        f"Content-Type: application/json\r\n"
        f"Content-Length: {len(body)}\r\n"
        f"Connection: close\r\n"
        f"\r\n"
        f"{body}"
    )

    try:
        zap.core.send_request(request)
        logger.info("ZAP auth hook: setup request sent, session cookie should be set")
    except Exception as e:
        logger.warning("ZAP auth hook: setup request failed: %s", e)
