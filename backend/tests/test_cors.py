"""CORS: origins only from CORS_ORIGINS (none by default, nothing hardcoded),
exact methods and headers. conftest sets CORS_ORIGINS=http://localhost:4200."""
from __future__ import annotations
import os
import pathlib
import subprocess
import sys

import pytest
from fastapi.testclient import TestClient

import main

BACKEND = pathlib.Path(__file__).resolve().parents[1]
ALLOWED = "http://localhost:4200"


@pytest.fixture
def client():
    return TestClient(main.app)


def _preflight(client, origin, method="GET", headers=None):
    h = {"Origin": origin, "Access-Control-Request-Method": method}
    if headers:
        h["Access-Control-Request-Headers"] = headers
    return client.options("/api/alerts", headers=h)


def test_an_allowed_origin_gets_the_cors_headers(client):
    r = _preflight(client, ALLOWED, "PATCH", "content-type")
    assert r.status_code == 200
    assert r.headers["access-control-allow-origin"] == ALLOWED
    assert r.headers["access-control-allow-credentials"] == "true"
    assert set(r.headers["access-control-allow-methods"].split(", ")) == {"GET", "POST", "PATCH", "DELETE"}


@pytest.mark.parametrize("origin", [
    "https://signal-forge-tane.onrender.com",  # the deleted static site
    "https://evil.example",
    "http://localhost:4201",
    "null",
])
def test_other_origins_get_no_cors_headers(client, origin):
    r = _preflight(client, origin)
    assert r.status_code == 400
    assert "access-control-allow-origin" not in r.headers
    simple = client.get("/health", headers={"Origin": origin})
    assert "access-control-allow-origin" not in simple.headers


@pytest.mark.parametrize("method", ["PUT", "TRACE", "CONNECT"])
def test_methods_outside_the_list_are_refused(client, method):
    assert _preflight(client, ALLOWED, method).status_code == 400


def test_headers_outside_the_list_are_refused(client):
    assert _preflight(client, ALLOWED, "POST", "content-type, x-custom").status_code == 400
    assert _preflight(client, ALLOWED, "POST", "authorization").status_code == 400


@pytest.mark.parametrize("raw, expected", [
    ("", []),
    ("   ", []),
    ("https://a.example", ["https://a.example"]),
    (" https://a.example , http://localhost:4200 ,", ["https://a.example", "http://localhost:4200"]),
])
def test_origins_are_parsed(raw, expected):
    assert main._cors_origins(raw) == expected


@pytest.mark.parametrize("raw", [
    "*", "https://*.example", "https://a.example/", "https://a.example/path", "a.example",
    "ftp://a.example", "https://A.example", "https://a.example:99999x", "https://a.example,null",
])
def test_a_malformed_origin_stops_startup(raw):
    with pytest.raises(RuntimeError, match="CORS_ORIGINS"):
        main._cors_origins(raw)


def _wired(value: str | None) -> subprocess.CompletedProcess:
    env = {k: v for k, v in os.environ.items() if k != "CORS_ORIGINS"}
    env["PYTHONPATH"] = str(BACKEND)
    # Set explicitly (even to ""), so load_dotenv cannot fill it from a local .env.
    env["CORS_ORIGINS"] = "" if value is None else value
    probe = (
        "import main\n"
        "from fastapi.middleware.cors import CORSMiddleware\n"
        "m = [m for m in main.app.user_middleware if m.cls is CORSMiddleware][0]\n"
        "print(m.kwargs['allow_origins'], m.kwargs['allow_methods'], m.kwargs['allow_headers'])\n"
    )
    return subprocess.run([sys.executable, "-c", probe], cwd=BACKEND / "tests", env=env,
                          capture_output=True, text=True, timeout=60)


def test_no_origin_is_allowed_by_default():
    r = _wired(None)
    assert r.returncode == 0, r.stderr[-2000:]
    assert r.stdout.strip().splitlines()[-1] == "[] ['GET', 'POST', 'PATCH', 'DELETE'] ['Content-Type']"


def test_the_app_refuses_to_start_with_a_wildcard():
    r = _wired("*")
    assert r.returncode != 0
    assert "CORS_ORIGINS" in r.stderr
