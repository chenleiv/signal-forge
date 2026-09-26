"""Users and identity (RBAC phase 1): login, session claims, /auth/me, /api/users."""
import time

import pytest
from fastapi.testclient import TestClient
from jose import jwt

import main
from tests.conftest import ANALYST_PASSWORD
from store import SECRET_KEY

COOKIE = "sf_session"


@pytest.fixture
def client():
    return TestClient(main.app)


def _login(client, username, password):
    return client.post("/auth/login", json={"username": username, "password": password})


def test_login_puts_username_and_role_in_session(client):
    assert _login(client, "alice", ANALYST_PASSWORD).status_code == 200
    claims = jwt.decode(client.cookies.get(COOKIE), SECRET_KEY, algorithms=["HS256"])
    assert (claims["sub"], claims["role"], claims["typ"]) == ("alice", "analyst", "session")


def test_admin_logs_in_with_admin_password(client):
    assert _login(client, "admin", "test-admin-password").status_code == 200
    assert client.get("/auth/me").json() == {
        "username": "admin", "display_name": "Sarah Kim", "role": "admin",
    }


def test_old_hardcoded_credentials_no_longer_work(client):
    assert _login(client, "analyst", "signalforge").status_code == 401


def test_demo_passwords_do_not_work_outside_demo_mode(client):
    for username, password in [("admin", "admin-demo"), ("alice", "alice-demo")]:
        assert _login(client, username, password).status_code == 401


def test_unknown_user_and_wrong_password_look_identical(client):
    unknown = _login(client, "mallory", "whatever")
    wrong = _login(client, "alice", "wrong-password")
    assert unknown.status_code == wrong.status_code == 401
    assert unknown.json() == wrong.json()


def test_unknown_user_still_pays_for_bcrypt(client, monkeypatch):
    """Timing: the unknown-user path must run a real bcrypt check."""
    import users
    calls = []
    real = users.bcrypt.checkpw
    monkeypatch.setattr(users.bcrypt, "checkpw", lambda *a: calls.append(1) or real(*a))
    _login(client, "mallory", "whatever")
    assert calls == [1]


@pytest.mark.parametrize("body", [{}, {"username": ["alice"], "password": ANALYST_PASSWORD}, {"username": "alice", "password": None}])
def test_malformed_login_is_401(client, body):
    assert client.post("/auth/login", json=body).status_code == 401


def test_overlong_password_is_rejected_not_truncated(client, monkeypatch):
    """bcrypt only looks at 72 bytes: '<72-byte password>' + anything must not log in."""
    import users
    monkeypatch.setitem(users._users, "carol", {
        "username": "carol", "display_name": "Carol", "role": "analyst",
        "password_hash": users.hash_password("p" * 72),
    })
    assert _login(client, "carol", "p" * 72).status_code == 200
    assert _login(client, "carol", "p" * 72 + "anything").status_code == 401


def test_login_is_rate_limited(client):
    codes = [_login(client, "alice", "wrong").status_code for _ in range(6)]
    assert codes[:5] == [401] * 5
    assert codes[5] == 429


def test_users_list_never_exposes_hashes(client):
    _login(client, "alice", ANALYST_PASSWORD)
    body = client.get("/api/users").json()
    assert {u["username"] for u in body} >= {"admin", "alice", "bob"}
    for u in body:
        assert set(u) == {"username", "display_name", "role"}


def test_ws_ticket_carries_real_username(client):
    _login(client, "bob", ANALYST_PASSWORD)
    ticket = client.get("/auth/ws-ticket").json()["ticket"]
    assert jwt.decode(ticket, SECRET_KEY, algorithms=["HS256"])["sub"] == "bob"


def test_session_without_role_is_rejected(client):
    """Pre-RBAC session tokens (no role claim) must force a new login."""
    legacy = jwt.encode({"sub": "alice", "typ": "session", "exp": int(time.time()) + 300}, SECRET_KEY, algorithm="HS256")
    client.cookies.set(COOKIE, legacy)
    assert client.get("/auth/me").status_code == 401


def test_session_with_unknown_role_is_rejected(client):
    forged = jwt.encode({"sub": "alice", "role": "superuser", "typ": "session", "exp": int(time.time()) + 300}, SECRET_KEY, algorithm="HS256")
    client.cookies.set(COOKIE, forged)
    assert client.get("/api/stats").status_code == 401
