"""Regression test: several WebSocket clients must share ONE event stream.

Before the fix, every connection ran its own generator and wrote into the
global store, so N open tabs produced N x the events (inflated stats,
alerts and incidents).
"""
import os

# Isolate from the developer's .env: no DB, no external APIs.
for key in ("DATABASE_URL", "ABUSEIPDB_API_KEY", "IPINFO_TOKEN", "GROQ_API_KEY"):
    os.environ[key] = ""
os.environ["ENV"] = "development"

from fastapi.testclient import TestClient  # noqa: E402

from tests.conftest import ANALYST_PASSWORD  # noqa: E402

import main  # noqa: E402
import simulation  # noqa: E402
import store  # noqa: E402

N = 20


async def _fake_refresh(allow_sample: bool = False) -> None:
    simulation.THREAT_IPS = {"8.8.8.8": 90, "1.1.1.1": 70, "9.9.9.9": 50}


def _ticket(client: TestClient) -> str:
    client.post("/auth/login", json={"username": "alice", "password": ANALYST_PASSWORD})
    return client.get("/auth/ws-ticket").json()["ticket"]


def test_two_clients_share_one_stream(monkeypatch):
    monkeypatch.setattr(main, "refresh_threat_ips", _fake_refresh)
    monkeypatch.setattr(main, "STREAM_INTERVAL", (0.01, 0.02), raising=False)

    with TestClient(main.app) as client:
        t1, t2 = _ticket(client), _ticket(client)
        store.ip_store.clear()

        with client.websocket_connect(f"/ws/threats?ticket={t1}") as ws1, \
             client.websocket_connect(f"/ws/threats?ticket={t2}") as ws2:
            seen1 = {ws1.receive_json()["timestamp"] for _ in range(N)}
            seen2 = {ws2.receive_json()["timestamp"] for _ in range(N)}

    # Same stream -> both tabs receive (mostly) the same events.
    assert len(seen1 & seen2) >= N // 2, f"clients saw different streams ({len(seen1 & seen2)} shared)"
