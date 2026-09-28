"""Self-service password change (RBAC phase 7): PATCH /auth/me.

Every user changes only their own password, and must prove they know the
current one. Other sessions are signed out; the session that made the
change keeps working.
"""
from __future__ import annotations
import copy

import pytest
from fastapi.testclient import TestClient

import main
import users
from tests.conftest import ANALYST_PASSWORD, login

NEW_PASSWORD = "a-brand-new-password-9"


@pytest.fixture(autouse=True)
def _restore_users():
    saved = copy.deepcopy(users._users)
    yield
    users._users.clear()
    users._users.update(saved)


def _change(client: TestClient, current: str, new: str = NEW_PASSWORD, **extra):
    return client.patch("/auth/me", json={"current_password": current, "new_password": new, **extra})


def _can_log_in(username: str, password: str) -> bool:
    r = TestClient(main.app).post("/auth/login", json={"username": username, "password": password})
    return r.status_code == 200


# ── The change ────────────────────────────────────────────────

@pytest.mark.parametrize("username,password", [
    ("alice", ANALYST_PASSWORD), ("mira", ANALYST_PASSWORD), ("admin", "test-admin-password"),
])
def test_every_role_changes_their_own_password(username, password):
    client = login(username, password)
    r = _change(client, password)
    assert r.status_code == 200
    assert r.json()["username"] == username
    assert not _can_log_in(username, password)
    assert _can_log_in(username, NEW_PASSWORD)


def test_other_sessions_are_signed_out_this_one_keeps_working():
    this = login("alice", ANALYST_PASSWORD)
    other = login("alice", ANALYST_PASSWORD)

    assert _change(this, ANALYST_PASSWORD).status_code == 200

    assert other.get("/auth/me").status_code == 401   # e.g. a stolen session
    assert this.get("/auth/me").status_code == 200    # fresh cookie for the changer


def test_the_change_only_touches_the_caller():
    bob_hash = users.get_user("bob")["password_hash"]
    _change(login("alice", ANALYST_PASSWORD), ANALYST_PASSWORD)
    assert users.get_user("bob")["password_hash"] == bob_hash


# ── Proving the current password ──────────────────────────────

def test_wrong_current_password_is_403_and_changes_nothing():
    client = login("alice", ANALYST_PASSWORD)
    r = _change(client, "not-my-password")
    assert r.status_code == 403 and r.json() == {"detail": "Current password is incorrect"}
    assert _can_log_in("alice", ANALYST_PASSWORD)
    assert client.get("/auth/me").status_code == 200   # not signed out either


def test_wrong_current_password_is_rate_limited_even_for_the_right_one():
    """A stolen session cannot brute-force the current password."""
    client = login("alice", ANALYST_PASSWORD)
    codes = [_change(client, f"guess-{i}").status_code for i in range(5)]
    assert codes == [403] * 5
    assert _change(client, ANALYST_PASSWORD).status_code == 429   # locked, even when correct
    assert _can_log_in("alice", ANALYST_PASSWORD)


def test_the_limit_is_per_user():
    alice = login("alice", ANALYST_PASSWORD)
    for i in range(5):
        _change(alice, f"guess-{i}")
    bob = login("bob", ANALYST_PASSWORD)
    assert _change(bob, ANALYST_PASSWORD).status_code == 200


# ── Narrow payload: nothing but the two passwords ─────────────

@pytest.mark.parametrize("extra", [
    {"role": "admin"}, {"username": "admin"}, {"display_name": "Boss"},
    {"session_key": "x"}, {"password_hash": "x"},
])
def test_no_other_field_is_accepted_not_even_ignored(extra):
    client = login("alice", ANALYST_PASSWORD)
    r = _change(client, ANALYST_PASSWORD, **extra)
    assert r.status_code == 422
    assert users.get_user("alice")["role"] == "analyst"
    assert _can_log_in("alice", ANALYST_PASSWORD)   # the password did not change either


@pytest.mark.parametrize("body", [
    {}, {"current_password": ANALYST_PASSWORD}, {"new_password": NEW_PASSWORD},
    {"current_password": ANALYST_PASSWORD, "new_password": 123456789012345},
    {"current_password": None, "new_password": NEW_PASSWORD},
])
def test_malformed_body_is_422(body):
    client = login("alice", ANALYST_PASSWORD)
    assert client.patch("/auth/me", json=body).status_code == 422
    assert _can_log_in("alice", ANALYST_PASSWORD)


@pytest.mark.parametrize("new", ["short", "x" * 73, ANALYST_PASSWORD])
def test_new_password_rules(new):
    """12-72 bytes (the same rule as everywhere), and different from the current one."""
    client = login("alice", ANALYST_PASSWORD)
    assert _change(client, ANALYST_PASSWORD, new).status_code == 422
    assert _can_log_in("alice", ANALYST_PASSWORD)


# ── Access ────────────────────────────────────────────────────

def test_needs_a_session():
    assert _change(TestClient(main.app), ANALYST_PASSWORD).status_code == 401


def test_demo_mode_blocks_it(monkeypatch):
    """The demo accounts' passwords are public: nobody may change them."""
    client = login("alice", ANALYST_PASSWORD)
    monkeypatch.setattr(main, "DEMO_MODE", True)
    r = _change(client, ANALYST_PASSWORD)
    assert r.status_code == 403 and r.json() == {"detail": "Read-only demo"}
    assert _can_log_in("alice", ANALYST_PASSWORD)
