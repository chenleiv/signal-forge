"""Saved hunts: the creator is recorded, the list stays shared and shows it."""
from __future__ import annotations

import pytest

import store
from routers.hunting import MAX_SAVED_HUNTS, MAX_SAVED_HUNTS_PER_USER
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


# ── Delete: the creator or the admin ──────────────────────────

DENIED = {"detail": "Only the hunt's creator or an admin can delete this hunt"}


@pytest.mark.parametrize("caller,owner", [
    ("alice", "bob"),    # analyst, another user's hunt
    ("alice", None),     # analyst, no owner
    ("mira", "alice"),   # manager, another user's hunt
    ("mira", None),      # manager, no owner
])
def test_non_owner_cannot_delete(caller, owner):
    store._saved_hunts[:] = [_hunt("h1", owner)]
    before = [dict(h) for h in store._saved_hunts]
    r = _client(caller).delete("/api/hunts/h1")
    assert r.status_code == 403
    assert r.json() == DENIED
    assert store._saved_hunts == before


@pytest.mark.parametrize("caller,owner", [
    ("alice", "alice"),  # analyst, own hunt
    ("mira", "mira"),    # manager, own hunt
    ("admin", "bob"),    # admin, another user's hunt
    ("admin", None),     # admin, no owner
])
def test_owner_or_admin_can_delete(caller, owner):
    store._saved_hunts[:] = [_hunt("h1", owner), _hunt("h2", "bob")]
    r = _client(caller).delete("/api/hunts/h1")
    assert r.status_code == 200
    assert [h["id"] for h in store._saved_hunts] == ["h2"]


def test_delete_unknown_hunt_is_404():
    store._saved_hunts[:] = [_hunt("h1", "alice")]
    r = _client("alice").delete("/api/hunts/nope")
    assert r.status_code == 404
    assert r.json() == {"detail": "Saved hunt not found"}
    assert [h["id"] for h in store._saved_hunts] == ["h1"]


def _fill(owner: str | None, count: int, start: int = 0) -> None:
    store._saved_hunts.extend(_hunt(f"{owner}-{i}", owner) for i in range(start, start + count))


# ── Caps: per user and in total ───────────────────────────────

def test_per_user_cap():
    _fill("alice", MAX_SAVED_HUNTS_PER_USER)
    r = _client("alice").post("/api/hunts", json={"name": "one more"})
    assert r.status_code == 409
    assert r.json() == {"detail": f"You have {MAX_SAVED_HUNTS_PER_USER} saved hunts, the most allowed. "
                                  "Delete one of yours first"}
    assert len(store._saved_hunts) == MAX_SAVED_HUNTS_PER_USER


def test_per_user_cap_does_not_block_other_users():
    _fill("alice", MAX_SAVED_HUNTS_PER_USER)
    assert _client("bob").post("/api/hunts", json={"name": "b"}).status_code == 200


def test_deleting_one_of_yours_frees_a_place():
    _fill("alice", MAX_SAVED_HUNTS_PER_USER)
    assert _client("alice").delete("/api/hunts/alice-0").status_code == 200
    assert _client("alice").post("/api/hunts", json={"name": "again"}).status_code == 200


def test_one_user_cannot_fill_the_global_cap_alone():
    assert MAX_SAVED_HUNTS_PER_USER < MAX_SAVED_HUNTS
    alice = _client("alice")
    codes = [alice.post("/api/hunts", json={"name": f"a{i}"}).status_code for i in range(MAX_SAVED_HUNTS_PER_USER + 1)]
    assert codes == [200] * MAX_SAVED_HUNTS_PER_USER + [409]
    assert len(store._saved_hunts) == MAX_SAVED_HUNTS_PER_USER


def test_global_cap_message():
    _fill("bob", MAX_SAVED_HUNTS_PER_USER)
    _fill(None, MAX_SAVED_HUNTS - MAX_SAVED_HUNTS_PER_USER)
    r = _client("alice").post("/api/hunts", json={"name": "one more"})
    assert r.status_code == 409
    assert r.json() == {"detail": f"Saved hunts are limited to {MAX_SAVED_HUNTS} in total. "
                                  "Ask an admin to delete old ones"}
    assert len(store._saved_hunts) == MAX_SAVED_HUNTS


def test_delete_twice_is_404_the_second_time():
    _client("alice").post("/api/hunts", json={"name": "a"})
    hunt_id = store._saved_hunts[0]["id"]
    assert _client("alice").delete(f"/api/hunts/{hunt_id}").status_code == 200
    assert _client("alice").delete(f"/api/hunts/{hunt_id}").status_code == 404
