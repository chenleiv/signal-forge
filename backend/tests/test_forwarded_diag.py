"""TEMPORARY DIAGNOSTIC tests: remove together with forwarded_diag.py.

The X-Forwarded-For count diagnostic is off by default, logs only fixed words
and integers (never an address, header value, ticket or cookie), and logs at
most 10 lines per process."""
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

LINE = re.compile(
    r"\[diag\] forwarded-count kind=(http|ws) xff=(present|absent) entries=\d+ "
    r"trusted_proxy_hops=\d+ line=\d+/10"
)
# Everything a request below carries that must never reach the log.
SECRETS = ("198.51.100.7", "203.0.113.9", "2001:db8::1", "testclient",
           "cookie-secret-value", "ticket-secret-value", "bearer-secret-value", "sf_session")


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
        middleware=[Middleware(forwarded_diag.ForwardedCountDiagnostic)],
    )
    return TestClient(app)


def _traffic(client: TestClient, http: int = 1, ws: int = 1) -> None:
    for _ in range(http):
        client.get("/api/x", headers={
            "X-Forwarded-For": "198.51.100.7, 203.0.113.9",
            "Cookie": "sf_session=cookie-secret-value",
            "Authorization": "Bearer bearer-secret-value",
        })
    for _ in range(ws):
        with client.websocket_connect("/ws/threats", headers={"X-Forwarded-For": "2001:db8::1"}) as sock:
            sock.send_text('{"type": "auth", "ticket": "ticket-secret-value"}')


def _diag_records(caplog) -> list[logging.LogRecord]:
    return [r for r in caplog.records if r.getMessage().startswith("[diag]")]


@pytest.fixture(autouse=True)
def _fresh(monkeypatch, caplog):
    monkeypatch.setattr(forwarded_diag, "_logged", {"http": 0, "ws": 0})
    monkeypatch.setattr(rate_limit, "TRUSTED_PROXY_HOPS", 1)
    caplog.set_level(logging.DEBUG)


def test_wired_into_the_app():
    assert any(m.cls is forwarded_diag.ForwardedCountDiagnostic for m in main.app.user_middleware)


@pytest.mark.parametrize("value", [None, "", "false", "1", "yes", "on"])
def test_off_unless_exactly_true(monkeypatch, caplog, value):
    if value is None:
        monkeypatch.delenv(forwarded_diag.ENV_FLAG, raising=False)
    else:
        monkeypatch.setenv(forwarded_diag.ENV_FLAG, value)
    _traffic(_client(), http=3, ws=3)
    assert _diag_records(caplog) == []


def test_on_logs_kind_presence_and_count_only(monkeypatch, caplog):
    monkeypatch.setenv(forwarded_diag.ENV_FLAG, "true")
    client = _client()
    _traffic(client, http=1, ws=1)
    client.get("/api/x")                                   # no X-Forwarded-For at all
    messages = [r.getMessage() for r in _diag_records(caplog)]
    assert messages == [
        "[diag] forwarded-count kind=http xff=present entries=2 trusted_proxy_hops=1 line=1/10",
        "[diag] forwarded-count kind=ws xff=present entries=1 trusted_proxy_hops=1 line=2/10",
        "[diag] forwarded-count kind=http xff=absent entries=0 trusted_proxy_hops=1 line=3/10",
    ]


def test_no_address_or_secret_ever_reaches_the_log(monkeypatch, caplog):
    monkeypatch.setenv(forwarded_diag.ENV_FLAG, "TRUE")
    _traffic(_client(), http=3, ws=3)
    records = _diag_records(caplog)
    assert records
    for record in records:
        text = record.getMessage() + repr(record.args)
        assert LINE.fullmatch(record.getMessage()), record.getMessage()
        for secret in SECRETS:
            assert secret not in text


def test_other_paths_are_not_logged(monkeypatch, caplog):
    monkeypatch.setenv(forwarded_diag.ENV_FLAG, "true")
    client = _client()
    client.get("/health", headers={"X-Forwarded-For": "198.51.100.7"})
    client.get("/", headers={"X-Forwarded-For": "198.51.100.7"})
    assert _diag_records(caplog) == []


def test_at_most_ten_lines_per_process(monkeypatch, caplog):
    monkeypatch.setenv(forwarded_diag.ENV_FLAG, "true")
    _traffic(_client(), http=20, ws=20)
    _traffic(_client(), http=5, ws=5)                      # a rebuilt stack shares the cap
    records = _diag_records(caplog)
    assert len(records) == forwarded_diag.MAX_LINES == 10
    kinds = [re.search(r"kind=(\w+)", r.getMessage()).group(1) for r in records]
    assert kinds.count("http") == 5 and kinds.count("ws") == 5
