"""Per-IP limits on the read routes that had none (finding L7)."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

import main
from tests.conftest import session_client

PROXY_SEEN = "203.0.113.7"

# (path, requests allowed per minute, needs a session)
READ_ROUTES = [
    ("/api/alerts", 120, True),
    ("/api/alerts/summary", 120, True),
    ("/api/users", 120, True),
    ("/api/users/directory", 120, True),
    ("/auth/me", 120, True),
    ("/api/threat-feed", 120, True),
    ("/api/config", 120, False),
    ("/api/incidents", 60, True),
    ("/api/rules", 60, True),
    ("/api/behavioral/settings", 60, True),
    ("/api/ip/8.8.8.8/case", 60, True),
]


def _client(authenticated: bool) -> TestClient:
    return session_client("alice", "analyst") if authenticated else TestClient(main.app)


@pytest.mark.parametrize("path,allowed,authenticated", READ_ROUTES)
def test_read_route_is_limited_per_ip(path, allowed, authenticated):
    client = _client(authenticated)
    headers = {"X-Forwarded-For": "198.51.100.20"}
    codes = [client.get(path, headers=headers).status_code for _ in range(allowed)]
    assert codes == [200] * allowed
    r = client.get(path, headers=headers)
    assert r.status_code == 429
    assert r.json() == {"error": f"Rate limit exceeded: {allowed} per 1 minute"}
    assert 1 <= int(r.headers["Retry-After"]) <= 60


def test_rotating_a_spoofed_entry_does_not_escape_the_read_limit():
    client = _client(True)
    codes = [
        client.get("/api/alerts", headers={"X-Forwarded-For": f"10.0.{i % 250}.1, {PROXY_SEEN}"}).status_code
        for i in range(121)
    ]
    assert codes == [200] * 120 + [429]


def test_another_ip_keeps_its_own_read_budget():
    client = _client(True)
    for _ in range(121):
        client.get("/api/incidents", headers={"X-Forwarded-For": "198.51.100.21"})
    assert client.get("/api/incidents", headers={"X-Forwarded-For": "198.51.100.22"}).status_code == 200


def test_routes_keep_separate_budgets():
    client = _client(True)
    headers = {"X-Forwarded-For": "198.51.100.23"}
    for _ in range(121):
        client.get("/api/alerts", headers=headers)
    assert client.get("/api/alerts/summary", headers=headers).status_code == 200


def test_unauthenticated_requests_do_not_use_the_budget():
    """The session check runs before the limit, so a 401 flood cannot lock
    signed-in users behind the same address out of their reads."""
    anonymous = TestClient(main.app)
    headers = {"X-Forwarded-For": "198.51.100.24"}
    assert {anonymous.get("/api/alerts", headers=headers).status_code for _ in range(130)} == {401}
    assert _client(True).get("/api/alerts", headers=headers).status_code == 200


def test_health_is_not_limited():
    client = TestClient(main.app)
    headers = {"X-Forwarded-For": "198.51.100.25"}
    assert {client.get("/health", headers=headers).status_code for _ in range(150)} == {200}
    assert {client.head("/health", headers=headers).status_code for _ in range(150)} == {200}
