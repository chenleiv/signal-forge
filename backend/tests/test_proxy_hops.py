"""client_ip with separate hop counts for HTTP requests and WebSocket upgrades.

Measured on Render: HTTP requests carry 2 X-Forwarded-For entries, WebSocket
upgrades 1, so one hop count cannot fit both (docs/DECISIONS.md). Each row
below is one case of that analysis: which entry becomes the rate-limit key,
and whether a client can choose it by sending its own header."""
from __future__ import annotations

import os
import pathlib
import subprocess
import sys

import pytest
from starlette.requests import HTTPConnection

import rate_limit
from rate_limit import client_ip

BACKEND = pathlib.Path(__file__).resolve().parents[1]

C = "198.51.100.10"     # the real client, as the first proxy saw it
P = "203.0.113.20"      # the entry the second HTTP proxy appends
X = "6.6.6.6"           # a value the client wrote itself
PEER = "10.0.0.1"       # the TCP peer (Render's proxy): one key for everyone

HTTP_HONEST = [C, P]
HTTP_FORGED = [X, C, P]
WS_HONEST = [C]
WS_FORGED = [X, C]


def _conn(kind: str, entries: list[str]) -> HTTPConnection:
    headers = [(b"x-forwarded-for", ", ".join(entries).encode())] if entries else []
    return HTTPConnection({"type": kind, "path": "/", "headers": headers, "client": (PEER, 1234)})


def _hops(monkeypatch, http: int, ws: int) -> None:
    # raising=False: on code with a single TRUSTED_PROXY_HOPS the tests reach
    # their real assertions instead of failing on the missing name.
    monkeypatch.setattr(rate_limit, "TRUSTED_PROXY_HOPS_HTTP", http, raising=False)
    monkeypatch.setattr(rate_limit, "TRUSTED_PROXY_HOPS_WS", ws, raising=False)


# ── One value for both paths (what a single variable gives) ────

@pytest.mark.parametrize("kind, entries, hops, expected", [
    pytest.param("http", HTTP_HONEST, 3, PEER, id="http-honest-3-shared-peer"),
    pytest.param("http", HTTP_HONEST, 2, C, id="http-honest-2-client"),
    pytest.param("http", HTTP_HONEST, 1, P, id="http-honest-1-second-hop"),
    pytest.param("websocket", WS_HONEST, 3, PEER, id="ws-honest-3-shared-peer"),
    pytest.param("websocket", WS_HONEST, 2, PEER, id="ws-honest-2-shared-peer"),
    pytest.param("websocket", WS_HONEST, 1, C, id="ws-honest-1-client"),
    pytest.param("http", HTTP_FORGED, 3, X, id="http-forged-3-client-chooses"),
    pytest.param("http", HTTP_FORGED, 2, C, id="http-forged-2-client"),
    pytest.param("http", HTTP_FORGED, 1, P, id="http-forged-1-second-hop"),
    pytest.param("websocket", WS_FORGED, 2, X, id="ws-forged-2-client-chooses"),
    pytest.param("websocket", WS_FORGED, 1, C, id="ws-forged-1-client"),
])
def test_same_value_for_both_paths(monkeypatch, kind, entries, hops, expected):
    _hops(monkeypatch, http=hops, ws=hops)
    assert client_ip(_conn(kind, entries)) == expected


# ── Split values (the target: HTTP 2, WebSocket 1) ─────────────

@pytest.mark.parametrize("kind, entries", [
    ("http", HTTP_HONEST), ("http", HTTP_FORGED),
    ("websocket", WS_HONEST), ("websocket", WS_FORGED),
])
def test_split_values_key_every_case_on_the_real_client(monkeypatch, kind, entries):
    _hops(monkeypatch, http=2, ws=1)
    assert client_ip(_conn(kind, entries)) == C


def test_the_http_value_does_not_apply_to_websocket_upgrades(monkeypatch):
    _hops(monkeypatch, http=3, ws=1)
    assert client_ip(_conn("websocket", WS_FORGED)) == C


def test_the_websocket_value_does_not_apply_to_http_requests(monkeypatch):
    _hops(monkeypatch, http=1, ws=3)
    assert client_ip(_conn("http", HTTP_FORGED)) == P


# ── Zero hops: the header is ignored, never indexed ───────────

@pytest.mark.parametrize("kind, entries", [("http", HTTP_FORGED), ("websocket", WS_FORGED)])
def test_zero_hops_keys_on_the_socket_address(monkeypatch, kind, entries):
    # entries[-0] would be entries[0], the value the client wrote itself.
    _hops(monkeypatch, http=0, ws=0)
    key = client_ip(_conn(kind, entries))
    assert key == PEER
    assert key not in entries


# ── Reading the environment ───────────────────────────────────

@pytest.mark.parametrize("raw, expected", [(None, 1), ("", 1), ("  ", 1), ("0", 0), ("2", 2), (" 3 ", 3)])
def test_hops_from_env(monkeypatch, raw, expected):
    if raw is None:
        monkeypatch.delenv("TRUSTED_PROXY_HOPS_HTTP", raising=False)
    else:
        monkeypatch.setenv("TRUSTED_PROXY_HOPS_HTTP", raw)
    assert rate_limit._hops_from_env("TRUSTED_PROXY_HOPS_HTTP") == expected


@pytest.mark.parametrize("raw", ["-1", "abc", "1.5"])
def test_hops_from_env_rejects_invalid_values(monkeypatch, raw):
    monkeypatch.setenv("TRUSTED_PROXY_HOPS_WS", raw)
    with pytest.raises(RuntimeError, match="TRUSTED_PROXY_HOPS_WS must be a non-negative integer"):
        rate_limit._hops_from_env("TRUSTED_PROXY_HOPS_WS")


def _import_rate_limit(**env_vars: str) -> subprocess.CompletedProcess:
    env = {k: v for k, v in os.environ.items() if not k.startswith("TRUSTED_PROXY_HOPS")}
    env.update(env_vars, PYTHONPATH=str(BACKEND))
    probe = "import rate_limit as r; print(r.TRUSTED_PROXY_HOPS_HTTP, r.TRUSTED_PROXY_HOPS_WS)"
    return subprocess.run([sys.executable, "-c", probe], cwd=BACKEND / "tests", env=env,
                          capture_output=True, text=True, timeout=60)


def test_both_default_to_one():
    r = _import_rate_limit()
    assert r.returncode == 0, r.stderr[-2000:]
    assert r.stdout.split() == ["1", "1"]


def test_both_are_read_from_the_environment():
    r = _import_rate_limit(TRUSTED_PROXY_HOPS_HTTP="2", TRUSTED_PROXY_HOPS_WS="1")
    assert r.returncode == 0, r.stderr[-2000:]
    assert r.stdout.split() == ["2", "1"]


@pytest.mark.parametrize("value", ["3", "1", "0"])
def test_the_old_variable_refuses_startup(value):
    # Never a fallback: Render held 3, which would be unsafe on both paths.
    r = _import_rate_limit(TRUSTED_PROXY_HOPS=value)
    assert r.returncode != 0
    assert "TRUSTED_PROXY_HOPS was replaced by TRUSTED_PROXY_HOPS_HTTP and TRUSTED_PROXY_HOPS_WS" in r.stderr


def test_an_empty_old_variable_is_ignored():
    r = _import_rate_limit(TRUSTED_PROXY_HOPS="")
    assert r.returncode == 0, r.stderr[-2000:]
    assert r.stdout.split() == ["1", "1"]
