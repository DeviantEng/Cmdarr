"""Unit tests for security headers middleware"""

from fastapi import FastAPI
from starlette.testclient import TestClient

from app.security_headers import SecurityHeadersMiddleware

app = FastAPI()
app.add_middleware(SecurityHeadersMiddleware)


@app.get("/test")
def _test_route():
    return {"ok": True}


def test_security_headers_added():
    client = TestClient(app)
    response = client.get("/test")
    assert response.status_code == 200
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["x-frame-options"] == "DENY"
    assert "permissions-policy" in response.headers
    assert "content-security-policy" in response.headers
    assert "default-src 'self'" in response.headers["content-security-policy"]


def test_security_headers_permissions_policy():
    client = TestClient(app)
    response = client.get("/test")
    policy = response.headers.get("permissions-policy", "")
    assert "camera=()" in policy
    assert "microphone=()" in policy
