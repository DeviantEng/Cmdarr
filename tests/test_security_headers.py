"""Unit tests for security headers middleware"""

from fastapi import FastAPI
from starlette.testclient import TestClient

from app.security_headers import SecurityHeadersMiddleware

app = FastAPI()
app.add_middleware(SecurityHeadersMiddleware)


@app.get("/test")
def _test_route():
    return {"ok": True}


def test_security_headers_added(monkeypatch):
    monkeypatch.delenv("CMDARR_RELAXED_CSP", raising=False)
    client = TestClient(app)
    response = client.get("/test")
    assert response.status_code == 200
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["x-frame-options"] == "DENY"
    assert "permissions-policy" in response.headers
    assert "content-security-policy" in response.headers
    csp = response.headers["content-security-policy"]
    assert "default-src 'self'" in csp
    assert "base-uri 'self'" in csp
    assert "form-action 'self'" in csp
    assert "object-src 'none'" in csp
    assert "frame-src 'none'" in csp
    assert "script-src 'self'" in csp
    assert "unsafe-eval" not in csp
    assert "https:" not in csp
    assert "upgrade-insecure-requests" not in csp
    # TestClient uses http://testserver — COOP omitted (non-trustworthy origin)
    assert "cross-origin-opener-policy" not in response.headers
    assert response.headers["cross-origin-embedder-policy"] == "unsafe-none"
    assert response.headers["cross-origin-resource-policy"] == "cross-origin"


def test_security_headers_permissions_policy(monkeypatch):
    monkeypatch.delenv("CMDARR_RELAXED_CSP", raising=False)
    client = TestClient(app)
    response = client.get("/test")
    policy = response.headers.get("permissions-policy", "")
    assert "camera=()" in policy
    assert "microphone=()" in policy


def test_coop_set_when_x_forwarded_proto_https(monkeypatch):
    """Behind TLS-terminating proxy, COOP applies."""
    monkeypatch.delenv("CMDARR_RELAXED_CSP", raising=False)
    app_https = FastAPI()
    app_https.add_middleware(SecurityHeadersMiddleware)

    @app_https.get("/t")
    def _t():
        return {}

    client = TestClient(app_https)
    r = client.get("/t", headers={"X-Forwarded-Proto": "https"})
    assert r.headers.get("cross-origin-opener-policy") == "same-origin"


def test_security_headers_relaxed_csp_when_env_set(monkeypatch):
    monkeypatch.setenv("CMDARR_RELAXED_CSP", "1")
    from app import security_headers

    csp = security_headers.build_content_security_policy()
    assert "unsafe-eval" in csp
    assert "ws:" in csp
