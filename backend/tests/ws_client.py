"""Test helpers for the live stream: the ticket is sent as the first message."""
from __future__ import annotations

from contextlib import contextmanager
from typing import Iterator

from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

WS_PATH = "/ws/threats"
READY = {"type": "ready"}


def auth_message(ticket: str) -> dict:
    return {"type": "auth", "ticket": ticket}


@contextmanager
def open_stream(client: TestClient, ticket: str) -> Iterator:
    """An authenticated stream: connect, send the ticket, expect ready."""
    with client.websocket_connect(WS_PATH) as ws:
        ws.send_json(auth_message(ticket))
        assert ws.receive_json() == READY
        yield ws


def ws_accepts(client: TestClient, ticket: str) -> bool:
    """Send the ticket and wait only for the server's answer (ready or close),
    never for an event, so a wrongly accepted ticket fails the test instead of
    hanging it."""
    try:
        with client.websocket_connect(WS_PATH) as ws:
            ws.send_json(auth_message(ticket))
            return ws.receive_json() == READY
    except WebSocketDisconnect:
        return False
