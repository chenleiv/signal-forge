"""The shared RBAC permission matrix (testing/permission-matrix.json), run
against the real API for every role: allow -> 2xx, deny -> 403 and nothing
changed. Runs twice: in-memory storage and a real database, so the two
storage paths cannot drift apart.

The frontend runs the same file through its client-side permission check
(permissions.matrix.spec.ts), so the two can never silently diverge.
"""
from __future__ import annotations
import json
import pathlib

import pytest

import copy

import store
import users
from tests.conftest import ANALYST_PASSWORD, session_client

MATRIX = json.loads(
    (pathlib.Path(__file__).resolve().parents[2] / "testing" / "permission-matrix.json").read_text()
)
PUBLIC_IP = "8.8.8.8"

# Who "self", "other" and "third" are for each role. A manager's "other" is
# an analyst, so "reset user password" exercises the one reset they may do.
PEOPLE = {
    "analyst": {"self": "alice", "other": "bob",   "third": "admin", "self_password": ANALYST_PASSWORD},
    "manager": {"self": "mira",  "other": "alice", "third": "bob",   "self_password": ANALYST_PASSWORD},
    "admin":   {"self": "admin", "other": "bob",   "third": "alice", "self_password": "test-admin-password"},
}


def _case_id(case: dict) -> str:
    owner = f" [{case['owner']}]" if case["owner"] else ""
    return f"{case['role']}: {case['action']}{owner}"


@pytest.fixture(autouse=True)
def _restore_state():
    snapshot = (list(store.incidents_store), list(store.alerts_store), [dict(r) for r in store._rules],
                list(store._saved_hunts), set(store._blocked_ips), dict(store._behavioral_config))
    saved_users = copy.deepcopy(users._users)
    yield
    users._users.clear(); users._users.update(saved_users)
    incidents, alerts, rules, hunts, blocked, behavioral = snapshot
    store.incidents_store.clear(); store.incidents_store.extend(incidents)
    store.alerts_store.clear(); store.alerts_store.extend(alerts)
    store._rules[:] = rules
    store._saved_hunts[:] = hunts
    store._blocked_ips.clear(); store._blocked_ips.update(blocked)
    store._behavioral_config.clear(); store._behavioral_config.update(behavioral)


@pytest.fixture(params=["memory", "database"])
def storage(request):
    """Each case runs with in-memory storage and with a real database."""
    if request.param == "database":
        request.getfixturevalue("db_app")
    return request.param


def _admin():
    return session_client("admin", "admin")


def _fixtures(owner_username: str | None) -> dict:
    """Create the objects the placeholders refer to through the API (so they
    land in whichever storage is active); return their ids."""
    store.incidents_store.clear()
    admin = _admin()
    incident = admin.post("/api/incidents/from-ip", json={"ip": "1.1.1.1"}).json()["id"]
    assert admin.patch(f"/api/incidents/{incident}", json={"assigned_to": owner_username}).status_code == 200
    rule = admin.post("/api/rules", json={"name": "matrix"}).json()["id"]
    hunt = admin.post("/api/hunts", json={"name": "h", "query": {}}).json()["id"]
    alert = store._create_alert("test", "SQLi", "high", "9.9.9.9", "matrix alert")["id"]   # alerts live in memory
    return {"incident": incident, "alert": alert, "rule": rule, "hunt": hunt, "ip": PUBLIC_IP}


def _fill(value, names: dict):
    if isinstance(value, str):
        for key, sub in names.items():
            value = value.replace("{" + key + "}", sub)
        return value
    if isinstance(value, dict):
        return {k: _fill(v, names) for k, v in value.items()}
    if isinstance(value, list):
        return [_fill(v, names) for v in value]
    return value


def test_matrix_covers_every_role_for_every_action():
    actions = {}
    for case in MATRIX["cases"]:
        actions.setdefault((case["action"], case["owner"]), set()).add(case["role"])
    assert all(roles == {"analyst", "manager", "admin"} for roles in actions.values())
    assert len(MATRIX["cases"]) >= 70


def _state() -> tuple:
    """Everything a write could change, read through the API for stored data
    (so it reflects memory or the database, whichever is active)."""
    admin = _admin()
    stored = tuple(admin.get(path).json() for path in ("/api/incidents", "/api/rules", "/api/behavioral/settings"))
    return stored + (copy.deepcopy(list(store.alerts_store)), copy.deepcopy(store._saved_hunts),
                     set(store._blocked_ips), copy.deepcopy(users._users))


@pytest.mark.parametrize("case", MATRIX["cases"], ids=_case_id)
def test_permission_matrix(case, storage):
    people = PEOPLE[case["role"]]
    owner = {"self": people["self"], "other": people["other"], "none": None, None: None}[case["owner"]]
    names = {**people, **_fixtures(owner)}
    client = session_client(people["self"], case["role"])
    before = _state()

    r = client.request(case["method"], _fill(case["path"], names), json=_fill(case["body"], names))

    if case["expect"] == "allow":
        assert 200 <= r.status_code < 300, f"expected success, got {r.status_code}: {r.text}"
    else:
        assert r.status_code == 403, f"expected 403, got {r.status_code}: {r.text}"
        assert _state() == before, "a denied request changed something"
