"""client_ip fails closed when X-Forwarded-For has fewer entries than hops.

Measured on Render: uvicorn trusts every peer (FORWARDED_ALLOW_IPS='*') and
puts the leftmost, client-chosen entry into scope["client"]. So the socket
address is not a safe fallback: a short chain gets one fixed key for
everyone, and one warning per process (docs/DECISIONS.md)."""
from __future__ import annotations

import logging

import pytest
from starlette.requests import HTTPConnection

import rate_limit
from rate_limit import SHORT_CHAIN_KEY, client_ip

FORGED = "203.0.113.9"      # what a client writes into its own header
CLIENT = "198.51.100.10"
PROXY = "203.0.113.20"
PEER = "10.0.0.1"


def _conn(kind: str, entries: list[str], peer: str = PEER) -> HTTPConnection:
    headers = [(b"x-forwarded-for", ", ".join(entries).encode())] if entries else []
    return HTTPConnection({"type": kind, "path": "/", "headers": headers, "client": (peer, 1234)})


@pytest.fixture(autouse=True)
def _fresh_warning(monkeypatch):
    monkeypatch.setattr(rate_limit, "_short_chain_warned", False)


def _hops(monkeypatch, http: int, ws: int) -> None:
    monkeypatch.setattr(rate_limit, "TRUSTED_PROXY_HOPS_HTTP", http)
    monkeypatch.setattr(rate_limit, "TRUSTED_PROXY_HOPS_WS", ws)


def _warnings(caplog) -> list[logging.LogRecord]:
    return [r for r in caplog.records if r.name == "uvicorn.error" and r.levelno == logging.WARNING]


@pytest.mark.parametrize("kind, entries", [
    ("http", []), ("http", [FORGED]),
    ("websocket", []), ("websocket", [FORGED]),
])
def test_short_chain_gets_the_fixed_key_not_the_peer(monkeypatch, kind, entries):
    _hops(monkeypatch, http=2, ws=2)
    key = client_ip(_conn(kind, entries))
    assert key == SHORT_CHAIN_KEY
    assert key != PEER


def test_a_forged_peer_does_not_change_the_short_chain_key(monkeypatch):
    # As on Render with '*': uvicorn has already put the forged entry in client.
    _hops(monkeypatch, http=2, ws=1)
    assert client_ip(_conn("http", [FORGED], peer=FORGED)) == SHORT_CHAIN_KEY


def test_different_peers_share_the_short_chain_key(monkeypatch):
    _hops(monkeypatch, http=2, ws=1)
    keys = {client_ip(_conn("http", [CLIENT], peer=p)) for p in ("10.0.0.1", "10.0.0.2", FORGED)}
    assert keys == {SHORT_CHAIN_KEY}


def test_the_fixed_key_is_not_an_address():
    import ipaddress
    with pytest.raises(ValueError):
        ipaddress.ip_address(SHORT_CHAIN_KEY)


def test_zero_hops_uses_the_peer_and_does_not_warn(monkeypatch, caplog):
    _hops(monkeypatch, http=0, ws=0)
    with caplog.at_level(logging.WARNING, logger="uvicorn.error"):
        assert client_ip(_conn("http", [FORGED])) == PEER
        assert client_ip(_conn("websocket", [])) == PEER
    assert _warnings(caplog) == []


def test_a_full_chain_does_not_warn(monkeypatch, caplog):
    _hops(monkeypatch, http=2, ws=1)
    with caplog.at_level(logging.WARNING, logger="uvicorn.error"):
        assert client_ip(_conn("http", [FORGED, CLIENT, PROXY])) == CLIENT
        assert client_ip(_conn("websocket", [CLIENT])) == CLIENT
    assert _warnings(caplog) == []


def test_short_chains_warn_once_per_process(monkeypatch, caplog):
    _hops(monkeypatch, http=2, ws=2)
    with caplog.at_level(logging.WARNING, logger="uvicorn.error"):
        for _ in range(3):
            client_ip(_conn("http", [FORGED]))
            client_ip(_conn("websocket", []))
    records = _warnings(caplog)
    assert len(records) == 1
    assert records[0].getMessage() == (
        "X-Forwarded-For has 1 entries, fewer than TRUSTED_PROXY_HOPS_HTTP=2; per-IP limits share one bucket"
    )


def test_the_warning_names_the_websocket_variable(monkeypatch, caplog):
    _hops(monkeypatch, http=1, ws=2)
    with caplog.at_level(logging.WARNING, logger="uvicorn.error"):
        client_ip(_conn("websocket", [CLIENT]))
    assert "TRUSTED_PROXY_HOPS_WS=2" in _warnings(caplog)[0].getMessage()


def test_the_warning_carries_no_address_or_header_value(monkeypatch, caplog):
    _hops(monkeypatch, http=3, ws=1)
    with caplog.at_level(logging.WARNING, logger="uvicorn.error"):
        client_ip(_conn("http", [FORGED, CLIENT], peer=PEER))
    record = _warnings(caplog)[0]
    text = record.getMessage() + " " + repr(record.args)
    for value in (FORGED, CLIENT, PEER):
        assert value not in text
