"""Demo mode shows simulated IP addresses only (docs/DECISIONS.md).

- The feed, the live stream, the backfill, alerts, incidents and stats only
  ever carry addresses of the simulated pool (RFC 5737 documentation ranges).
- Lookups accept only pool addresses; any other address is refused with a 4xx
  before AbuseIPDB, ipinfo or Groq can be called.
- Stored incidents whose source IP is outside the pool are not returned.
- With DEMO_MODE=false nothing of this applies.
"""
from __future__ import annotations

import asyncio
import ipaddress
import json
from collections import defaultdict, deque
from datetime import datetime, timezone
from types import SimpleNamespace

import groq
import httpx
import pytest
from fastapi.testclient import TestClient

import main
import simulation as m
import store
from db_ops import db_create_incident
from routers import ip as ip_router
from simulated_pool import SIMULATED_GEO, SIMULATED_IPS, SIMULATED_NETWORKS, SIMULATED_ORG
from tests.conftest import session_client

REAL_IP = "8.8.8.8"
POOL_IP = next(iter(SIMULATED_IPS))
LOOKUP_ROUTES = ("history", "geo", "ai-summary", "related", "block", "case")


def _in_pool(ip: object) -> bool:
    return isinstance(ip, str) and ip in SIMULATED_IPS


# ── Fixtures ──────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def _isolated_state(monkeypatch):
    """Fresh in-memory state, so nothing leaks into other tests."""
    monkeypatch.setattr(store, "ip_store", defaultdict(lambda: deque(maxlen=200)))
    monkeypatch.setattr(store, "minute_buckets", deque(maxlen=15))
    monkeypatch.setattr(store, "alerts_store", deque(maxlen=100))
    monkeypatch.setattr(store, "incidents_store", deque(maxlen=50))
    monkeypatch.setattr(store, "_current_minute", "")
    monkeypatch.setattr(store, "_current_bucket_count", 0)
    monkeypatch.setattr(ip_router, "ip_store", store.ip_store)
    monkeypatch.setattr(m, "THREAT_IPS", {})
    monkeypatch.setattr(m, "FEED_STATUS", {"state": "unavailable", "reason": None})
    for cache in ("_abuse_cache", "_geo_cache", "_ai_summary_cache"):
        monkeypatch.setattr(ip_router, cache, {})


@pytest.fixture
def demo(monkeypatch):
    monkeypatch.setattr(store, "DEMO_MODE", True)
    monkeypatch.setattr(main, "DEMO_MODE", True)


@pytest.fixture
def no_demo(monkeypatch):
    monkeypatch.setattr(store, "DEMO_MODE", False)
    monkeypatch.setattr(main, "DEMO_MODE", False)


class FakeGroq:
    prompts: list[str] = []

    def __init__(self, **_):
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._create))

    async def _create(self, **kwargs):
        FakeGroq.prompts.append(kwargs["messages"][0]["content"])
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content="A summary."))])


@pytest.fixture
def external(monkeypatch):
    """Every outbound call the backend can make, recorded: httpx (AbuseIPDB,
    ipinfo) and Groq. Keys are set, so only the code decides whether to call."""
    calls: list[str] = []

    async def send(self, request, *args, **kwargs):
        calls.append(str(request.url.host))
        if request.url.host == "ipinfo.io":
            body = {"country": "US", "city": "Mountain View", "org": "AS15169 Google LLC", "loc": "37.4,-122.1"}
        else:
            body = {"data": {"abuseConfidenceScore": 0, "countryCode": "US", "isp": "Google", "totalReports": 1}}
        return httpx.Response(200, json=body, request=request)

    monkeypatch.setattr(httpx.AsyncClient, "send", send)
    FakeGroq.prompts = []

    def groq_factory(**kw):
        calls.append("groq")
        return FakeGroq(**kw)

    monkeypatch.setattr(groq, "AsyncGroq", groq_factory)
    monkeypatch.setattr(ip_router, "ABUSEIPDB_API_KEY", "test-key")
    monkeypatch.setattr(ip_router, "IPINFO_TOKEN", "test-token")
    monkeypatch.setattr(ip_router, "GROQ_API_KEY", "test-key")
    return calls


def _event(ip: str) -> dict:
    return {
        "ip": ip, "score": 70, "threat_level": "high", "attack_type": "SQLi", "region": "EU",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


def _incident(n: int, ip: str | None) -> dict:
    now = datetime.now(timezone.utc).isoformat()
    return {
        "id": f"INC-{9000 + n}", "title": f"Case {n}", "severity": "high", "status": "open",
        "attack_type": "SQLi", "source_ip": ip, "source_region": "EU", "event_count": 1,
        "assigned_to": None, "created_at": now, "updated_at": now, "mitre_tags": [],
        "notes": [], "completed_tasks": [],
    }


# ── The pool ──────────────────────────────────────────────────

def test_pool_is_documentation_ranges_only():
    assert len(SIMULATED_IPS) == 36
    for ip, score in SIMULATED_IPS.items():
        addr = ipaddress.ip_address(ip)
        assert any(addr in net for net in SIMULATED_NETWORKS), ip
        assert not store.is_public_ip(ip), ip
        assert 0 <= score <= 100


def test_pool_geolocation_is_simulated():
    assert set(SIMULATED_GEO) == set(SIMULATED_IPS)
    for geo in SIMULATED_GEO.values():
        assert geo["org"] == SIMULATED_ORG
        assert 64496 <= int(geo["asn"].removeprefix("AS")) <= 64511
        assert {"lat", "lng", "country", "country_code", "city", "timezone"} <= set(geo)


def test_use_simulated_feed_sets_the_pool_and_the_status():
    m.use_simulated_feed()
    assert m.THREAT_IPS == SIMULATED_IPS
    assert m.FEED_STATUS == {"state": "simulated", "reason": None}
    assert all(_in_pool(m.generate_threat()["ip"]) for _ in range(2000))


# ── Demo startup, stream, alerts, incidents ───────────────────

async def _never(**_):
    raise AssertionError("demo mode must not refresh the AbuseIPDB feed")


def test_demo_startup_streams_only_pool_ips_and_calls_nothing(demo, external, monkeypatch):
    monkeypatch.setattr(main, "refresh_threat_ips", _never)
    monkeypatch.setattr(main, "IPINFO_TOKEN", "test-token")  # the prefetch must still not run

    with TestClient(main.app):
        client = session_client("alice", "analyst")
        stats = client.get("/api/stats").json()
        feed = client.get("/api/threat-feed").json()

    assert feed == {"state": "simulated", "reason": None}
    assert stats["top_ips"] and all(_in_pool(row["ip"]) for row in stats["top_ips"])
    assert sum(stats["severity_counts"].values()) == m.MAX_BACKFILL_EVENTS  # backfilled
    assert all(_in_pool(ip) for ip in store.ip_store)
    assert external == []


def test_live_stream_alerts_and_incidents_carry_pool_ips_only(demo, monkeypatch):
    m.use_simulated_feed()
    monkeypatch.setattr(main, "STREAM_INTERVAL", (0.0, 0.0))
    # A rule that fires on every event, so alerts, incidents and blocks are made.
    monkeypatch.setattr(store, "_rules", [{
        "id": "r1", "name": "Every event", "enabled": True, "logic": "AND", "match_count": 0,
        "conditions": [{"field": "score", "operator": ">", "value": "-1"}],
        "actions": ["alert", "incident"],
    }])

    async def collect(n: int) -> list[dict]:
        queue: asyncio.Queue[str] = asyncio.Queue(maxsize=n)
        main._clients.add(queue)
        task = asyncio.create_task(main._stream_loop())
        try:
            return [json.loads(await asyncio.wait_for(queue.get(), 5)) for _ in range(n)]
        finally:
            task.cancel()
            main._clients.discard(queue)

    events = asyncio.run(collect(300))
    assert all(_in_pool(e["ip"]) for e in events)
    assert store.alerts_store and all(_in_pool(a["ip"]) for a in store.alerts_store)
    assert store.incidents_store and all(_in_pool(i["source_ip"]) for i in store.incidents_store)


# ── Lookups in demo mode ──────────────────────────────────────

@pytest.mark.parametrize("route", LOOKUP_ROUTES)
@pytest.mark.parametrize("target", [REAL_IP, "1.1.1.1", "10.0.0.1", "192.0.2.0"])
def test_demo_refuses_ips_outside_the_pool_without_an_external_call(demo, external, route, target):
    store.ip_store[target].append(_event(target))  # even an IP with events is refused
    r = session_client("alice", "analyst").get(f"/api/ip/{target}/{route}")
    assert r.status_code == 404
    assert r.json() == {"detail": store.DEMO_UNKNOWN_IP}
    assert external == []


@pytest.mark.parametrize("route", LOOKUP_ROUTES)
def test_demo_rejects_a_malformed_ip_as_before(demo, external, route):
    r = session_client("alice", "analyst").get(f"/api/ip/not-an-ip/{route}")
    assert r.status_code == 422
    assert external == []


def test_demo_geo_and_history_for_a_pool_ip_are_simulated(demo, external):
    store.ip_store[POOL_IP].append(_event(POOL_IP))
    client = session_client("alice", "analyst")

    geo = client.get(f"/api/ip/{POOL_IP}/geo")
    assert geo.status_code == 200 and geo.json() == SIMULATED_GEO[POOL_IP]

    history = client.get(f"/api/ip/{POOL_IP}/history")
    assert history.status_code == 200
    body = history.json()
    assert body["ip"] == POOL_IP and len(body["events"]) == 1
    assert not {"abuse_confidence", "isp", "total_reports"} & set(body)
    assert external == []


def test_demo_ai_summary_sends_only_simulated_data_to_groq(demo, external):
    m.use_simulated_feed()
    for _ in range(20):
        event = m.generate_threat()
        store._record_event(event)
    ip = next(iter(store.ip_store))

    r = session_client("alice", "analyst").get(f"/api/ip/{ip}/ai-summary")
    assert r.status_code == 200 and r.json() == {"summary": "A summary."}
    assert external == ["groq"]
    (prompt,) = FakeGroq.prompts
    context = json.loads(prompt[prompt.index("{"):prompt.rindex("}") + 1])
    assert context["ip"] == ip and _in_pool(ip)
    # No other address of any kind in what was sent.
    words = prompt.replace('"', " ").replace(",", " ").split()
    assert [w for w in words if w.count(".") == 3 and w != ip and w.rstrip(".") != ip] == []


# ── Stored incidents in demo mode ─────────────────────────────

def test_demo_hides_in_memory_incidents_outside_the_pool(demo):
    for n, ip in enumerate([REAL_IP, POOL_IP, None]):
        store.incidents_store.append(_incident(n, ip))
    r = session_client("alice", "analyst").get("/api/incidents")
    assert r.status_code == 200
    assert [i["source_ip"] for i in r.json()] == [POOL_IP]


def test_demo_hides_database_incidents_outside_the_pool(demo, db_app):
    async def seed(session):
        for n, ip in enumerate([REAL_IP, POOL_IP, None, "1.1.1.1"]):
            await db_create_incident(session, _incident(n, ip))
    db_app(seed)

    r = session_client("alice", "analyst").get("/api/incidents")
    assert r.status_code == 200
    assert [i["source_ip"] for i in r.json()] == [POOL_IP]
    # The stored rows are kept, only hidden.
    from db_ops import db_get_incidents
    assert len(db_app(db_get_incidents)) == 4


def test_demo_case_lookup_never_reveals_a_real_ip_case(demo, db_app):
    async def seed(session):
        await db_create_incident(session, _incident(1, REAL_IP))
    db_app(seed)
    r = session_client("alice", "analyst").get(f"/api/ip/{REAL_IP}/case")
    assert r.status_code == 404


# ── DEMO_MODE=false keeps the old behaviour ───────────────────

def test_non_demo_startup_uses_the_abuseipdb_feed(no_demo, monkeypatch):
    seen: list[dict] = []

    async def refresh(**kwargs):
        seen.append(kwargs)
        m.THREAT_IPS = {REAL_IP: 90}
        m.FEED_STATUS.update(state="live", reason=None)

    monkeypatch.setattr(main, "refresh_threat_ips", refresh)
    with TestClient(main.app):
        feed = session_client("alice", "analyst").get("/api/threat-feed").json()

    assert len(seen) == 1 and seen[0]["allow_sample"] is False
    assert feed == {"state": "live", "reason": None}
    assert m.THREAT_IPS == {REAL_IP: 90}
    assert m.generate_threat()["ip"] == REAL_IP


def test_non_demo_lookups_call_the_services_as_before(no_demo, external):
    store.ip_store[REAL_IP].append(_event(REAL_IP))
    client = session_client("alice", "analyst")

    history = client.get(f"/api/ip/{REAL_IP}/history").json()
    assert history["isp"] == "Google"
    geo = client.get(f"/api/ip/{REAL_IP}/geo").json()
    assert geo["org"] == "Google LLC"
    assert client.get(f"/api/ip/{REAL_IP}/ai-summary").json() == {"summary": "A summary."}
    assert external == ["api.abuseipdb.com", "ipinfo.io", "groq"]


@pytest.mark.parametrize("route", LOOKUP_ROUTES)
def test_non_demo_still_refuses_documentation_ranges(no_demo, external, route):
    r = session_client("alice", "analyst").get(f"/api/ip/{POOL_IP}/{route}")
    assert r.status_code == 422
    assert r.json() == {"detail": "Private or reserved IP not allowed"}
    assert external == []


def test_non_demo_lists_every_incident(no_demo):
    for n, ip in enumerate([REAL_IP, POOL_IP, None]):
        store.incidents_store.append(_incident(n, ip))
    r = session_client("alice", "analyst").get("/api/incidents")
    assert [i["source_ip"] for i in r.json()] == [REAL_IP, POOL_IP, None]
