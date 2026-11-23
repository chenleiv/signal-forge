"""FastAPI's trailing-slash redirect is off (main.py, redirect_slashes=False).

With uvicorn --no-proxy-headers the scheme is http behind Render's proxy, so
the redirect would have pointed at http:// (docs/DECISIONS.md). A trailing
slash gets 404, or the SPA when backend/static exists; never a redirect."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

import main


def test_slash_redirects_are_off():
    assert main.app.router.redirect_slashes is False


@pytest.mark.parametrize("method, path", [
    ("GET", "/api/stats/"),
    ("GET", "/api/config/"),
    ("GET", "/health/"),
    ("POST", "/auth/login/"),
])
def test_trailing_slash_api_path_is_never_redirected(method, path):
    client = TestClient(main.app, follow_redirects=False)
    r = client.request(method, path, json={"username": "alice", "password": "x"} if method == "POST" else None)
    assert not 300 <= r.status_code < 400
    assert "location" not in r.headers
    if main._static.exists():
        # The SPA catch-all is GET-only: other methods get 405, not the route.
        assert r.status_code == (200 if method == "GET" else 405)
    else:
        assert r.status_code == 404
    assert "sf_session" not in r.cookies
