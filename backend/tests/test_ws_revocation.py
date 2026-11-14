"""An open WebSocket stream ends when its session does: logout, deletion,
role change and password resets close it with code 4001, and a ticket from an
ended session cannot open a new stream."""
from __future__ import annotations
import copy
import time
from datetime import datetime, timedelta, timezone

import jwt
import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from tests.conftest import ANALYST_PASSWORD, login, session_client

import main
import simulation
import users
from store import SECRET_KEY

NEW_PASSWORD = "ws-revocation-password-1"
# Enough frames to prove the stream would otherwise keep going (about 3 s).
MAX_FRAMES = 200
# Idle test: seconds with no events at all.
IDLE_WINDOW = 1.0


async def _fake_refresh(**_) -> None:
    simulation.THREAT_IPS = {"8.8.8.8": 90, "1.1.1.1": 70, "9.9.9.9": 50}


@pytest.fixture(autouse=True)
def _restore_users():
    saved = copy.deepcopy(users._users)
    yield
    users._users.clear()
    users._users.update(saved)


@pytest.fixture
def app_client(monkeypatch):
    """Runs the app's lifespan (the shared stream loop) with a fast stream and
    a short idle re-check."""
    monkeypatch.setattr(main, "refresh_threat_ips", _fake_refresh)
    monkeypatch.setattr(main, "STREAM_INTERVAL", (0.01, 0.02))
    monkeypatch.setattr(main, "WS_RECHECK_SECONDS", 0.05)
    with TestClient(main.app) as client:
        yield client


def _ticket(client: TestClient) -> str:
    r = client.get("/auth/ws-ticket")
    assert r.status_code == 200, r.text
    return r.json()["ticket"]


def _close_code(ws) -> int | None:
    """Read frames until the server closes; None if it never does."""
    try:
        for _ in range(MAX_FRAMES):
            ws.receive_json()
    except WebSocketDisconnect as exc:
        return exc.code
    return None


def _accepts(client: TestClient, ticket: str) -> bool:
    try:
        with client.websocket_connect(f"/ws/threats?ticket={ticket}"):
            return True
    except WebSocketDisconnect:
        return False


# ── Control ───────────────────────────────────────────────────

def test_valid_session_keeps_streaming(app_client):
    """Many re-check intervals pass and the stream stays open."""
    ticket = _ticket(login("alice"))
    with app_client.websocket_connect(f"/ws/threats?ticket={ticket}") as ws:
        for _ in range(40):
            assert "timestamp" in ws.receive_json()


def test_ticket_carries_the_session_claims(app_client):
    ticket = _ticket(login("alice"))
    claims = jwt.decode(ticket, SECRET_KEY, algorithms=["HS256"])
    assert claims["typ"] == "ws" and claims["sub"] == "alice" and claims["role"] == "analyst"
    assert claims["sk"] == users.get_user("alice")["session_key"]
    assert isinstance(claims["sid"], str) and claims["sid"]


# ── An open stream closes when its session ends ───────────────

def test_logout_closes_the_open_stream(app_client):
    user = login("alice")
    with app_client.websocket_connect(f"/ws/threats?ticket={_ticket(user)}") as ws:
        ws.receive_json()
        assert user.post("/auth/logout").status_code == 200
        assert _close_code(ws) == main.WS_SESSION_ENDED


def test_logout_of_another_session_keeps_this_stream(app_client):
    """Logout ends only its own session."""
    this, other = login("alice"), login("alice")
    with app_client.websocket_connect(f"/ws/threats?ticket={_ticket(this)}") as ws:
        ws.receive_json()
        assert other.post("/auth/logout").status_code == 200
        for _ in range(40):
            ws.receive_json()


@pytest.mark.parametrize("action", ["delete", "password_reset", "role_change"])
def test_admin_action_closes_the_users_stream(app_client, action):
    bob = login("bob")
    admin = session_client("admin", "admin")
    with app_client.websocket_connect(f"/ws/threats?ticket={_ticket(bob)}") as ws:
        ws.receive_json()
        if action == "delete":
            r = admin.delete("/api/users/bob")
        elif action == "password_reset":
            r = admin.patch("/api/users/bob", json={"password": NEW_PASSWORD})
        else:
            r = admin.patch("/api/users/bob", json={"role": "manager"})
        assert r.status_code == 200, r.text
        assert _close_code(ws) == main.WS_SESSION_ENDED


@pytest.mark.parametrize("action", ["delete", "password_reset"])
def test_busy_stream_is_closed_by_the_per_message_check(app_client, monkeypatch, action):
    """Events flowing and an idle re-check far beyond the frame cap's time
    (about 3 s): only the check before each send can close the stream. If it
    regresses, the cap is reached and the test fails instead of hanging."""
    monkeypatch.setattr(main, "WS_RECHECK_SECONDS", 30.0)
    bob = login("bob")
    admin = session_client("admin", "admin")
    with app_client.websocket_connect(f"/ws/threats?ticket={_ticket(bob)}") as ws:
        ws.receive_json()
        started = time.monotonic()
        if action == "delete":
            r = admin.delete("/api/users/bob")
        else:
            r = admin.patch("/api/users/bob", json={"password": NEW_PASSWORD})
        assert r.status_code == 200, r.text
        assert _close_code(ws) == main.WS_SESSION_ENDED
        assert time.monotonic() - started < 5.0


def test_own_password_change_closes_other_sessions_streams(app_client):
    streaming, changer = login("alice"), login("alice")
    with app_client.websocket_connect(f"/ws/threats?ticket={_ticket(streaming)}") as ws:
        ws.receive_json()
        r = changer.patch("/auth/me", json={"current_password": ANALYST_PASSWORD, "new_password": NEW_PASSWORD})
        assert r.status_code == 200, r.text
        assert _close_code(ws) == main.WS_SESSION_ENDED


def test_idle_stream_is_closed_by_the_periodic_recheck(app_client, monkeypatch):
    """No events for the first second: the timeout re-check alone must close
    the stream in that window. Events resume afterwards, so a broken re-check
    fails the timing assertion instead of hanging the suite."""
    real_generate, quiet_until = main.generate_threat, time.monotonic() + IDLE_WINDOW
    monkeypatch.setattr(main, "generate_threat",
                        lambda: None if time.monotonic() < quiet_until else real_generate())
    user = login("alice")
    with app_client.websocket_connect(f"/ws/threats?ticket={_ticket(user)}") as ws:
        assert user.post("/auth/logout").status_code == 200
        assert _close_code(ws) == main.WS_SESSION_ENDED
        assert time.monotonic() < quiet_until, "closed only after events resumed: idle re-check did not run"


# ── A ticket from an ended session cannot open a stream ───────

def test_ticket_minted_before_logout_is_rejected(app_client):
    user = login("alice")
    ticket = _ticket(user)
    assert user.post("/auth/logout").status_code == 200
    assert not _accepts(app_client, ticket)


def test_ticket_of_deleted_user_is_rejected(app_client):
    ticket = _ticket(login("bob"))
    assert session_client("admin", "admin").delete("/api/users/bob").status_code == 200
    assert not _accepts(app_client, ticket)


@pytest.mark.parametrize("missing", ["sid", "sk", "role"])
def test_crafted_ticket_without_session_claims_is_rejected(app_client, missing):
    """Signed and typed "ws" but without the session's revocation handles."""
    claims = {
        "sub": "alice", "role": "analyst", "typ": "ws",
        "sk": users.get_user("alice")["session_key"], "sid": "crafted-test-session-id",
        "exp": datetime.now(timezone.utc) + timedelta(minutes=5),
    }
    del claims[missing]
    assert not _accepts(app_client, jwt.encode(claims, SECRET_KEY, algorithm="HS256"))
