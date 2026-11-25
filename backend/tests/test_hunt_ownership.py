"""Saved hunts: the creator is recorded, the list stays shared and shows it."""
from __future__ import annotations

import pytest

import store
from tests.conftest import session_client


@pytest.fixture(autouse=True)
def _keep_hunts():
    hunts = list(store._saved_hunts)
    store._saved_hunts.clear()
    yield
    store._saved_hunts[:] = hunts


def _client(username: str):
    role = {"admin": "admin", "mira": "manager"}.get(username, "analyst")
    return session_client(username, role)


def _hunt(hunt_id: str, created_by: str | None = None) -> dict:
    hunt = {"id": hunt_id, "name": "h", "query": {}, "created_at": "", "result_count": 0}
    if created_by is not None:
        hunt["created_by"] = created_by
    return hunt


# ── Owner is recorded and shown ───────────────────────────────

def test_save_records_the_caller_as_creator():
    r = _client("alice").post("/api/hunts", json={"name": "mine"})
    assert r.status_code == 200
    assert r.json()["created_by"] == "alice"
    assert store._saved_hunts[0]["created_by"] == "alice"


def test_list_is_shared_and_shows_every_creator():
    _client("alice").post("/api/hunts", json={"name": "a"})
    _client("bob").post("/api/hunts", json={"name": "b"})
    store._saved_hunts.append(_hunt("legacy"))
    hunts = _client("mira").get("/api/hunts").json()
    assert [(h["name"], h["created_by"]) for h in hunts] == [("b", "bob"), ("a", "alice"), ("h", None)]


def test_client_cannot_choose_the_creator():
    r = _client("alice").post("/api/hunts", json={"name": "h", "created_by": "bob"})
    assert r.status_code == 422
    assert store._saved_hunts == []
