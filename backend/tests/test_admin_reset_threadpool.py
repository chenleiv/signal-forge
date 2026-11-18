"""An admin password reset hashes with bcrypt off the event loop, like the
self-service password change, so a reset does not pause every open request
and WebSocket stream while it hashes."""
from __future__ import annotations
import asyncio
import copy

import pytest

from tests.conftest import session_client

import user_admin
import users

NEW_PASSWORD = "threadpool-reset-password-1"


@pytest.fixture(autouse=True)
def _restore_users():
    saved = copy.deepcopy(users._users)
    yield
    users._users.clear()
    users._users.update(saved)


def test_admin_password_reset_hashes_off_the_event_loop(monkeypatch):
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
    r = session_client("admin", "admin").patch("/api/users/bob", json={"password": NEW_PASSWORD})
    assert r.status_code == 200, r.text
    assert on_event_loop == [False]
    assert users.authenticate("bob", NEW_PASSWORD) is not None


@pytest.mark.parametrize("change", ["deleted", "promoted"])
def test_reset_is_refused_if_the_user_changes_during_the_hash(monkeypatch, change):
    """A manager may reset only analysts. If the target is deleted or
    promoted while the hash runs, the permission check no longer holds: 409,
    and nothing about the user changes."""
    real_hash = user_admin.hash_password
    bob = users._users["bob"]

    def hash_while_user_changes(password: str) -> str:
        if change == "deleted":
            bob["deleted_at"] = "2026-11-18T00:00:00+00:00"
        else:
            bob["role"] = "manager"
        return real_hash(password)

    monkeypatch.setattr(user_admin, "hash_password", hash_while_user_changes)
    before = {k: bob[k] for k in ("password_hash", "session_key")}
    r = session_client("mira", "manager").patch("/api/users/bob", json={"password": NEW_PASSWORD})
    assert r.status_code == 409, r.text
    assert {k: bob[k] for k in ("password_hash", "session_key")} == before
