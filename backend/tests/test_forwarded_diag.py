"""TEMPORARY DIAGNOSTIC tests: remove together with forwarded_diag.py.

The X-Forwarded-For hash diagnostic is off by default, logs only fixed words,
integers and short salted hashes (never an address, header value, salt,
ticket or cookie), logs only new value combinations, and logs at most 10
lines per process."""
from __future__ import annotations

import logging
import re

import pytest
from starlette.applications import Starlette
from starlette.middleware import Middleware
from starlette.responses import PlainTextResponse
from starlette.routing import Route, WebSocketRoute
from starlette.testclient import TestClient

import forwarded_diag
import main
import rate_limit

H = r"(?:[0-9a-f]{6}|none)"
HTTP_LINE = re.compile(
    rf"\[diag\] forwarded-hash kind=http entries=\d+ pick=-2 pick_hash={H} last_hash={H} peer_hash={H} "
    r"hops=\d+ line=\d+/10"
)
WS_LINE = re.compile(rf"\[diag\] forwarded-hash kind=ws entries=\d+ pick=-1 pick_hash={H} peer_hash={H} hops=\d+ line=\d+/10")

CLIENT = "198.51.100.7"
SECOND_HOP = "203.0.113.9"
SALT = b"fixed-test-salt-value-16"
# Everything a request below carries that must never reach the log. The
# TestClient's TCP peer is "testclient".
SECRETS = (CLIENT, SECOND_HOP, "2001:db8::1", "testclient", "cookie-secret-value", "ticket-secret-value",
           "bearer-secret-value", "sf_session", SALT.decode(), SALT.hex())


async def _api(request):
    return PlainTextResponse("ok")


async def _ws(websocket):
    await websocket.accept()
    await websocket.receive_text()
    await websocket.close()


def _client() -> TestClient:
    """A minimal app behind the diagnostic, built after the env is set (the
    middleware reads the flag when the stack is built)."""
    app = Starlette(
        routes=[Route("/api/x", _api), Route("/health", _api), Route("/", _api),
                WebSocketRoute("/ws/threats", _ws)],
        middleware=[Middleware(forwarded_diag.ForwardedHashDiagnostic)],
    )
    return TestClient(app)


def _http(client: TestClient, xff: str | None = f"{CLIENT}, {SECOND_HOP}") -> None:
    headers = {"Cookie": "sf_session=cookie-secret-value", "Authorization": "Bearer bearer-secret-value"}
    if xff is not None:
        headers["X-Forwarded-For"] = xff
    client.get("/api/x", headers=headers)


def _ws_upgrade(client: TestClient, xff: str = CLIENT) -> None:
    with client.websocket_connect("/ws/threats", headers={"X-Forwarded-For": xff}) as sock:
        sock.send_text('{"type": "auth", "ticket": "ticket-secret-value"}')


def _diag_messages(caplog) -> list[str]:
    return [r.getMessage() for r in caplog.records if r.getMessage().startswith("[diag]")]


def _field(message: str, name: str) -> str:
    return re.search(rf"\b{name}=(\S+)", message).group(1)


@pytest.fixture(autouse=True)
def _fresh(monkeypatch, caplog):
    monkeypatch.setattr(forwarded_diag, "_logged", {"http": 0, "ws": 0})
    monkeypatch.setattr(forwarded_diag, "_seen", {"http": set(), "ws": set()})
    monkeypatch.setattr(forwarded_diag, "_SALT", SALT)
    monkeypatch.setattr(rate_limit, "TRUSTED_PROXY_HOPS_HTTP", 1)
    monkeypatch.setattr(rate_limit, "TRUSTED_PROXY_HOPS_WS", 1)
    caplog.set_level(logging.DEBUG)


def test_wired_into_the_app():
    assert any(m.cls is forwarded_diag.ForwardedHashDiagnostic for m in main.app.user_middleware)


@pytest.mark.parametrize("value", [None, "", "false", "1", "yes", "on"])
def test_off_unless_exactly_true(monkeypatch, caplog, value):
    if value is None:
        monkeypatch.delenv(forwarded_diag.ENV_FLAG, raising=False)
    else:
        monkeypatch.setenv(forwarded_diag.ENV_FLAG, value)
    client = _client()
    _http(client)
    _ws_upgrade(client)
    assert _diag_messages(caplog) == []


def test_line_format(monkeypatch, caplog):
    monkeypatch.setenv(forwarded_diag.ENV_FLAG, "true")
    client = _client()
    _http(client)
    _ws_upgrade(client)
    _http(client, xff=None)                                # no X-Forwarded-For at all
    h = forwarded_diag.short_hash
    assert _diag_messages(caplog) == [
        f"[diag] forwarded-hash kind=http entries=2 pick=-2 pick_hash={h(CLIENT)} last_hash={h(SECOND_HOP)} "
        f"peer_hash={h('testclient')} hops=1 line=1/10",
        f"[diag] forwarded-hash kind=ws entries=1 pick=-1 pick_hash={h(CLIENT)} peer_hash={h('testclient')} "
        f"hops=1 line=2/10",
        f"[diag] forwarded-hash kind=http entries=0 pick=-2 pick_hash=none last_hash=none "
        f"peer_hash={h('testclient')} hops=1 line=3/10",
    ]


def test_http_pick_and_websocket_pick_of_one_address_match(monkeypatch, caplog):
    # The comparison the diagnostic exists for.
    monkeypatch.setenv(forwarded_diag.ENV_FLAG, "true")
    client = _client()
    _http(client)
    _ws_upgrade(client)
    http, ws = _diag_messages(caplog)
    assert _field(http, "pick_hash") == _field(ws, "pick_hash")
    assert _field(http, "last_hash") != _field(ws, "pick_hash")


def test_different_addresses_give_different_hashes():
    assert forwarded_diag.short_hash(CLIENT) != forwarded_diag.short_hash(SECOND_HOP)
    assert re.fullmatch(r"[0-9a-f]{6}", forwarded_diag.short_hash(CLIENT))


def test_a_new_salt_changes_the_hash(monkeypatch):
    before = forwarded_diag.short_hash(CLIENT)
    monkeypatch.setattr(forwarded_diag, "_SALT", b"another-salt-value-16b")
    assert forwarded_diag.short_hash(CLIENT) != before


def test_no_address_salt_or_secret_ever_reaches_the_log(monkeypatch, caplog):
    monkeypatch.setenv(forwarded_diag.ENV_FLAG, "TRUE")
    client = _client()
    for xff in (f"{CLIENT}, {SECOND_HOP}", f"6.6.6.6, {CLIENT}, {SECOND_HOP}", None):
        _http(client, xff=xff)
    for xff in (CLIENT, "2001:db8::1", f"6.6.6.6, {CLIENT}"):
        _ws_upgrade(client, xff=xff)
    records = [r for r in caplog.records if r.getMessage().startswith("[diag]")]
    assert len(records) == 6
    for record in records:
        message = record.getMessage()
        assert HTTP_LINE.fullmatch(message) or WS_LINE.fullmatch(message), message
        text = message + repr(record.args)
        for secret in SECRETS:
            assert secret not in text


def test_repeated_values_are_logged_once(monkeypatch, caplog):
    monkeypatch.setenv(forwarded_diag.ENV_FLAG, "true")
    client = _client()
    for _ in range(4):
        _http(client)
        _ws_upgrade(client)
    _http(client, xff=f"192.0.2.1, {SECOND_HOP}")          # a second device: new pick
    kinds = [_field(m, "kind") for m in _diag_messages(caplog)]
    assert kinds == ["http", "ws", "http"]


def test_other_paths_are_not_logged(monkeypatch, caplog):
    monkeypatch.setenv(forwarded_diag.ENV_FLAG, "true")
    client = _client()
    client.get("/health", headers={"X-Forwarded-For": CLIENT})
    client.get("/", headers={"X-Forwarded-For": CLIENT})
    assert _diag_messages(caplog) == []


def test_at_most_ten_lines_per_process(monkeypatch, caplog):
    monkeypatch.setenv(forwarded_diag.ENV_FLAG, "true")
    for client in (_client(), _client()):                  # a rebuilt stack shares the cap
        for i in range(10):
            _http(client, xff=f"192.0.2.{i}, {SECOND_HOP}")
            _ws_upgrade(client, xff=f"192.0.2.{i}")
    kinds = [_field(m, "kind") for m in _diag_messages(caplog)]
    assert len(kinds) == forwarded_diag.MAX_LINES == 10
    assert kinds.count("http") == 5 and kinds.count("ws") == 5
