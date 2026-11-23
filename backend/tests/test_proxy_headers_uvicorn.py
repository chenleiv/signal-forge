"""What uvicorn's proxy headers handling does to scope["client"] and
scope["scheme"], with FORWARDED_ALLOW_IPS='*' as on Render, with and without
--no-proxy-headers (the Render start command and e2e/serve.mjs pass it).

Measured on Render: a forged "X-Forwarded-For: 203.0.113.9" showed up in the
access log as client 203.0.113.9:0. This runs a real uvicorn so an upgrade
that changes this behaviour fails here. Like test_ws_max_size_uvicorn.py, it
does not prove the deployed start command has the flag (docs/DECISIONS.md)."""
from __future__ import annotations

import os
import pathlib
import socket
import subprocess
import sys
import time

import httpx
import pytest

BACKEND = pathlib.Path(__file__).resolve().parent.parent
FORGED = "203.0.113.9"
HEADERS = {"X-Forwarded-For": FORGED, "X-Forwarded-Proto": "https"}


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


class _Server:
    def __init__(self, url: str, log: pathlib.Path):
        self.url = url
        self.log = log

    def access_log(self) -> str:
        return self.log.read_text(errors="replace")


@pytest.fixture(scope="module", params=[False, True], ids=["proxy-headers", "no-proxy-headers"])
def server(request, tmp_path_factory):
    flag = request.param
    port = _free_port()
    log = tmp_path_factory.mktemp("uvicorn") / "output.log"
    args = [sys.executable, "-m", "uvicorn", "tests._scope_echo_app:app",
            "--host", "127.0.0.1", "--port", str(port), "--log-level", "info"]
    if flag:
        args.append("--no-proxy-headers")
    env = {**os.environ, "FORWARDED_ALLOW_IPS": "*"}
    # The access log goes to stdout, the startup lines to stderr.
    with log.open("wb") as out:
        proc = subprocess.Popen(args, cwd=BACKEND, env=env, stdout=out, stderr=subprocess.STDOUT)
    try:
        deadline = time.monotonic() + 15
        while True:
            try:
                httpx.get(f"http://127.0.0.1:{port}/api/echo", timeout=1)
                break
            except httpx.HTTPError:
                pass
            if time.monotonic() > deadline or proc.poll() is not None:
                pytest.fail("uvicorn did not start")
            time.sleep(0.1)
        yield flag, _Server(f"http://127.0.0.1:{port}", log)
    finally:
        proc.terminate()
        proc.wait(10)


def _get(server: _Server, path: str) -> httpx.Response:
    return httpx.get(server.url + path, headers=HEADERS, follow_redirects=False, timeout=5)


def test_client_and_scheme(server):
    flag, srv = server
    body = _get(srv, "/api/echo").json()
    if flag:
        assert body["client"][0] == "127.0.0.1"   # the real TCP peer
        assert body["scheme"] == "http"
    else:
        assert body["client"] == [FORGED, 0]      # leftmost, client-chosen entry
        assert body["scheme"] == "https"


def test_access_log_shows_the_forged_address_only_without_the_flag(server):
    flag, srv = server
    _get(srv, "/api/echo?access-log")
    deadline = time.monotonic() + 5
    while "/api/echo?access-log" not in (log := srv.access_log()):
        if time.monotonic() > deadline:
            pytest.fail("no access log line")
        time.sleep(0.05)
    assert (FORGED in log) is not flag


def test_trailing_slash_is_never_redirected(server):
    # redirect_slashes=False, as in main.py: 404 without backend/static.
    _, srv = server
    r = _get(srv, "/api/echo/")
    assert r.status_code == 404
    assert "location" not in r.headers


def test_default_slash_redirect_would_point_at_http_with_the_flag(server):
    # Why main.py turns slash redirects off: with the flag the redirect is
    # built from the scheme the proxy used to reach us, not the browser's.
    flag, srv = server
    r = _get(srv, "/default-slashes/api/echo/")
    assert r.status_code == 307
    assert r.headers["location"].startswith("http://" if flag else "https://")
