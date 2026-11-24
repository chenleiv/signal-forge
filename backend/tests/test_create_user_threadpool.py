"""Creating a user hashes with bcrypt off the event loop, like the password
reset, and a user created under the same name during the hash is kept: the
second create gets 409."""
from __future__ import annotations
import asyncio
import copy

import pytest

from tests.conftest import session_client

import user_admin
import users

NEW_USER = {"username": "threadpool-new", "display_name": "Threadpool New",
            "role": "analyst", "password": "threadpool-create-password-1"}


@pytest.fixture(autouse=True)
def _restore_users():
    saved = copy.deepcopy(users._users)
    yield
    users._users.clear()
    users._users.update(saved)


def test_create_user_hashes_off_the_event_loop(monkeypatch):
    on_event_loop: list[bool] = []
    real_hash = user_admin.hash_password

    def recording_hash(password: str) -> str:
        try:
            asyncio.get_running_loop()
            on_event_loop.append(True)
        except RuntimeError:          # no loop in this thread: a worker thread
            on_event_loop.append(False)
        return real_hash(password)

    monkeypatch.setattr(user_admin, "hash_password", recording_hash)
    r = session_client("admin", "admin").post("/api/users", json=NEW_USER)
    assert r.status_code in (200, 201), r.text
    assert on_event_loop == [False]
    assert users.authenticate(NEW_USER["username"], NEW_USER["password"]) is not None


def test_a_user_created_during_the_hash_is_not_overwritten(monkeypatch):
    real_hash = user_admin.hash_password
    first = {"username": NEW_USER["username"], "display_name": "First", "role": "analyst",
             "password_hash": "first-hash", "session_key": "first-key", "deleted_at": None}

    def hash_while_someone_else_creates(password: str) -> str:
        users._users[NEW_USER["username"]] = first
        return real_hash(password)

    monkeypatch.setattr(user_admin, "hash_password", hash_while_someone_else_creates)
    r = session_client("admin", "admin").post("/api/users", json=NEW_USER)
    assert r.status_code == 409, r.text
    assert users._users[NEW_USER["username"]] is first
    assert first["password_hash"] == "first-hash" and first["session_key"] == "first-key"


def test_a_taken_name_is_refused_before_any_hash(monkeypatch):
    calls: list[str] = []
    monkeypatch.setattr(user_admin, "hash_password", lambda p: calls.append(p) or "x")
    r = session_client("admin", "admin").post("/api/users", json={**NEW_USER, "username": "bob"})
    assert r.status_code == 409
    assert calls == []
