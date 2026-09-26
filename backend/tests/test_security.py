"""Security regression tests.

Each test is a small attack. If one fails, a security control regressed.
"""
import base64
import json
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from jose import jwt

import main
from tests.conftest import ANALYST_PASSWORD
from store import SECRET_KEY

COOKIE = "sf_session"
PUBLIC_IP = "8.8.8.8"


@pytest.fixture
def client():
    return TestClient(main.app)


@pytest.fixture
def logged_in(client):
    r = client.post("/auth/login", json={"username": "alice", "password": ANALYST_PASSWORD})
    assert r.status_code == 200
    return client


def _token(claims: dict, key: str = SECRET_KEY) -> str:
    base = {"sub": "alice", "role": "analyst", "exp": datetime.now(timezone.utc) + timedelta(minutes=5)}
    return jwt.encode({**base, **claims}, key, algorithm="HS256")


def _as_session(client: TestClient, token: str) -> TestClient:
    client.cookies.clear()
    client.cookies.set(COOKIE, token)
    return client


# ── 1. Token confusion (the bug fixed in 0f88e23) ─────────────────

class TestTokenConfusion:
    def test_ws_ticket_is_rejected_as_session_cookie(self, logged_in):
        ticket = logged_in.get("/auth/ws-ticket").json()["ticket"]
        attacker = _as_session(TestClient(main.app), ticket)

        assert attacker.get("/api/stats").status_code == 401
        assert attacker.get("/auth/me").status_code == 401

    def test_ws_ticket_cannot_mint_new_tickets(self, logged_in):
        """The escalation: a leaked 5-minute ticket must not renew itself forever."""
        ticket = logged_in.get("/auth/ws-ticket").json()["ticket"]
        attacker = _as_session(TestClient(main.app), ticket)

        assert attacker.get("/auth/ws-ticket").status_code == 401

    def test_session_cookie_is_rejected_as_ws_ticket(self, logged_in):
        session = logged_in.cookies.get(COOKIE)
        with pytest.raises(Exception):
            with logged_in.websocket_connect(f"/ws/threats?ticket={session}") as ws:
                ws.receive_text()

    def test_token_without_type_is_rejected(self, client):
        legacy = _token({})  # pre-fix format: valid signature, no "typ"
        assert _as_session(client, legacy).get("/api/stats").status_code == 401


# ── 2. Classic JWT attacks ────────────────────────────────────────

class TestJwtAttacks:
    def test_forged_signature_is_rejected(self, client):
        forged = _token({"typ": "session"}, key="attacker-guessed-key")
        assert _as_session(client, forged).get("/api/stats").status_code == 401

    def test_expired_token_is_rejected(self, client):
        expired = _token({"typ": "session", "exp": datetime.now(timezone.utc) - timedelta(seconds=1)})
        assert _as_session(client, expired).get("/api/stats").status_code == 401

    def test_alg_none_is_rejected(self, client):
        """'alg: none' = unsigned token. Libraries that honour it accept anything."""
        def b64(d: dict) -> str:
            return base64.urlsafe_b64encode(json.dumps(d).encode()).rstrip(b"=").decode()

        exp = int((datetime.now(timezone.utc) + timedelta(minutes=5)).timestamp())
        unsigned = f'{b64({"alg": "none", "typ": "JWT"})}.{b64({"sub": "alice", "role": "analyst", "typ": "session", "exp": exp})}.'
        assert _as_session(client, unsigned).get("/api/stats").status_code == 401


# ── 3. Every API route requires authentication ────────────────────

# Routes that are intentionally public. Anything not listed here must
# return 401 without a session, so a new route that forgets auth fails CI.
PUBLIC_ROUTES = {
    ("POST", "/auth/login"),
    ("POST", "/auth/logout"),
    ("GET", "/api/config"),
}


def _api_routes():
    # Read routes from the OpenAPI schema: it lists every HTTP route,
    # including those mounted from sub-routers, on any FastAPI version.
    for path, ops in main.app.openapi()["paths"].items():
        if not path.startswith(("/api/", "/auth/")):
            continue
        for method in ops:
            if method.upper() != "HEAD" and (method.upper(), path) not in PUBLIC_ROUTES:
                yield method.upper(), path


def test_route_discovery_finds_routes():
    """Guard against the check below silently testing nothing."""
    assert len(list(_api_routes())) >= 20


@pytest.mark.parametrize("method,path", sorted(_api_routes()))
def test_route_requires_auth(client, method, path):
    url = path.replace("{ip}", PUBLIC_IP)
    for param in ("{alert_id}", "{incident_id}", "{rule_id}", "{hunt_id}"):
        url = url.replace(param, "x1")

    r = client.request(method, url, json={})
    assert r.status_code == 401, f"{method} {path} is reachable without login ({r.status_code})"


# ── 4. SSRF guard: no internal addresses to external lookups ──────

@pytest.mark.parametrize("ip", [
    "127.0.0.1",        # loopback
    "10.0.0.5",         # private
    "192.168.1.1",      # private
    "172.16.0.1",       # private
    "169.254.169.254",  # link-local: cloud metadata endpoint
    "0.0.0.0",          # unspecified
    "224.0.0.1",        # multicast
    "::1",              # IPv6 loopback
    "fd00::1",          # IPv6 private
])
def test_internal_ips_are_rejected(logged_in, ip):
    assert logged_in.get(f"/api/ip/{ip}/history").status_code == 422


@pytest.mark.parametrize("ip", [
    "2130706433",       # 127.0.0.1 as a decimal integer
    "0x7f.0.0.1",       # hex octet
    "127.1",            # short form
    "localhost",
    "8.8.8.8.evil.com",
])
def test_obfuscated_addresses_are_rejected(logged_in, ip):
    assert logged_in.get(f"/api/ip/{ip}/history").status_code == 422


def test_public_ip_is_allowed(logged_in):
    assert logged_in.get(f"/api/ip/{PUBLIC_IP}/history").status_code == 200


# ── 5. Read-only demo mode ────────────────────────────────────────

@pytest.fixture
def demo(logged_in, monkeypatch):
    monkeypatch.setattr(main, "DEMO_MODE", True)
    return logged_in


@pytest.mark.parametrize("method,path", [
    ("POST", "/api/rules"),
    ("DELETE", "/api/rules/x1"),
    ("PATCH", "/api/behavioral/settings"),
    ("POST", "/api/command"),
    ("POST", "/auth/login/../../api/rules"),  # path traversal into the allowlist
    ("POST", "/AUTH/LOGIN"),                  # case games
    ("PUT", "/auth/login"),                   # right path, wrong method
])
def test_demo_blocks_writes(demo, method, path):
    assert demo.request(method, path, json={}).status_code == 403


def test_demo_ignores_method_override_header(demo):
    r = demo.post("/api/rules", json={}, headers={"X-HTTP-Method-Override": "GET"})
    assert r.status_code == 403


def test_demo_still_allows_reads_and_login(demo):
    assert demo.get("/api/rules").status_code == 200
    assert demo.post("/auth/logout").status_code == 200


# ── 6. Identity comes from the session, not the request ───────────

def test_note_author_cannot_be_spoofed(logged_in):
    """A client must not be able to write notes in someone else's name."""
    case = logged_in.post("/api/incidents/from-ip", json={"ip": PUBLIC_IP}).json()

    r = logged_in.post(
        f"/api/incidents/{case['id']}/notes",
        json={"text": "Containment approved.", "author": "CISO"},
    )

    assert r.status_code == 200
    assert r.json()["author"] == "alice"   # the logged-in user, not "CISO"
