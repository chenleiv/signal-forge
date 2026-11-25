"""Quotas for the routes that call external services (finding L8): per user
AND client IP, counted only when the service is really called, plus one
daily cap for all AI summaries."""
from __future__ import annotations

import time
from collections import deque
from types import SimpleNamespace

import groq
import pytest
from limits import parse_many

import rate_limit
from rate_limit import KeyedLimit, user_ip_key
from routers import ip as ip_router
from tests.conftest import session_client

TARGET = "8.8.4.4"


def _get(client, path, client_ip="198.51.100.40"):
    return client.get(path, headers={"X-Forwarded-For": client_ip})


def _retry_after(r) -> int:
    return int(r.headers["Retry-After"])


# ── AI summary (Groq) ─────────────────────────────────────────

class FakeGroq:
    calls = 0
    fail = False

    def __init__(self, **_):
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._create))

    async def _create(self, **_):
        FakeGroq.calls += 1
        if FakeGroq.fail:
            raise TimeoutError("slow upstream")
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content="A summary."))])


@pytest.fixture
def fake_groq(monkeypatch):
    FakeGroq.calls = 0
    FakeGroq.fail = False
    monkeypatch.setattr(groq, "AsyncGroq", FakeGroq)
    monkeypatch.setattr(ip_router, "GROQ_API_KEY", "test-key")
    monkeypatch.setattr(ip_router, "_ai_summary_cache", {})
    return FakeGroq


def _summary(client, n, client_ip="198.51.100.40"):
    return _get(client, f"/api/ip/8.8.8.{n}/ai-summary", client_ip)


def test_ai_summary_quota_per_user_and_ip(fake_groq):
    alice = session_client("alice", "analyst")
    assert [_summary(alice, n).status_code for n in range(1, 6)] == [200] * 5
    r = _summary(alice, 6)
    assert r.status_code == 429
    assert r.json() == {"detail": "AI summary limit reached, try again later"}
    assert 1 <= _retry_after(r) <= 60
    assert fake_groq.calls == 5


def test_ai_summary_quota_is_separate_per_ip_and_per_user(fake_groq):
    alice = session_client("alice", "analyst")
    for n in range(1, 7):
        _summary(alice, n)
    # Same user, another address (e.g. another visitor on the demo account).
    assert _summary(alice, 7, client_ip="198.51.100.41").status_code == 200
    # Another user at the same address.
    assert _summary(session_client("bob", "analyst"), 8).status_code == 200


def test_cached_summaries_are_free_after_the_quota_is_used(fake_groq):
    alice = session_client("alice", "analyst")
    for n in range(1, 7):
        _summary(alice, n)
    calls = fake_groq.calls
    r = _summary(alice, 1)
    assert r.status_code == 200 and r.json() == {"summary": "A summary."}
    assert fake_groq.calls == calls


def test_no_groq_key_counts_nothing(fake_groq, monkeypatch):
    monkeypatch.setattr(ip_router, "GROQ_API_KEY", "")
    alice = session_client("alice", "analyst")
    assert {_summary(alice, n).json()["summary"] for n in range(1, 9)} == {None}
    monkeypatch.setattr(ip_router, "GROQ_API_KEY", "test-key")
    assert _summary(alice, 9, client_ip="198.51.100.42").status_code == 200


def test_failed_groq_calls_count_toward_the_quota(fake_groq):
    fake_groq.fail = True
    alice = session_client("alice", "analyst")
    assert [_summary(alice, n).json() for n in range(1, 6)] == [{"summary": None}] * 5
    assert _summary(alice, 6).status_code == 429


def test_global_daily_cap_covers_every_user_and_address(fake_groq, monkeypatch):
    monkeypatch.setattr(rate_limit.AI_SUMMARY_GLOBAL, "items", parse_many("3/day"))
    clients = [session_client(u, "analyst") for u in ("alice", "bob")]
    codes = [_summary(clients[n % 2], n, client_ip=f"198.51.100.{50 + n}").status_code for n in range(1, 4)]
    assert codes == [200] * 3
    r = _summary(clients[0], 4, client_ip="198.51.100.60")
    assert r.status_code == 429
    assert _retry_after(r) > 60          # the daily window
    assert fake_groq.calls == 3


def test_a_refusal_by_the_global_cap_does_not_use_the_user_quota(fake_groq, monkeypatch):
    monkeypatch.setattr(rate_limit.AI_SUMMARY_GLOBAL, "items", parse_many("1/day"))
    alice = session_client("alice", "analyst")
    _summary(alice, 1)
    for n in range(2, 7):
        assert _summary(alice, n).status_code == 429
    key = user_ip_key("alice", SimpleNamespace(scope={"type": "http"}, headers=_Headers("198.51.100.40")))
    assert not rate_limit.AI_SUMMARY_PER_USER_IP.exceeded(key)


class _Headers:
    def __init__(self, xff):
        self.xff = xff

    def getlist(self, name):
        return [self.xff] if name == "x-forwarded-for" else []


# ── Geolocation (ipinfo) ──────────────────────────────────────

@pytest.fixture
def fake_ipinfo(monkeypatch):
    calls = []

    async def fetch(_client, ip):
        calls.append(ip)
        return None                         # a failed lookup: never cached with a token

    monkeypatch.setattr(ip_router, "fetch_ipinfo", fetch)
    monkeypatch.setattr(ip_router, "IPINFO_TOKEN", "test-token")
    monkeypatch.setattr(ip_router, "_geo_cache", {})
    return calls


def test_geo_quota_per_user_and_ip(fake_ipinfo):
    alice = session_client("alice", "analyst")
    assert {_get(alice, f"/api/ip/{TARGET}/geo").status_code for _ in range(20)} == {200}
    r = _get(alice, f"/api/ip/{TARGET}/geo")
    assert r.status_code == 429
    assert r.json() == {"detail": "Geolocation limit reached, try again later"}
    assert 1 <= _retry_after(r) <= 60
    assert len(fake_ipinfo) == 20
    assert _get(alice, f"/api/ip/{TARGET}/geo", client_ip="198.51.100.43").status_code == 200


def test_cached_geo_is_free_after_the_quota_is_used(fake_ipinfo):
    alice = session_client("alice", "analyst")
    for _ in range(21):
        _get(alice, f"/api/ip/{TARGET}/geo")
    ip_router._geo_cache["1.1.1.1"] = {"country": "Australia"}
    assert _get(alice, "/api/ip/1.1.1.1/geo").json() == {"country": "Australia"}


def test_geo_without_a_token_counts_nothing(fake_ipinfo, monkeypatch):
    monkeypatch.setattr(ip_router, "IPINFO_TOKEN", "")
    alice = session_client("alice", "analyst")
    assert {_get(alice, f"/api/ip/8.8.8.{n}/geo").status_code for n in range(1, 26)} == {200}
    assert fake_ipinfo == []


# ── IP history (AbuseIPDB enrichment) ─────────────────────────

@pytest.fixture
def fake_abuseipdb(monkeypatch):
    calls = []

    async def enrich(ip):
        calls.append(ip)
        return {"abuse_confidence": 90}

    monkeypatch.setattr(ip_router, "enrich_ip", enrich)
    monkeypatch.setattr(ip_router, "ABUSEIPDB_API_KEY", "test-key")
    monkeypatch.setattr(ip_router, "_abuse_cache", {})
    event = {"score": 80, "region": "US", "attack_type": "SQLi", "threat_level": "high"}
    monkeypatch.setitem(ip_router.ip_store, TARGET, deque([event]))
    return calls


def test_history_quota_skips_only_the_lookup(fake_abuseipdb):
    alice = session_client("alice", "analyst")
    for _ in range(20):
        r = _get(alice, f"/api/ip/{TARGET}/history")
        assert r.status_code == 200 and r.json()["abuse_confidence"] == 90
    r = _get(alice, f"/api/ip/{TARGET}/history")
    assert r.status_code == 200
    assert len(r.json()["events"]) == 1
    assert "abuse_confidence" not in r.json()
    assert len(fake_abuseipdb) == 20


def test_cached_history_enrichment_is_free(fake_abuseipdb):
    alice = session_client("alice", "analyst")
    for _ in range(21):
        _get(alice, f"/api/ip/{TARGET}/history")
    ip_router._abuse_cache[TARGET] = {"abuse_confidence": 90}
    assert _get(alice, f"/api/ip/{TARGET}/history").json()["abuse_confidence"] == 90


def test_history_without_a_key_counts_nothing(fake_abuseipdb, monkeypatch):
    monkeypatch.setattr(ip_router, "ABUSEIPDB_API_KEY", "")
    alice = session_client("alice", "analyst")
    for _ in range(25):
        _get(alice, f"/api/ip/{TARGET}/history")
    monkeypatch.setattr(ip_router, "ABUSEIPDB_API_KEY", "test-key")
    assert _get(alice, f"/api/ip/{TARGET}/history").json()["abuse_confidence"] == 90


# ── keys and memory ───────────────────────────────────────────

def test_user_ip_key_is_a_fixed_length_digest_without_the_address():
    a = user_ip_key("alice", SimpleNamespace(scope={"type": "http"}, headers=_Headers("198.51.100.40")))
    b = user_ip_key("alice", SimpleNamespace(scope={"type": "http"}, headers=_Headers("198.51.100.41")))
    c = user_ip_key("bob", SimpleNamespace(scope={"type": "http"}, headers=_Headers("198.51.100.40")))
    long_name = user_ip_key("a" * 50, SimpleNamespace(scope={"type": "http"}, headers=_Headers("198.51.100.40")))
    assert len({a, b, c, long_name}) == 4
    assert all(len(k) == 64 and "198.51" not in k for k in (a, b, c, long_name))


def test_expired_keys_are_removed_from_memory():
    """Old counters do not pile up: the storage drops a key once its window
    has passed (on its next sweep, which any new hit schedules)."""
    limit = KeyedLimit("test-expiry", "1/second")
    limit.hit("old")
    storage = KeyedLimit._storage.storage
    assert any("/test-expiry/old/" in k for k in storage)
    time.sleep(1.1)
    limit.hit("new")
    deadline = time.time() + 2
    while any("/test-expiry/old/" in k for k in storage) and time.time() < deadline:
        time.sleep(0.02)
    assert not any("/test-expiry/old/" in k for k in storage)
