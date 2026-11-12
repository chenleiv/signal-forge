"""Security headers on every response, the SPA's CSP, HSTS over HTTPS only,
and the API docs switched off unless ENABLE_API_DOCS=true."""
from __future__ import annotations
import os
import pathlib
import re
import subprocess
import sys

import pytest
from fastapi.testclient import TestClient

import main
from security_headers import API_CSP, COMMON_HEADERS, HSTS, SPA_CSP
from tests.conftest import login

BACKEND = pathlib.Path(__file__).resolve().parents[1]
REPO = BACKEND.parent


def _assert_common(r):
    for name, value in COMMON_HEADERS.items():
        assert r.headers.get(name) == value, name


@pytest.fixture
def client():
    return TestClient(main.app)


# ── Present on every kind of response ─────────────────────────

def test_ok_response_has_the_headers():
    r = login().get("/api/alerts")
    assert r.status_code == 200
    _assert_common(r)
    assert r.headers["Content-Security-Policy"] == API_CSP
    assert r.headers["Cache-Control"] == "no-store"


def test_unauthenticated_response_has_the_headers(client):
    r = client.get("/api/alerts")
    assert r.status_code == 401
    _assert_common(r)
    assert r.headers["Content-Security-Policy"] == API_CSP


def test_not_found_response_has_the_headers():
    r = login().patch("/api/alerts/does-not-exist", json={"status": "acknowledged"})
    assert r.status_code == 404
    _assert_common(r)


def test_rate_limited_response_has_the_headers(client):
    body = {"username": "mallory", "password": "guess"}
    codes = [client.post("/auth/login", json=body) for _ in range(6)]
    assert codes[-1].status_code == 429
    _assert_common(codes[-1])
    assert codes[-1].headers["Cache-Control"] == "no-store"


def test_cors_preflight_has_the_headers(client):
    r = client.options("/api/alerts", headers={
        "Origin": "http://localhost:4200", "Access-Control-Request-Method": "GET",
    })
    assert r.status_code == 200
    _assert_common(r)


def test_health_has_the_headers(client):
    r = client.get("/health")
    _assert_common(r)
    assert r.headers["Cache-Control"] == "no-store"


# ── CSP ───────────────────────────────────────────────────────

def _directive(csp: str, name: str) -> str:
    match = re.search(rf"(?:^|;\s*){name}\s+([^;]*)", csp)
    assert match, f"{name} missing"
    return match.group(1)


def test_spa_csp_allows_no_inline_or_eval_scripts():
    scripts = _directive(SPA_CSP, "script-src")
    assert scripts == "'self'"
    assert _directive(SPA_CSP, "object-src") == "'none'"
    assert _directive(SPA_CSP, "frame-ancestors") == "'none'"
    assert _directive(SPA_CSP, "base-uri") == "'self'"


def test_api_csp_allows_nothing():
    assert _directive(API_CSP, "default-src") == "'none'"
    assert _directive(API_CSP, "frame-ancestors") == "'none'"


def test_spa_paths_get_the_spa_csp(client):
    r = client.get("/dashboard")  # index.html with a build, 404 without one
    _assert_common(r)
    assert r.headers["Content-Security-Policy"] == SPA_CSP
    assert r.headers.get("Cache-Control") != "no-store"


# ── HSTS ──────────────────────────────────────────────────────

def test_hsts_is_sent_behind_an_https_proxy(client):
    r = client.get("/health", headers={"X-Forwarded-Proto": "https"})
    assert r.headers["Strict-Transport-Security"] == HSTS
    assert "preload" not in HSTS and "includeSubDomains" in HSTS


def test_hsts_is_sent_on_direct_https():
    r = TestClient(main.app, base_url="https://testserver").get("/health")
    assert r.headers["Strict-Transport-Security"] == HSTS


def test_no_hsts_over_plain_http(client):
    assert "Strict-Transport-Security" not in client.get("/health").headers
    r = client.get("/health", headers={"X-Forwarded-Proto": "http"})
    assert "Strict-Transport-Security" not in r.headers


# ── API docs ──────────────────────────────────────────────────

@pytest.mark.parametrize("path", ["/docs", "/redoc", "/openapi.json"])
def test_api_docs_are_off_by_default(client, path):
    r = client.get(path)
    assert "swagger" not in r.text.lower()
    assert "redoc" not in r.text.lower()
    assert '"openapi"' not in r.text


def _docs_urls(value: str) -> list:
    env = {**os.environ, "ENABLE_API_DOCS": value, "PYTHONPATH": str(BACKEND)}
    probe = "import main; print(main.app.docs_url, main.app.redoc_url, main.app.openapi_url)"
    r = subprocess.run([sys.executable, "-c", probe], cwd=BACKEND / "tests", env=env,
                       capture_output=True, text=True, timeout=60)
    assert r.returncode == 0, r.stderr[-2000:]
    return r.stdout.strip().splitlines()[-1].split()


def test_api_docs_flag_turns_them_on():
    assert _docs_urls("true") == ["/docs", "/redoc", "/openapi.json"]


@pytest.mark.parametrize("value", ["", "false", "1", "yes"])
def test_api_docs_stay_off_for_any_other_value(value):
    assert _docs_urls(value) == ["None", "None", "None"]


# ── Built frontend ────────────────────────────────────────────

def _built_index() -> pathlib.Path | None:
    for path in (BACKEND / "static" / "index.html",
                 REPO / "frontend" / "dist" / "signal-forge" / "browser" / "index.html"):
        if path.is_file():
            return path
    return None


def test_source_index_has_no_inline_script():
    html = (REPO / "frontend" / "src" / "index.html").read_text()
    assert re.findall(r"<script(?![^>]*\bsrc=)[^>]*>", html) == []


def test_built_index_has_no_inline_script_or_handler():
    """The CSP forbids inline scripts and event handlers: a build that adds
    one (e.g. critical CSS inlining's onload) would break the page."""
    index = _built_index()
    if index is None:
        pytest.skip("no frontend build")
    html = index.read_text()
    assert re.findall(r"<script(?![^>]*\bsrc=)[^>]*>", html) == []
    assert re.findall(r"\son[a-z]+\s*=", html) == []
