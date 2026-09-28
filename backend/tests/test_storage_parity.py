"""Memory and database storage must behave the same: every flow runs in
both modes and is checked through the API only (what the UI would see)."""
from __future__ import annotations

import pytest

import store
from tests.conftest import session_client

PUBLIC_IP = "8.8.8.8"


@pytest.fixture(params=["memory", "database"])
def storage(request):
    saved = (list(store.incidents_store), [dict(r) for r in store._rules], dict(store._behavioral_config),
             list(store.alerts_store))
    store.incidents_store.clear()
    if request.param == "database":
        request.getfixturevalue("db_app")
    yield request.param
    incidents, rules, behavioral, alerts = saved
    store.incidents_store.clear(); store.incidents_store.extend(incidents)
    store._rules[:] = rules
    store._behavioral_config.clear(); store._behavioral_config.update(behavioral)
    store.alerts_store.clear(); store.alerts_store.extend(alerts)


@pytest.fixture
def alice():
    return session_client("alice", "analyst")


@pytest.fixture
def admin():
    return session_client("admin", "admin")


def _incident(client, inc_id: str) -> dict:
    return next(i for i in client.get("/api/incidents").json() if i["id"] == inc_id)


def test_case_lifecycle(storage, alice, admin):
    case = alice.post("/api/incidents/from-ip", json={"ip": PUBLIC_IP}).json()
    assert case["existing"] is False and case["assigned_to"] == "alice"

    again = admin.post("/api/incidents/from-ip", json={"ip": PUBLIC_IP}).json()
    assert again["id"] == case["id"] and again["existing"] is True   # one open case per IP

    assert alice.patch(f"/api/incidents/{case['id']}", json={"status": "investigating"}).status_code == 200
    note = alice.post(f"/api/incidents/{case['id']}/notes", json={"text": "  checked the logs  "}).json()
    assert set(note) == {"id", "text", "author", "at"}
    assert note["author"] == "alice" and note["text"] == "checked the logs"
    assert alice.patch(f"/api/incidents/{case['id']}/tasks", json={"completed_tasks": [2, 0]}).json() == {"completed_tasks": [2, 0]}

    seen = _incident(alice, case["id"])
    assert seen["status"] == "investigating"
    assert [n["text"] for n in seen["notes"]] == ["checked the logs"]
    assert sorted(seen["completed_tasks"]) == [0, 2]
    assert alice.get(f"/api/ip/{PUBLIC_IP}/case").json() == {"case_id": case["id"]}


def test_assignment_and_unknown_incident(storage, alice, admin):
    case = admin.post("/api/incidents/from-ip", json={"ip": PUBLIC_IP}).json()
    assert admin.patch(f"/api/incidents/{case['id']}", json={"assigned_to": None}).status_code == 200
    assert alice.patch(f"/api/incidents/{case['id']}", json={"assigned_to": "alice"}).status_code == 200   # take
    assert _incident(admin, case["id"])["assigned_to"] == "alice"
    for method, path, body in [
        ("PATCH", "/api/incidents/INC-NOPE", {"status": "open"}),
        ("POST", "/api/incidents/INC-NOPE/notes", {"text": "x"}),
        ("PATCH", "/api/incidents/INC-NOPE/tasks", {"completed_tasks": []}),
    ]:
        assert admin.request(method, path, json=body).status_code == 404


def test_closed_case_allows_a_new_one_for_the_same_ip(storage, admin):
    first = admin.post("/api/incidents/from-ip", json={"ip": PUBLIC_IP}).json()
    admin.patch(f"/api/incidents/{first['id']}", json={"status": "closed"})
    second = admin.post("/api/incidents/from-ip", json={"ip": PUBLIC_IP}).json()
    assert second["id"] != first["id"] and second["existing"] is False
    assert admin.get(f"/api/ip/{PUBLIC_IP}/case").json() == {"case_id": second["id"]}


def test_case_from_alert(storage, alice):
    alert = store._create_alert("test", "SQLi", "high", PUBLIC_IP, "test alert")
    case = alice.post(f"/api/alerts/{alert['id']}/case").json()
    assert case["assigned_to"] == "alice" and case["source_ip"] == PUBLIC_IP
    assert _incident(alice, case["id"])["id"] == case["id"]


def test_rules_crud(storage, admin):
    rule = admin.post("/api/rules", json={"name": "parity", "conditions": [], "actions": ["alert"]}).json()
    assert any(r["id"] == rule["id"] and r["name"] == "parity" for r in admin.get("/api/rules").json())

    updated = admin.patch(f"/api/rules/{rule['id']}", json={"enabled": False, "name": "renamed"}).json()
    assert (updated["enabled"], updated["name"]) == (False, "renamed")
    assert next(r for r in admin.get("/api/rules").json() if r["id"] == rule["id"])["enabled"] is False
    # the live detector reads the in-memory copy: it must follow in both modes
    assert next(r for r in store._rules if r["id"] == rule["id"])["enabled"] is False
    assert admin.patch("/api/rules/nope1234", json={"enabled": False}).status_code == 404

    assert admin.delete(f"/api/rules/{rule['id']}").status_code == 200
    assert all(r["id"] != rule["id"] for r in admin.get("/api/rules").json())
    assert all(r["id"] != rule["id"] for r in store._rules)


def test_behavioral_settings(storage, admin):
    assert admin.get("/api/behavioral/settings").json()["repeated_threshold"] == 8
    r = admin.patch("/api/behavioral/settings", json={"cooldown_min": 45})
    assert r.status_code == 200 and r.json()["cooldown_min"] == 45
    got = admin.get("/api/behavioral/settings").json()
    assert (got["cooldown_min"], got["repeated_threshold"], got["escalation_delta"]) == (45, 8, 20)
    assert store._behavioral_config["cooldown_min"] == 45   # the detector reads this copy


def test_a_write_on_a_reassigned_incident_is_refused(storage, admin, request):
    """Compare-and-set in both stores: a write whose permission check saw an
    older assignee is refused (the route answers 409)."""
    import asyncio
    import repositories
    from db_ops import StaleIncident

    case = admin.post("/api/incidents/from-ip", json={"ip": PUBLIC_IP}).json()   # assigned to admin

    async def stale_patch(session=None):
        return await repositories.incidents(session).patch(case["id"], {"status": "closed"}, expected_assignee="alice")

    with pytest.raises(StaleIncident):
        if storage == "database":
            request.getfixturevalue("db_app")(stale_patch)
        else:
            asyncio.run(stale_patch())
    assert _incident(admin, case["id"])["status"] == "open"
