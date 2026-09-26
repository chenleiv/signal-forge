"""The shared RBAC permission matrix (testing/permission-matrix.json), run
against the real API for both roles: allow -> 2xx, deny -> 403.

The frontend runs the same file through its client-side permission check
(permissions.matrix.spec.ts), so the two can never silently diverge.
"""
from __future__ import annotations
import json
import pathlib
from datetime import datetime, timezone

import pytest

import store
from tests.conftest import session_client

MATRIX = json.loads(
    (pathlib.Path(__file__).resolve().parents[2] / "testing" / "permission-matrix.json").read_text()
)
PUBLIC_IP = "8.8.8.8"

# Who "self", "other" and "third" are for each role.
PEOPLE = {
    "analyst": {"self": "alice", "other": "bob", "third": "admin"},
    "admin":   {"self": "admin", "other": "bob", "third": "alice"},
}


def _case_id(case: dict) -> str:
    owner = f" [{case['owner']}]" if case["owner"] else ""
    return f"{case['role']}: {case['action']}{owner}"


@pytest.fixture(autouse=True)
def _restore_state():
    snapshot = (list(store.incidents_store), list(store.alerts_store), [dict(r) for r in store._rules],
                list(store._saved_hunts), set(store._blocked_ips), dict(store._behavioral_config))
    yield
    incidents, alerts, rules, hunts, blocked, behavioral = snapshot
    store.incidents_store.clear(); store.incidents_store.extend(incidents)
    store.alerts_store.clear(); store.alerts_store.extend(alerts)
    store._rules[:] = rules
    store._saved_hunts[:] = hunts
    store._blocked_ips.clear(); store._blocked_ips.update(blocked)
    store._behavioral_config.clear(); store._behavioral_config.update(behavioral)


def _fixtures(owner_username: str | None) -> dict:
    """Create the objects the placeholders refer to; return their ids."""
    store.incidents_store.clear()
    now = datetime.now(timezone.utc).isoformat()
    store.incidents_store.appendleft({
        "id": "INC-M001", "title": "matrix", "severity": "high", "status": "open",
        "attack_type": "SQLi", "source_ip": "1.1.1.1", "source_region": "US",
        "event_count": 1, "assigned_to": owner_username, "created_at": now,
        "updated_at": now, "mitre_tags": [], "notes": [], "completed_tasks": [],
    })
    alert = store._create_alert("test", "SQLi", "high", "9.9.9.9", "matrix alert")
    rule = {"id": "rmatrix1", "name": "matrix", "enabled": True, "conditions": [], "logic": "AND",
            "actions": ["alert"], "created_at": now, "match_count": 0}
    store._rules.append(rule)
    store._saved_hunts.append({"id": "hmatrix1", "name": "h", "query": {}, "result_count": 0, "created_at": now})
    return {"incident": "INC-M001", "alert": alert["id"], "rule": rule["id"], "hunt": "hmatrix1", "ip": PUBLIC_IP}


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


def test_matrix_covers_both_roles_for_every_action():
    actions = {}
    for case in MATRIX["cases"]:
        actions.setdefault((case["action"], case["owner"]), set()).add(case["role"])
    assert all(roles == {"analyst", "admin"} for roles in actions.values())
    assert len(MATRIX["cases"]) >= 70


@pytest.mark.parametrize("case", MATRIX["cases"], ids=_case_id)
def test_permission_matrix(case):
    people = PEOPLE[case["role"]]
    owner = {"self": people["self"], "other": people["other"], "none": None, None: None}[case["owner"]]
    names = {**people, **_fixtures(owner)}
    client = session_client(people["self"], case["role"])

    r = client.request(case["method"], _fill(case["path"], names), json=_fill(case["body"], names))

    if case["expect"] == "allow":
        assert 200 <= r.status_code < 300, f"expected success, got {r.status_code}: {r.text}"
    else:
        assert r.status_code == 403, f"expected 403, got {r.status_code}: {r.text}"
