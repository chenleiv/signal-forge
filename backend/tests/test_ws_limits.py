"""WebSocket limits: open sockets are capped per client IP and in total (the
handshake is refused with 429), every exit path releases its slot, and a
client frame after "ready" closes the stream with 1008."""
from __future__ import annotations

import time
from contextlib import ExitStack

import pytest
from fastapi.testclient import TestClient
from starlette.testclient import WebSocketDenialResponse
from starlette.websockets import WebSocketDisconnect

import main
import rate_limit
import simulation
import users
from tests.conftest import login
from tests.ws_client import WS_PATH, auth_message, open_stream

# Enough frames to prove the stream would otherwise keep going (about 3 s).
MAX_FRAMES = 200


async def _fake_refresh(**_) -> None:
    simulation.THREAT_IPS = {"8.8.8.8": 90, "1.1.1.1": 70, "9.9.9.9": 50}


@pytest.fixture(autouse=True)
def _one_trusted_proxy(monkeypatch):
    # As on Render: the rightmost X-Forwarded-For entry of a WebSocket
    # upgrade is the client. Set here so a local .env cannot change it.
    monkeypatch.setattr(rate_limit, "TRUSTED_PROXY_HOPS_WS", 1)


@pytest.fixture
def client():
    return TestClient(main.app)


@pytest.fixture
def live(monkeypatch):
    """Runs the lifespan (the shared stream loop) with a fast stream."""
    monkeypatch.setattr(main, "refresh_threat_ips", _fake_refresh)
    monkeypatch.setattr(main, "STREAM_INTERVAL", (0.01, 0.02))
    monkeypatch.setattr(main, "WS_RECHECK_SECONDS", 0.05)
    with TestClient(main.app) as c:
        yield c


def _caps(monkeypatch, per_ip: int, total: int = 500) -> None:
    # raising=False: on code without the caps the tests reach their real
    # assertions instead of failing on the missing name.
    monkeypatch.setattr(main, "WS_MAX_PER_IP", per_ip, raising=False)
    monkeypatch.setattr(main, "WS_MAX_TOTAL", total, raising=False)


def _from(ip_chain: str) -> dict:
    return {"X-Forwarded-For": ip_chain}


def _hold(stack: ExitStack, client: TestClient, headers: dict | None = None):
    """An open, unauthenticated socket, kept open until the stack closes."""
    return stack.enter_context(client.websocket_connect(WS_PATH, headers=dict(headers or {})))


def _refused(client: TestClient, headers: dict | None = None) -> int | None:
    """The handshake's HTTP status if the server refuses it, else None."""
    try:
        with client.websocket_connect(WS_PATH, headers=dict(headers or {})):
            return None
    except WebSocketDenialResponse as exc:
        return exc.status_code


def _close_code(ws) -> int | None:
    """Read frames until the server closes; None if it never does."""
    try:
        for _ in range(MAX_FRAMES):
            ws.receive_json()
    except WebSocketDisconnect as exc:
        return exc.code
    return None


def _no_open_sockets() -> bool:
    deadline = time.monotonic() + 1.0
    while time.monotonic() < deadline:
        if getattr(main, "_ws_open_by_ip", None) == {}:
            return True
        time.sleep(0.01)
    return False


# ── Caps ──────────────────────────────────────────────────────

def test_per_ip_cap_refuses_the_next_socket_with_429(client, monkeypatch):
    _caps(monkeypatch, per_ip=2)
    with ExitStack() as stack:
        _hold(stack, client, _from("203.0.113.1"))
        _hold(stack, client, _from("203.0.113.1"))
        assert _refused(client, _from("203.0.113.1")) == 429
        assert _refused(client, _from("203.0.113.2")) is None   # another IP still gets in
    assert _no_open_sockets()


def test_spoofed_forwarded_entries_do_not_rotate_the_key(client, monkeypatch):
    """Only the entry added by the trusted proxy counts; the client-chosen
    entries to its left change nothing."""
    _caps(monkeypatch, per_ip=2)
    with ExitStack() as stack:
        _hold(stack, client, _from("10.0.0.1, 203.0.113.9"))
        _hold(stack, client, _from("10.0.0.2, 203.0.113.9"))
        assert _refused(client, _from("10.0.0.3, 203.0.113.9")) == 429


def test_total_cap_refuses_the_next_socket_with_429(client, monkeypatch):
    _caps(monkeypatch, per_ip=20, total=2)
    with ExitStack() as stack:
        _hold(stack, client, _from("203.0.113.1"))
        _hold(stack, client, _from("203.0.113.2"))
        assert _refused(client, _from("203.0.113.3")) == 429
    assert _refused(client, _from("203.0.113.3")) is None   # released on close


def test_every_exit_path_releases_its_slot(live, monkeypatch):
    """With a cap of one, each path must free its slot, or the next socket
    from the same IP is refused."""
    _caps(monkeypatch, per_ip=1)
    monkeypatch.setattr(main, "WS_AUTH_TIMEOUT_SECONDS", 0.2)
    alice = login("alice")

    def ticket() -> str:
        r = alice.get("/auth/ws-ticket")
        assert r.status_code == 200, r.text
        return r.json()["ticket"]

    def check(path: str) -> None:
        assert _no_open_sockets(), f"slot still held after: {path}"
        assert _refused(live) is None, f"next socket refused after: {path}"

    with live.websocket_connect(WS_PATH):
        pass                                             # client leaves before its ticket
    check("client disconnect before the ticket")

    with live.websocket_connect(WS_PATH) as ws:
        assert _close_code(ws) == main.WS_AUTH_TIMEOUT
    check("auth timeout (4408)")

    with live.websocket_connect(WS_PATH) as ws:
        ws.send_json(auth_message("not-a-jwt"))
        assert _close_code(ws) == main.WS_SESSION_ENDED
    check("invalid ticket (4001)")

    with open_stream(live, ticket()) as ws:
        ws.receive_json()
    check("client disconnect while streaming")

    record = users.get_user("alice")
    real_key = record["session_key"]
    try:
        with open_stream(live, ticket()) as ws:
            record["session_key"] = "rotated-for-this-test"
            assert _close_code(ws) == main.WS_SESSION_ENDED
    finally:
        record["session_key"] = real_key              # alice's sessions valid again
    check("session ended while streaming (4001)")

    with open_stream(live, ticket()) as ws:
        ws.send_text("hello")
        assert _close_code(ws) == 1008
    check("client frame after ready (1008)")


# ── Frames after ready ────────────────────────────────────────

@pytest.mark.parametrize("send", [
    lambda ws: ws.send_text('{"type": "ping"}'),
    lambda ws: ws.send_bytes(b"\x00\x01"),
], ids=["text", "binary"])
def test_client_frame_after_ready_closes_with_1008(live, send):
    with open_stream(live, login("alice").get("/auth/ws-ticket").json()["ticket"]) as ws:
        send(ws)
        assert _close_code(ws) == 1008


def test_stream_without_client_frames_keeps_streaming(live):
    """Guard: the reader must not end a stream whose client stays silent."""
    with open_stream(live, login("alice").get("/auth/ws-ticket").json()["ticket"]) as ws:
        for _ in range(40):
            assert "timestamp" in ws.receive_json()
