"""The WebSocket ticket travels as the first message, never in the URL.

A valid ticket gets {"type": "ready"}; a missing or wrong one closes with 4001;
no first message in time closes with 4408. The ticket is never logged."""
from __future__ import annotations

import json
import logging
import time
from datetime import datetime, timedelta, timezone

import jwt
import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

import main
import simulation
import users
from store import SECRET_KEY
from tests.conftest import login
from tests.ws_client import READY, WS_PATH, auth_message, open_stream

SHORT_TIMEOUT = 0.2


@pytest.fixture
def client():
    return TestClient(main.app)


@pytest.fixture
def short_timeout(monkeypatch):
    monkeypatch.setattr(main, "WS_AUTH_TIMEOUT_SECONDS", SHORT_TIMEOUT)


def _ticket() -> str:
    r = login("alice").get("/auth/ws-ticket")
    assert r.status_code == 200, r.text
    return r.json()["ticket"]


def _close_code(ws) -> int | None:
    try:
        ws.receive_json()
    except WebSocketDisconnect as exc:
        return exc.code
    return None


# ── Valid ticket ──────────────────────────────────────────────

def test_valid_ticket_gets_ready(client):
    with client.websocket_connect(WS_PATH) as ws:
        ws.send_json(auth_message(_ticket()))
        assert ws.receive_json() == READY


async def _fake_refresh(**_) -> None:
    simulation.THREAT_IPS = {"8.8.8.8": 90, "1.1.1.1": 70, "9.9.9.9": 50}


def test_valid_ticket_then_events(monkeypatch):
    monkeypatch.setattr(main, "refresh_threat_ips", _fake_refresh)
    monkeypatch.setattr(main, "STREAM_INTERVAL", (0.01, 0.02))
    with TestClient(main.app) as live:
        with open_stream(live, _ticket()) as ws:
            assert "timestamp" in ws.receive_json()


# ── Missing ticket ────────────────────────────────────────────

@pytest.mark.parametrize("send", [
    lambda ws: ws.send_json({"type": "auth"}),
    lambda ws: ws.send_json({"type": "auth", "ticket": None}),
    lambda ws: ws.send_json({"ticket": "x"}),
    lambda ws: ws.send_json(["auth"]),
    lambda ws: ws.send_text("not json"),
    lambda ws: ws.send_text(""),
    lambda ws: ws.send_bytes(b'{"type": "auth"}'),
], ids=["no-ticket", "null-ticket", "no-type", "not-an-object", "not-json", "empty", "binary"])
def test_missing_ticket_closes_with_4001(client, send):
    with client.websocket_connect(WS_PATH) as ws:
        send(ws)
        assert _close_code(ws) == main.WS_SESSION_ENDED


def test_oversized_first_message_closes_with_4001(client):
    ticket = _ticket()
    padded = json.dumps({"type": "auth", "ticket": ticket, "pad": "x" * main.WS_AUTH_MAX_CHARS})
    with client.websocket_connect(WS_PATH) as ws:
        ws.send_text(padded)
        assert _close_code(ws) == main.WS_SESSION_ENDED


# ── Wrong ticket ──────────────────────────────────────────────

def _crafted(**changes) -> str:
    claims = {
        "sub": "alice", "role": "analyst", "typ": "ws",
        "sk": users.get_user("alice")["session_key"], "sid": "crafted-test-session-id",
        "exp": datetime.now(timezone.utc) + timedelta(minutes=5),
    }
    key = changes.pop("key", SECRET_KEY)
    return jwt.encode({**claims, **changes}, key, algorithm="HS256")


@pytest.mark.parametrize("ticket", [
    lambda: "not-a-jwt",
    lambda: _crafted(key="attacker-guessed-key-of-a-valid-32-byte-length"),
    lambda: _crafted(exp=datetime.now(timezone.utc) - timedelta(seconds=1)),
    lambda: _crafted(typ="session"),
], ids=["garbage", "forged", "expired", "session-typed"])
def test_wrong_ticket_closes_with_4001(client, ticket):
    with client.websocket_connect(WS_PATH) as ws:
        ws.send_json(auth_message(ticket()))
        assert _close_code(ws) == main.WS_SESSION_ENDED


# ── Late ticket ───────────────────────────────────────────────

def test_no_first_message_closes_with_timeout_code(client, short_timeout):
    started = time.monotonic()
    with client.websocket_connect(WS_PATH) as ws:
        assert _close_code(ws) == main.WS_AUTH_TIMEOUT
    assert time.monotonic() - started < 2.0


def test_late_ticket_is_not_accepted(client, short_timeout):
    ticket = _ticket()
    with client.websocket_connect(WS_PATH) as ws:
        time.sleep(SHORT_TIMEOUT * 3)
        ws.send_json(auth_message(ticket))
        assert _close_code(ws) == main.WS_AUTH_TIMEOUT


def test_ticket_in_the_query_string_is_ignored(client, short_timeout):
    """The old URL form no longer authenticates: without a first message the
    socket times out even though the query carries a valid ticket."""
    with client.websocket_connect(f"{WS_PATH}?ticket={_ticket()}") as ws:
        assert _close_code(ws) == main.WS_AUTH_TIMEOUT


# ── Never logged ──────────────────────────────────────────────

def test_ticket_is_never_logged(client, caplog):
    valid = _ticket()
    forged = _crafted(key="attacker-guessed-key-of-a-valid-32-byte-length")
    caplog.set_level(logging.DEBUG)

    with client.websocket_connect(WS_PATH) as ws:
        ws.send_json(auth_message(valid))
        assert ws.receive_json() == READY
    with client.websocket_connect(WS_PATH) as ws:
        ws.send_json(auth_message(forged))
        assert _close_code(ws) == main.WS_SESSION_ENDED
    with client.websocket_connect(WS_PATH) as ws:
        ws.send_text(json.dumps({"type": "auth", "ticket": valid, "pad": "x" * main.WS_AUTH_MAX_CHARS}))
        assert _close_code(ws) == main.WS_SESSION_ENDED

    for record in caplog.records:
        text = record.getMessage() + repr(record.args) + (record.exc_text or "")
        for ticket in (valid, forged):
            assert ticket not in text, f"ticket logged by {record.name}"
