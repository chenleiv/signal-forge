"""Input validation and abuse limits: console targets, blocklist cap,
note text, completed_tasks, per-user case creation. Invalid input is a
422 (or a console error line), never a 500."""
from __future__ import annotations
from datetime import datetime, timezone

import pytest

import store
from constants import MAX_NOTE_LENGTH, RESPONSE_TASKS
from tests.conftest import session_client

PUBLIC_IP = "8.8.8.8"


@pytest.fixture(autouse=True)
def _restore_state():
    incidents, blocked = list(store.incidents_store), set(store._blocked_ips)
    yield
    store.incidents_store.clear()
    store.incidents_store.extend(incidents)
    store._blocked_ips.clear()
    store._blocked_ips.update(blocked)


@pytest.fixture
def alice():
    return session_client("alice", "analyst")


@pytest.fixture
def own_incident():
    """An SQLi incident (5 tasks) assigned to alice."""
    now = datetime.now(timezone.utc).isoformat()
    store.incidents_store.appendleft({
        "id": "INC-V001", "title": "t", "severity": "high", "status": "open",
        "attack_type": "SQLi", "source_ip": PUBLIC_IP, "source_region": "US",
        "event_count": 1, "assigned_to": "alice", "created_at": now,
        "updated_at": now, "mitre_tags": [], "notes": [], "completed_tasks": [],
    })
    return "INC-V001"


def _console(client, command: str) -> str:
    r = client.post("/api/command", json={"command": command})
    assert r.status_code == 200
    return r.json()["output"]


# ── 1. Console targets and blocklist cap ──────────────────────

@pytest.mark.parametrize("verb", ["block ip", "unblock ip", "scan"])
@pytest.mark.parametrize("target", ["127.0.0.1", "169.254.169.254", "10.0.0.1", "localhost",
                                    "2130706433", "not-an-ip", "8.8.8.8; rm -rf /"])
def test_console_rejects_invalid_targets(alice, verb, target):
    before = set(store._blocked_ips)
    assert _console(alice, f"{verb} {target}").startswith("Error:")
    assert store._blocked_ips == before


@pytest.mark.parametrize("verb", ["block ip", "unblock ip", "scan"])
def test_console_without_target_changes_nothing(alice, verb):
    before = set(store._blocked_ips)
    assert _console(alice, f"{verb}   ").startswith("Unknown command")
    assert store._blocked_ips == before


def test_console_accepts_and_normalizes_public_ips(alice):
    assert _console(alice, f"block ip {PUBLIC_IP}").startswith("[BLOCKED]")
    assert PUBLIC_IP in store._blocked_ips
    assert _console(alice, f"scan {PUBLIC_IP}").startswith(PUBLIC_IP)
    assert _console(alice, f"unblock ip {PUBLIC_IP}").startswith("[OK]")
    assert PUBLIC_IP not in store._blocked_ips


@pytest.fixture
def full_blocklist(monkeypatch):
    monkeypatch.setattr(store, "MAX_BLOCKED_IPS", 3)
    monkeypatch.setattr("routers.ip.MAX_BLOCKED_IPS", 3)
    store._blocked_ips.clear()
    store._blocked_ips.update({"1.1.1.1", "1.0.0.1", "9.9.9.9"})


def test_full_blocklist_rejects_new_entries_via_console(alice, full_blocklist):
    assert _console(alice, f"block ip {PUBLIC_IP}").startswith("Error: blocklist is full")
    assert PUBLIC_IP not in store._blocked_ips and len(store._blocked_ips) == 3


def test_full_blocklist_rejects_new_entries_via_api(alice, full_blocklist):
    r = alice.post(f"/api/ip/{PUBLIC_IP}/block")
    assert r.status_code == 409
    assert PUBLIC_IP not in store._blocked_ips


def test_full_blocklist_still_accepts_already_blocked_ip(alice, full_blocklist):
    assert alice.post("/api/ip/1.1.1.1/block").status_code == 200


def test_rule_auto_block_respects_the_cap(full_blocklist):
    store._execute_actions({"actions": ["block"], "name": "r"}, {"ip": PUBLIC_IP})
    assert PUBLIC_IP not in store._blocked_ips


# ── 2a. Note text ─────────────────────────────────────────────

@pytest.mark.parametrize("body", [{}, {"text": ""}, {"text": "   \n\t "}, {"text": None},
                                  {"text": 42}, {"text": ["x"]}, {"text": {"a": 1}},
                                  {"text": "x" * (MAX_NOTE_LENGTH + 1)}])
def test_invalid_note_is_422(alice, own_incident, body):
    r = alice.post(f"/api/incidents/{own_incident}/notes", json=body)
    assert r.status_code == 422
    assert store._find_incident(own_incident)["notes"] == []


def test_note_at_max_length_is_accepted_and_trimmed(alice, own_incident):
    text = "x" * MAX_NOTE_LENGTH
    r = alice.post(f"/api/incidents/{own_incident}/notes", json={"text": f"  {text}  "})
    assert r.status_code == 200 and r.json()["text"] == text


# ── 2b. completed_tasks ───────────────────────────────────────

N_SQLI = len(RESPONSE_TASKS["SQLi"])


@pytest.mark.parametrize("tasks", [None, "0,1", {"0": True}, [0, 0], [-1], [N_SQLI],
                                   [10**9], [1.0], ["1"], [True], [None], [[0]]])
def test_invalid_completed_tasks_is_422(alice, own_incident, tasks):
    r = alice.patch(f"/api/incidents/{own_incident}/tasks", json={"completed_tasks": tasks})
    assert r.status_code == 422
    assert store._find_incident(own_incident)["completed_tasks"] == []


def test_missing_completed_tasks_is_422(alice, own_incident):
    assert alice.patch(f"/api/incidents/{own_incident}/tasks", json={}).status_code == 422


@pytest.mark.parametrize("tasks", [[], [0], [N_SQLI - 1, 0, 2]])
def test_valid_completed_tasks_are_accepted(alice, own_incident, tasks):
    r = alice.patch(f"/api/incidents/{own_incident}/tasks", json={"completed_tasks": tasks})
    assert r.status_code == 200 and r.json()["completed_tasks"] == tasks


def test_incident_without_playbook_accepts_only_empty(alice, own_incident):
    store._find_incident(own_incident)["attack_type"] = "RepeatedIP"
    assert alice.patch(f"/api/incidents/{own_incident}/tasks", json={"completed_tasks": [0]}).status_code == 422
    assert alice.patch(f"/api/incidents/{own_incident}/tasks", json={"completed_tasks": []}).status_code == 200


def test_permission_is_checked_before_task_validation():
    """A non-owner gets 403, not a 422 that describes the playbook."""
    bob = session_client("bob", "analyst")
    now = datetime.now(timezone.utc).isoformat()
    store.incidents_store.appendleft({
        "id": "INC-V002", "title": "t", "severity": "high", "status": "open",
        "attack_type": "SQLi", "source_ip": PUBLIC_IP, "source_region": "US",
        "event_count": 1, "assigned_to": "alice", "created_at": now,
        "updated_at": now, "mitre_tags": [], "notes": [], "completed_tasks": [],
    })
    assert bob.patch("/api/incidents/INC-V002/tasks", json={"completed_tasks": "junk"}).status_code == 403


# ── 3. Per-user case creation limit ───────────────────────────

def _new_case(client, i: int):
    return client.post("/api/incidents/from-ip", json={"ip": f"8.8.4.{i}"})


def test_case_creation_is_limited_per_user(alice):
    store.incidents_store.clear()
    codes = [_new_case(alice, i).status_code for i in range(6)]
    assert codes == [200] * 5 + [429]


def test_case_limit_is_per_user_not_global(alice):
    store.incidents_store.clear()
    for i in range(6):
        _new_case(alice, i)
    bob = session_client("bob", "analyst")
    assert _new_case(bob, 100).status_code == 200


def test_case_limit_applies_to_cases_from_alerts(alice):
    store.incidents_store.clear()
    for i in range(5):
        _new_case(alice, i)
    alert = store._create_alert("test", "SQLi", "high", "8.8.4.200", "test alert")
    assert alice.post(f"/api/alerts/{alert['id']}/case").status_code == 429


def test_reopening_an_existing_case_does_not_count(alice):
    store.incidents_store.clear()
    for _ in range(10):
        assert alice.post("/api/incidents/from-ip", json={"ip": PUBLIC_IP}).status_code == 200
    assert _new_case(alice, 1).status_code == 200


def test_limited_request_creates_nothing(alice):
    store.incidents_store.clear()
    for i in range(5):
        _new_case(alice, i)
    count = len(store.incidents_store)
    _new_case(alice, 99)
    assert len(store.incidents_store) == count


def test_case_limit_does_not_touch_the_login_lockout(alice):
    """Separate counters: creating cases must not lock the user out of login."""
    from tests.conftest import ANALYST_PASSWORD
    store.incidents_store.clear()
    for i in range(5):
        _new_case(alice, i)
    anon = session_client("nobody", "analyst")
    anon.cookies.clear()
    for i in range(5):
        anon.post("/auth/login", json={"username": "alice", "password": "wrong"},
                  headers={"X-Forwarded-For": f"192.0.2.{i}"})
    r = anon.post("/auth/login", json={"username": "alice", "password": ANALYST_PASSWORD},
                  headers={"X-Forwarded-For": "192.0.2.99"})
    assert r.status_code == 200


# ── 4. Behavioral detection settings ──────────────────────────

@pytest.fixture
def admin_client():
    saved = dict(store._behavioral_config)
    yield session_client("admin", "admin")
    store._behavioral_config.clear()
    store._behavioral_config.update(saved)


@pytest.mark.parametrize("body", [
    {}, {"cooldown_min": "30"}, {"cooldown_min": True}, {"cooldown_min": 1.5}, {"cooldown_min": None},
    {"cooldown_min": 0}, {"cooldown_min": 1441}, {"repeated_threshold": -1}, {"escalation_delta": 101},
    {"unknown_setting": 5}, {"cooldown_min": 30, "extra": 1},
])
def test_invalid_behavioral_settings_are_422(admin_client, body):
    before = dict(store._behavioral_config)
    assert admin_client.patch("/api/behavioral/settings", json=body).status_code == 422
    assert store._behavioral_config == before


def test_valid_behavioral_settings_are_applied(admin_client):
    r = admin_client.patch("/api/behavioral/settings", json={"cooldown_min": 1, "repeated_threshold": 1000})
    assert r.status_code == 200
    assert (store._behavioral_config["cooldown_min"], store._behavioral_config["repeated_threshold"]) == (1, 1000)
