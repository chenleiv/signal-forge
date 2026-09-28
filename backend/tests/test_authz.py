"""Authorization (RBAC phase 2): the permission matrix, for both roles.

Allowed -> 2xx, denied -> 403. "own" = incident.assigned_to == the caller.
"""
from __future__ import annotations
from datetime import datetime, timezone

import pytest

import main
import store
from tests.conftest import session_client

PUBLIC_IP = "8.8.8.8"


_client = session_client


@pytest.fixture(autouse=True)
def _restore_stores():
    """These tests mutate shared in-memory state; leave it as found."""
    incidents, alerts = list(store.incidents_store), list(store.alerts_store)
    yield
    store.incidents_store.clear()
    store.incidents_store.extend(incidents)
    store.alerts_store.clear()
    store.alerts_store.extend(alerts)


@pytest.fixture
def alice():
    return _client("alice", "analyst")


@pytest.fixture
def bob():
    return _client("bob", "analyst")


@pytest.fixture
def admin():
    return _client("admin", "admin")


@pytest.fixture
def incident():
    """Factory: put an incident with a given assignee in the in-memory store."""
    created = []

    def make(assigned_to: str | None, status: str = "open") -> str:
        inc_id = f"INC-T{len(created) + 1:03d}"
        now = datetime.now(timezone.utc).isoformat()
        store.incidents_store.appendleft({
            "id": inc_id, "title": "t", "severity": "high", "status": status,
            "attack_type": "SQLi", "source_ip": PUBLIC_IP, "source_region": "US",
            "event_count": 1, "assigned_to": assigned_to, "created_at": now,
            "updated_at": now, "mitre_tags": [], "notes": [], "completed_tasks": [],
        })
        created.append(inc_id)
        return inc_id

    yield make
    for inc in [i for i in store.incidents_store if i["id"] in created]:
        store.incidents_store.remove(inc)


def _current(inc_id: str) -> dict:
    return next(i for i in store.incidents_store if i["id"] == inc_id)


# ── Working on an incident ────────────────────────────────────
# Who may work on which incident (and that a denial writes nothing) is the
# shared permission matrix (test_permission_matrix.py); these are the edges.

def test_denial_message_is_clear_and_not_leaky(alice, incident):
    r = alice.patch(f"/api/incidents/{incident('bob')}", json={"status": "closed"})
    assert r.json() == {"detail": "Only the assignee, a manager or an admin can change this incident"}


# ── Assignment ────────────────────────────────────────────────

def test_analyst_takes_unassigned_incident(alice, incident):
    inc = incident(None)
    assert alice.patch(f"/api/incidents/{inc}", json={"assigned_to": "alice"}).status_code == 200
    assert _current(inc)["assigned_to"] == "alice"


@pytest.mark.parametrize("owner,new", [
    ("bob", "alice"),   # take someone else's incident
    (None, "bob"),      # assign an unassigned incident to someone else
    ("alice", "bob"),   # hand own incident to someone else
    ("alice", None),    # unassign own incident
    ("bob", None),      # unassign someone else's
])
def test_analyst_cannot_assign(alice, incident, owner, new):
    inc = incident(owner)
    assert alice.patch(f"/api/incidents/{inc}", json={"assigned_to": new}).status_code == 403
    assert _current(inc)["assigned_to"] == owner


@pytest.mark.parametrize("new", ["mallory", "Alice Chen", 42, ["alice"]])
def test_assign_to_unknown_user_is_422(admin, incident, new):
    inc = incident(None)
    assert admin.patch(f"/api/incidents/{inc}", json={"assigned_to": new}).status_code == 422
    assert _current(inc)["assigned_to"] is None


def test_unchanged_assignee_is_a_no_op(alice, incident):
    """Clients may send the whole object back; that alone is not a reassignment."""
    inc = incident("bob")
    assert alice.patch(f"/api/incidents/{inc}", json={"assigned_to": "bob"}).status_code == 200


def test_unchanged_assignee_does_not_smuggle_a_status_change(alice, incident):
    inc = incident("bob", status="open")
    r = alice.patch(f"/api/incidents/{inc}", json={"assigned_to": "bob", "status": "closed"})
    assert r.status_code == 403
    assert _current(inc)["status"] == "open"


def test_owner_cannot_smuggle_a_reassignment_with_a_status_change(alice, incident):
    """Status is allowed for the owner; handing the incident away is not."""
    inc = incident("alice", status="open")
    r = alice.patch(f"/api/incidents/{inc}", json={"status": "closed", "assigned_to": "bob"})
    assert r.status_code == 403
    assert (_current(inc)["status"], _current(inc)["assigned_to"]) == ("open", "alice")


def test_take_and_status_change_together_is_denied(alice, incident):
    """Fields are checked against the CURRENT state: not yet the assignee."""
    inc = incident(None)
    r = alice.patch(f"/api/incidents/{inc}", json={"assigned_to": "alice", "status": "closed"})
    assert r.status_code == 403
    assert _current(inc)["assigned_to"] is None


# ── Input validation ──────────────────────────────────────────

@pytest.mark.parametrize("status", ["pwned", "", None, "OPEN", ["open"]])
def test_invalid_status_is_422(admin, incident, status):
    inc = incident("admin")
    assert admin.patch(f"/api/incidents/{inc}", json={"status": status}).status_code == 422
    assert _current(inc)["status"] == "open"


def test_unknown_incident_is_404(admin):
    assert admin.patch("/api/incidents/INC-NOPE", json={"status": "open"}).status_code == 404


@pytest.mark.parametrize("ip", ["127.0.0.1", "169.254.169.254", "10.0.0.1", "localhost", 2130706433, 134744072, None, "unknown"])
def test_case_from_ip_rejects_internal_or_invalid_ips(alice, ip):
    assert alice.post("/api/incidents/from-ip", json={"ip": ip}).status_code == 422


# ── Cases: any user, auto-assigned to the creator ─────────────

def test_case_from_ip_is_assigned_to_creator(bob):
    store.incidents_store.clear()
    r = bob.post("/api/incidents/from-ip", json={"ip": PUBLIC_IP})
    assert r.status_code == 200
    assert r.json()["assigned_to"] == "bob"


def test_existing_open_case_is_returned_unchanged(alice, bob):
    store.incidents_store.clear()
    first = alice.post("/api/incidents/from-ip", json={"ip": PUBLIC_IP}).json()
    again = bob.post("/api/incidents/from-ip", json={"ip": PUBLIC_IP}).json()
    assert again["id"] == first["id"] and again["existing"] is True
    assert again["assigned_to"] == "alice"


def test_case_from_alert_is_assigned_to_creator(bob):
    store.incidents_store.clear()
    store.alerts_store.clear()
    alert = store._create_alert("test", "SQLi", "high", PUBLIC_IP, "test alert")
    r = bob.post(f"/api/alerts/{alert['id']}/case")
    assert r.status_code == 200
    assert r.json()["assigned_to"] == "bob"


# ── Admin-only configuration ──────────────────────────────────

ADMIN_ONLY = [
    ("POST", "/api/rules", {"name": "r"}),
    ("PATCH", "/api/rules/{rule}", {"enabled": False}),
    ("DELETE", "/api/rules/{rule}", None),
    ("PATCH", "/api/behavioral/settings", {"cooldown_min": 30}),
]


@pytest.fixture
def rule(admin):
    r = admin.post("/api/rules", json={"name": "fixture rule"}).json()
    yield r["id"]
    store._rules[:] = [x for x in store._rules if x["id"] != r["id"]]


@pytest.mark.parametrize("method,path,body", ADMIN_ONLY)
def test_analyst_cannot_change_configuration(alice, rule, method, path, body):
    before = [dict(r) for r in store._rules], dict(store._behavioral_config)
    r = alice.request(method, path.format(rule=rule), json=body)
    assert r.status_code == 403
    assert r.json() == {"detail": "Admin role required"}
    assert ([dict(r) for r in store._rules], dict(store._behavioral_config)) == before


# ── Everyone: reads, alerts, IP actions, console, hunts ───────


# ── Demo middleware still runs first ──────────────────────────

def test_demo_mode_blocks_even_admin_writes(admin, monkeypatch):
    monkeypatch.setattr(main, "DEMO_MODE", True)
    r = admin.post("/api/rules", json={"name": "r"})
    assert r.status_code == 403 and r.json() == {"detail": "Read-only demo"}


# ── DB path: the take is a compare-and-set ────────────────────


async def _db_incident(session, assigned_to):
    from db_ops import db_create_incident
    now = datetime.now(timezone.utc).isoformat()
    await db_create_incident(session, {
        "id": "INC-DB1", "title": "t", "severity": "high", "status": "open",
        "attack_type": "SQLi", "source_ip": PUBLIC_IP, "source_region": "US",
        "event_count": 1, "assigned_to": assigned_to, "created_at": now,
        "updated_at": now, "mitre_tags": [],
    })


@pytest.mark.asyncio
async def test_db_patch_applies_when_assignee_unchanged(db_session):
    from db_ops import db_patch_incident
    await _db_incident(db_session, None)
    out = await db_patch_incident(db_session, "INC-DB1", {"assigned_to": "alice"}, expected_assignee=None)
    assert out["assigned_to"] == "alice"


@pytest.mark.asyncio
async def test_db_second_take_loses_the_race(db_session):
    """Both analysts saw 'unassigned'; only the first write may win."""
    from db_ops import StaleIncident, db_get_incident, db_patch_incident
    await _db_incident(db_session, None)
    await db_patch_incident(db_session, "INC-DB1", {"assigned_to": "alice"}, expected_assignee=None)
    with pytest.raises(StaleIncident):
        await db_patch_incident(db_session, "INC-DB1", {"assigned_to": "bob"}, expected_assignee=None)
    assert (await db_get_incident(db_session, "INC-DB1"))["assigned_to"] == "alice"


@pytest.mark.asyncio
async def test_db_status_write_fails_after_reassignment(db_session):
    from db_ops import StaleIncident, db_get_incident, db_patch_incident
    await _db_incident(db_session, "alice")
    await db_patch_incident(db_session, "INC-DB1", {"assigned_to": "bob"}, expected_assignee="alice")
    with pytest.raises(StaleIncident):  # alice's check saw herself as assignee
        await db_patch_incident(db_session, "INC-DB1", {"status": "closed"}, expected_assignee="alice")
    assert (await db_get_incident(db_session, "INC-DB1"))["status"] == "open"


@pytest.mark.asyncio
async def test_db_patch_returns_fresh_state_when_rows_are_cached(db_session):
    """The route loads the incident (with notes) before patching; the returned
    state must reflect the UPDATE, not the ORM's cached copy."""
    from db_ops import db_add_note, db_get_incident, db_patch_incident
    await _db_incident(db_session, "alice")
    await db_add_note(db_session, "INC-DB1", text="n", author="alice")
    await db_get_incident(db_session, "INC-DB1")  # cached, kept alive by the notes relationship
    out = await db_patch_incident(db_session, "INC-DB1", {"status": "closed"}, expected_assignee="alice")
    assert out["status"] == "closed"


@pytest.mark.asyncio
async def test_db_patch_unknown_incident_is_none(db_session):
    from db_ops import db_patch_incident
    assert await db_patch_incident(db_session, "NOPE", {"status": "open"}, expected_assignee=None) is None
