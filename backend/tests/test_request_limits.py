"""Request body size limit, typed request bodies, hunting caps and the
per-IP rate limits on write routes."""
from __future__ import annotations
import json

import pytest
from fastapi.testclient import TestClient

import main
import store
from request_limits import MAX_BODY_BYTES
from routers.hunting import MAX_HUNT_RESULTS, MAX_SAVED_HUNTS
from schemas import IncidentPatch, MAX_COMMAND, MAX_NAME
from tests.conftest import login

ADMIN_PASSWORD = "test-admin-password"
PUBLIC_IP = "8.8.8.8"


@pytest.fixture
def alice():
    return login()


@pytest.fixture
def admin():
    return login("admin", ADMIN_PASSWORD)


@pytest.fixture
def keep_state():
    """Restore rules and saved hunts that a test changes."""
    rules, hunts = list(store._rules), list(store._saved_hunts)
    yield
    store._rules[:] = rules
    store._saved_hunts[:] = hunts


# ── Body size ─────────────────────────────────────────────────

def _big_json(size: int) -> bytes:
    return json.dumps({"name": "x" * size}).encode()


def test_large_body_is_413_before_auth():
    r = TestClient(main.app).post("/auth/login", content=_big_json(MAX_BODY_BYTES),
                                  headers={"Content-Type": "application/json"})
    assert r.status_code == 413
    assert r.json() == {"detail": "Request body too large"}


def test_large_body_is_413_on_an_authenticated_route(alice, keep_state):
    before = list(store._saved_hunts)
    r = alice.post("/api/hunts", content=_big_json(MAX_BODY_BYTES),
                   headers={"Content-Type": "application/json"})
    assert r.status_code == 413
    assert store._saved_hunts == before


def test_large_chunked_body_without_content_length_is_413(alice, keep_state):
    payload = _big_json(MAX_BODY_BYTES)

    def chunks():
        for i in range(0, len(payload), 4096):
            yield payload[i:i + 4096]

    before = list(store._saved_hunts)
    r = alice.post("/api/hunts", content=chunks(), headers={"Content-Type": "application/json"})
    assert r.status_code == 413
    assert store._saved_hunts == before


def test_body_under_the_limit_is_not_413(alice, keep_state):
    r = alice.post("/api/hunts", content=_big_json(MAX_BODY_BYTES // 2),
                   headers={"Content-Type": "application/json"})
    assert r.status_code == 422  # too long a name, but read and validated


def test_413_carries_security_headers():
    r = TestClient(main.app).post("/auth/login", content=_big_json(MAX_BODY_BYTES),
                                  headers={"Content-Type": "application/json"})
    assert r.headers["X-Content-Type-Options"] == "nosniff"


# ── Typed bodies: unknown fields ──────────────────────────────

ALICE_ROUTES = [
    ("PATCH", "/api/alerts/x", {"status": "acknowledged", "extra": 1}),
    ("POST", "/api/hunts", {"name": "h", "owner": "bob"}),
    ("POST", "/api/hunts", {"name": "h", "query": {"ip": "1.2.3.4", "sql": "1=1"}}),
    ("PATCH", "/api/incidents/INC-X", {"status": "open", "severity": "low"}),
    ("POST", "/api/incidents/from-ip", {"ip": PUBLIC_IP, "assigned_to": "bob"}),
    ("PATCH", "/api/incidents/INC-X/tasks", {"completed_tasks": [], "x": 1}),
    ("POST", "/api/command", {"command": "help", "sudo": True}),
    ("PATCH", "/auth/me", {"current_password": "a", "new_password": "b", "role": "admin"}),
]

ADMIN_ROUTES = [
    ("PATCH", "/api/behavioral/settings", {"cooldown_min": 30, "debug": 1}),
    ("POST", "/api/rules", {"name": "r", "id": "fixed"}),
    ("PATCH", "/api/rules/x", {"match_count": 0}),
    ("POST", "/api/users", {"username": "new-user", "display_name": "N", "role": "analyst",
                            "password": "long-enough-password", "session_key": "k"}),
    ("PATCH", "/api/users/alice", {"display_name": "Mallory"}),
]


@pytest.mark.parametrize("method,path,body", ALICE_ROUTES)
def test_unknown_fields_are_422(alice, keep_state, method, path, body):
    assert alice.request(method, path, json=body).status_code == 422


@pytest.mark.parametrize("method,path,body", ADMIN_ROUTES)
def test_unknown_fields_are_422_on_admin_routes(admin, keep_state, method, path, body):
    assert admin.request(method, path, json=body).status_code == 422


# ── Typed bodies: wrong types and sizes ───────────────────────

BAD_RULES = [
    {"conditions": [1]},
    {"conditions": ["score > 5"]},
    {"conditions": [{"field": "password", "operator": "=", "value": "x"}]},
    {"conditions": [{"field": "score", "operator": "~", "value": 5}]},
    {"conditions": [{"field": "score", "operator": ">", "value": True}]},
    {"conditions": [{"field": "ip", "operator": "=", "value": "x" * 65}]},
    {"conditions": [{"field": "score", "operator": ">", "value": 1}] * 21},
    {"actions": ["delete-all"]},
    {"actions": "block"},
    {"logic": "XOR"},
    {"enabled": "yes"},
    {"name": 5},
    {"name": "x" * (MAX_NAME + 1)},
]


@pytest.mark.parametrize("body", BAD_RULES)
def test_malformed_rule_is_422_and_not_stored(admin, keep_state, body):
    before = [dict(r) for r in store._rules]
    assert admin.post("/api/rules", json=body).status_code == 422
    assert [dict(r) for r in store._rules] == before


@pytest.mark.parametrize("body", [*BAD_RULES, {"name": None}, {"conditions": None}, {"enabled": None}])
def test_malformed_rule_patch_is_422(admin, keep_state, body):
    rule = admin.post("/api/rules", json={"name": "target"}).json()
    assert admin.patch(f"/api/rules/{rule['id']}", json=body).status_code == 422
    assert next(r for r in store._rules if r["id"] == rule["id"])["name"] == "target"


def test_valid_rule_round_trips(admin, keep_state):
    body = {"name": "r", "enabled": True, "logic": "OR", "actions": ["alert", "block"],
            "conditions": [{"field": "score", "operator": ">", "value": 80},
                           {"field": "region", "operator": "=", "value": "EU"}]}
    rule = admin.post("/api/rules", json=body).json()
    assert {k: rule[k] for k in body} == body
    r = admin.patch(f"/api/rules/{rule['id']}", json={"enabled": False})
    assert r.status_code == 200 and r.json()["enabled"] is False
    assert r.json()["conditions"] == body["conditions"]


@pytest.mark.parametrize("method,path,body", [
    ("PATCH", "/api/alerts/x", {"status": "deleted"}),
    ("PATCH", "/api/alerts/x", {}),
    ("POST", "/api/hunts", {"name": "x" * (MAX_NAME + 1)}),
    ("POST", "/api/hunts", {"name": "h", "result_count": -1}),
    ("POST", "/api/hunts", {"name": "h", "query": {"min_score": 101}}),
    ("POST", "/api/hunts", {"name": "h", "query": "all"}),
    ("POST", "/api/incidents/from-ip", {"ip": 134744072}),
    ("POST", "/api/incidents/from-ip", {}),
    ("PATCH", "/api/incidents/INC-X", {"status": None}),
    ("POST", "/api/command", {"command": ["help"]}),
    ("POST", "/api/command", {"command": "x" * (MAX_COMMAND + 1)}),
    ("PATCH", "/auth/me", {"current_password": 1, "new_password": "b"}),
])
def test_wrong_types_and_sizes_are_422(alice, keep_state, method, path, body):
    assert alice.request(method, path, json=body).status_code == 422


@pytest.mark.parametrize("body", [
    {"cooldown_min": None}, {"cooldown_min": "30"}, {"cooldown_min": 30.5}, {"cooldown_min": True},
])
def test_wrong_behavioral_types_are_422(admin, body):
    assert admin.patch("/api/behavioral/settings", json=body).status_code == 422


def test_incident_patch_still_accepts_null_assignee():
    assert IncidentPatch.model_validate({"assigned_to": None}).changes() == {"assigned_to": None}


@pytest.mark.parametrize("body", [
    {"username": "x" * 65, "password": "p"},
    {"username": "alice", "password": "p" * 257},
    {"username": 1, "password": 2},
    {"username": "alice", "password": "wrong", "remember": True},
])
def test_malformed_login_stays_401(body):
    assert TestClient(main.app).post("/auth/login", json=body).status_code == 401


# ── Hunting caps ──────────────────────────────────────────────

@pytest.mark.parametrize("limit", [0, -1, MAX_HUNT_RESULTS + 1])
def test_hunt_limit_out_of_range_is_422(alice, limit):
    assert alice.get("/api/hunt", params={"limit": limit}).status_code == 422


def test_hunt_limit_at_max_is_accepted(alice):
    assert alice.get("/api/hunt", params={"limit": MAX_HUNT_RESULTS}).status_code == 200


def test_saved_hunts_are_capped(alice, keep_state):
    store._saved_hunts[:] = [{"id": f"h{i}", "name": "h", "query": {}, "created_at": "", "result_count": 0}
                             for i in range(MAX_SAVED_HUNTS)]
    assert alice.post("/api/hunts", json={"name": "one more"}).status_code == 409
    assert len(store._saved_hunts) == MAX_SAVED_HUNTS
    alice.delete("/api/hunts/h0")
    assert alice.post("/api/hunts", json={"name": "one more"}).status_code == 200


def test_saved_hunt_keeps_only_sent_query_fields(alice, keep_state):
    r = alice.post("/api/hunts", json={"name": "h", "query": {"ip": "1.2", "min_score": 50}, "result_count": 3})
    assert r.status_code == 200
    assert r.json()["query"] == {"ip": "1.2", "min_score": 50}


# ── Per-IP rate limits on write routes ────────────────────────

def _codes(n: int, call) -> list[int]:
    return [call().status_code for _ in range(n)]


def test_write_routes_are_rate_limited(alice):
    codes = _codes(31, lambda: alice.patch("/api/alerts/none", json={"status": "acknowledged"}))
    assert codes == [404] * 30 + [429]


def test_admin_write_routes_are_rate_limited(admin):
    codes = _codes(21, lambda: admin.delete("/api/rules/none"))
    assert codes == [200] * 20 + [429]


def test_hunt_queries_are_rate_limited(alice):
    assert _codes(31, lambda: alice.get("/api/hunt"))[-1] == 429


def test_ws_ticket_minting_is_rate_limited(alice):
    codes = _codes(61, lambda: alice.get("/auth/ws-ticket"))
    assert codes == [200] * 60 + [429]


def test_logout_is_rate_limited():
    client = TestClient(main.app)
    assert _codes(31, lambda: client.post("/auth/logout"))[-1] == 429
