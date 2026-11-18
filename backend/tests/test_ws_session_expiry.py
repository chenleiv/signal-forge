"""An open WebSocket stream ends when its session token expires (8 hours),
not only on logout or revocation. The ticket carries the session's expiry
("sexp"); the handshake rejects a ticket without a usable one, and
/auth/ws-ticket never issues such a ticket.

Also measured here: deletion, password reset and role change close an idle
stream in the same time, one re-check interval at most."""
from __future__ import annotations
import copy
import time
from datetime import datetime, timedelta, timezone

import jwt
import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from tests.conftest import login, session_client
from tests.ws_client import open_stream, ws_accepts

import main
import sessions
import simulation
import users
from store import SECRET_KEY

COOKIE = "sf_session"
NEW_PASSWORD = "ws-expiry-password-1"
# Enough frames to prove a busy stream would otherwise keep going.
MAX_FRAMES = 200
# Expiry tests: the session ends this many seconds after the stream opens.
EXPIRES_IN = 0.5
# Upper bound for an expiry close; the idle re-check is far longer (30 s).
EXPIRY_DEADLINE = 2.0
# Timing test: idle re-check interval, and the slack allowed on top of it
# for the admin request and thread scheduling.
TIMING_RECHECK = 0.3
TIMING_SLACK = 0.7
# Timing test: no events for this long, then events resume so a broken
# re-check fails an assertion instead of hanging the suite.
TIMING_QUIET = 3.0


async def _fake_refresh(**_) -> None:
    simulation.THREAT_IPS = {"8.8.8.8": 90, "1.1.1.1": 70, "9.9.9.9": 50}


@pytest.fixture(autouse=True)
def _restore_users():
    saved = copy.deepcopy(users._users)
    yield
    users._users.clear()
    users._users.update(saved)


@pytest.fixture
def busy_client(monkeypatch):
    """The app's lifespan with a fast event stream and a 30 s idle re-check,
    so only the expiry can close a stream within the test's deadline."""
    monkeypatch.setattr(main, "refresh_threat_ips", _fake_refresh)
    monkeypatch.setattr(main, "STREAM_INTERVAL", (0.01, 0.02))
    monkeypatch.setattr(main, "WS_RECHECK_SECONDS", 30.0)
    with TestClient(main.app) as client:
        yield client


@pytest.fixture
def idle_client(monkeypatch):
    """No events until well past the expiry deadline and a 30 s idle
    re-check. Events resume afterwards, so a stream that ignores the expiry
    fails on the frame cap instead of hanging the suite."""
    monkeypatch.setattr(main, "refresh_threat_ips", _fake_refresh)
    monkeypatch.setattr(main, "STREAM_INTERVAL", (0.01, 0.02))
    monkeypatch.setattr(main, "WS_RECHECK_SECONDS", 30.0)
    real_generate = main.generate_threat
    quiet_until = time.monotonic() + EXPIRY_DEADLINE * 2
    monkeypatch.setattr(main, "generate_threat",
                        lambda: {} if time.monotonic() < quiet_until else real_generate())
    with TestClient(main.app) as client:
        yield client


def _ticket(**changes) -> str:
    """A ticket for alice, valid in every respect except what the test changes."""
    claims = {
        "sub": "alice", "role": "analyst", "typ": "ws",
        "sk": users.get_user("alice")["session_key"], "sid": sessions.new_session_id(),
        "exp": datetime.now(timezone.utc) + timedelta(minutes=5),
        "sexp": time.time() + 3600,
    }
    claims.update(changes)
    for key in [k for k, v in claims.items() if v is _DROP]:
        del claims[key]
    return jwt.encode(claims, SECRET_KEY, algorithm="HS256")


_DROP = object()


def _close_code(ws) -> int | None:
    """Read frames until the server closes; None if it never does."""
    try:
        for _ in range(MAX_FRAMES):
            ws.receive_json()
    except WebSocketDisconnect as exc:
        return exc.code
    return None


# ── Issuance ──────────────────────────────────────────────────

def test_ticket_carries_the_session_expiry():
    client = login("alice")
    session = jwt.decode(client.cookies[COOKIE], SECRET_KEY, algorithms=["HS256"])
    r = client.get("/auth/ws-ticket")
    assert r.status_code == 200, r.text
    ticket = jwt.decode(r.json()["ticket"], SECRET_KEY, algorithms=["HS256"])
    assert ticket["sexp"] == session["exp"]


def _session_cookie(**changes) -> TestClient:
    claims = {
        "sub": "alice", "role": "analyst", "typ": "session",
        "sk": users.get_user("alice")["session_key"], "sid": sessions.new_session_id(),
        "exp": datetime.now(timezone.utc) + timedelta(minutes=5),
    }
    claims.update(changes)
    for key in [k for k, v in claims.items() if v is _DROP]:
        del claims[key]
    client = TestClient(main.app)
    client.cookies.set(COOKIE, jwt.encode(claims, SECRET_KEY, algorithm="HS256"))
    return client


def test_control_session_with_expiry_gets_a_ticket():
    assert _session_cookie().get("/auth/ws-ticket").status_code == 200


def test_session_without_expiry_gets_no_ticket():
    """jwt.decode accepts a token with no "exp" at all; issuance must not hand
    out a ticket the handshake would reject."""
    r = _session_cookie(exp=_DROP).get("/auth/ws-ticket")
    assert r.status_code == 401
    assert "ticket" not in r.json()


# ── Handshake ─────────────────────────────────────────────────

def test_control_crafted_ticket_is_accepted(busy_client):
    assert ws_accepts(busy_client, _ticket())


@pytest.mark.parametrize("sexp", [
    lambda: time.time() - 1,
    lambda: _DROP,
    lambda: "4102444800",
    lambda: True,
    lambda: None,
], ids=["past", "missing", "string", "bool", "null"])
def test_ticket_without_a_live_session_expiry_is_rejected(busy_client, sexp):
    assert not ws_accepts(busy_client, _ticket(sexp=sexp()))


# ── An open stream closes at expiry ───────────────────────────

def test_expiry_closes_an_idle_stream(idle_client):
    """No events and a 30 s re-check: only the wait clamped to the expiry
    can close the stream this soon."""
    opened = time.monotonic()
    with open_stream(idle_client, _ticket(sexp=time.time() + EXPIRES_IN)) as ws:
        assert _close_code(ws) == main.WS_SESSION_ENDED
    elapsed = time.monotonic() - opened
    assert EXPIRES_IN * 0.8 <= elapsed < EXPIRY_DEADLINE, elapsed


def test_expiry_closes_a_busy_stream(busy_client):
    opened = time.monotonic()
    with open_stream(busy_client, _ticket(sexp=time.time() + EXPIRES_IN)) as ws:
        assert "timestamp" in ws.receive_json()   # events flowed before expiry
        assert _close_code(ws) == main.WS_SESSION_ENDED
    elapsed = time.monotonic() - opened
    assert EXPIRES_IN * 0.8 <= elapsed < EXPIRY_DEADLINE, elapsed


def test_session_not_yet_expired_stays_open(busy_client, monkeypatch):
    """Many re-check intervals pass and the stream stays open."""
    monkeypatch.setattr(main, "WS_RECHECK_SECONDS", 0.05)
    with open_stream(busy_client, _ticket(sexp=time.time() + 3600)) as ws:
        for _ in range(40):
            assert "timestamp" in ws.receive_json()


# ── Delete vs password reset vs role change ───────────────────

@pytest.fixture
def quiet_client(monkeypatch):
    """No events for TIMING_QUIET seconds, then events resume; idle re-check
    every TIMING_RECHECK seconds."""
    monkeypatch.setattr(main, "refresh_threat_ips", _fake_refresh)
    monkeypatch.setattr(main, "STREAM_INTERVAL", (0.01, 0.02))
    monkeypatch.setattr(main, "WS_RECHECK_SECONDS", TIMING_RECHECK)
    real_generate = main.generate_threat
    quiet_until = time.monotonic() + TIMING_QUIET
    monkeypatch.setattr(main, "generate_threat",
                        lambda: {} if time.monotonic() < quiet_until else real_generate())
    with TestClient(main.app) as client:
        yield client, quiet_until


@pytest.mark.parametrize("action", ["delete", "password_reset", "role_change"])
def test_admin_action_closes_an_idle_stream_within_one_recheck(quiet_client, action):
    """All three rotate the user's session key before responding, so the
    stream notices at its next idle re-check, whatever the action."""
    client, quiet_until = quiet_client
    bob = login("bob")
    admin = session_client("admin", "admin")
    with open_stream(client, bob.get("/auth/ws-ticket").json()["ticket"]) as ws:
        if action == "delete":
            r = admin.delete("/api/users/bob")
        elif action == "password_reset":
            r = admin.patch("/api/users/bob", json={"password": NEW_PASSWORD})
        else:
            r = admin.patch("/api/users/bob", json={"role": "manager"})
        assert r.status_code == 200, r.text
        acted = time.monotonic()
        assert _close_code(ws) == main.WS_SESSION_ENDED
        latency = time.monotonic() - acted
    assert time.monotonic() < quiet_until, "closed only after events resumed: idle re-check did not run"
    assert latency < TIMING_RECHECK + TIMING_SLACK, f"{action}: {latency:.3f}s"
