"""Threat feed status: an exhausted AbuseIPDB quota must be explained, not
look like a broken dashboard. Also the enrichment caches around it."""
from __future__ import annotations

import json
import time
from unittest.mock import AsyncMock, patch

import httpx
import pytest
from fastapi.testclient import TestClient

import main
import simulation as m
import store
from routers import ip as ip_router
from tests.conftest import session_client


def _response(status: int, body: dict | None = None) -> httpx.Response:
    return httpx.Response(status, json=body or {}, request=httpx.Request("GET", "https://api.test"))


async def _refresh_with(response: httpx.Response, *, cache: dict, allow_sample: bool) -> None:
    client = AsyncMock()
    client.get.return_value = response
    with patch("simulation.httpx.AsyncClient") as cls, \
         patch("simulation._cache_is_fresh", return_value=False), \
         patch("simulation._load_cache", return_value=cache), \
         patch("simulation._save_cache"):
        cls.return_value.__aenter__.return_value = client
        await m.refresh_threat_ips(allow_sample=allow_sample)


@pytest.fixture(autouse=True)
def _feed(monkeypatch):
    monkeypatch.setattr(m, "ABUSEIPDB_API_KEY", "test-key")
    monkeypatch.setattr(m, "THREAT_IPS", {})
    monkeypatch.setattr(m, "FEED_STATUS", {"state": "unavailable", "reason": None})
    monkeypatch.setattr(m, "_quota_resets_in", None)


# ── Feed state ────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_quota_exhausted_in_demo_streams_the_sample():
    await _refresh_with(_response(429), cache={}, allow_sample=True)
    assert m.FEED_STATUS == {"state": "sample", "reason": "quota"}
    assert m.THREAT_IPS == m._load_sample() and m.THREAT_IPS


@pytest.mark.asyncio
async def test_quota_exhausted_outside_demo_never_streams_the_sample():
    """A real SOC must not raise alerts on made-up data."""
    await _refresh_with(_response(429), cache={}, allow_sample=False)
    assert m.FEED_STATUS == {"state": "unavailable", "reason": "quota"}
    assert m.THREAT_IPS == {}


@pytest.mark.asyncio
async def test_an_older_cache_wins_over_the_sample():
    await _refresh_with(_response(429), cache={"8.8.8.8": 90}, allow_sample=True)
    assert m.FEED_STATUS == {"state": "cached", "reason": "quota"}
    assert m.THREAT_IPS == {"8.8.8.8": 90}


@pytest.mark.asyncio
async def test_other_http_errors_are_not_reported_as_quota():
    await _refresh_with(_response(500), cache={}, allow_sample=True)
    assert m.FEED_STATUS == {"state": "sample", "reason": "error"}


@pytest.mark.asyncio
async def test_fresh_data_is_live():
    body = {"data": [{"ipAddress": "8.8.8.8", "abuseConfidenceScore": 97}]}
    await _refresh_with(_response(200, body), cache={}, allow_sample=True)
    assert m.FEED_STATUS == {"state": "live", "reason": None}
    assert m.THREAT_IPS == {"8.8.8.8": 97}


@pytest.mark.asyncio
async def test_no_api_key_in_demo_streams_the_sample(monkeypatch):
    monkeypatch.setattr(m, "ABUSEIPDB_API_KEY", "")
    with patch("simulation._load_cache", return_value={}):
        await m.refresh_threat_ips(allow_sample=True)
    assert m.FEED_STATUS == {"state": "sample", "reason": "no_key"}


@pytest.mark.parametrize("status, wait", [
    ({"state": "live", "reason": None}, m.REFRESH_SECONDS),
    ({"state": "cached", "reason": "no_key"}, m.REFRESH_SECONDS),   # retrying cannot help
    ({"state": "sample", "reason": "quota"}, m.RETRY_SECONDS),
    ({"state": "cached", "reason": "error"}, m.RETRY_SECONDS),
])
def test_a_feed_that_is_not_live_is_retried_hourly(monkeypatch, status, wait):
    monkeypatch.setattr(m, "FEED_STATUS", status)
    assert m.next_refresh_in() == wait


def test_sample_ips_are_public_addresses():
    """Private or reserved IPs are rejected by every IP action (block, case from IP)."""
    sample = json.loads(m._SAMPLE_FILE.read_text())["ips"]
    assert sample
    for ip, score in sample.items():
        assert store.validate_ip(ip) == ip
        assert 0 <= score <= 100


# ── API ───────────────────────────────────────────────────────

def test_feed_status_requires_a_session():
    assert TestClient(main.app).get("/api/threat-feed").status_code == 401


def test_feed_status_is_served(monkeypatch):
    monkeypatch.setattr(m, "FEED_STATUS", {"state": "sample", "reason": "quota"})
    r = session_client("alice", "analyst").get("/api/threat-feed")
    assert r.status_code == 200
    assert r.json() == {"state": "sample", "reason": "quota"}


# ── Regression: startup read a stale copy of THREAT_IPS ───────

def test_ipinfo_prefetch_sees_the_refreshed_ip_list(monkeypatch):
    async def fake_refresh(**_) -> None:
        m.THREAT_IPS = {"8.8.8.8": 90}

    async def fake_ipinfo(client, ip):
        return {"lat": 1.5, "lng": 2.5}

    monkeypatch.setattr(main, "refresh_threat_ips", fake_refresh)
    monkeypatch.setattr(main, "fetch_ipinfo", fake_ipinfo)
    monkeypatch.setattr(main, "IPINFO_TOKEN", "test-token")
    store._ip_coords.pop("8.8.8.8", None)
    with TestClient(main.app):
        deadline = time.monotonic() + 2
        while "8.8.8.8" not in store._ip_coords and time.monotonic() < deadline:
            time.sleep(0.01)
    assert store._ip_coords.pop("8.8.8.8") == (1.5, 2.5)


# ── Enrichment caches ─────────────────────────────────────────

@pytest.mark.asyncio
async def test_a_failed_abuseipdb_lookup_is_not_cached(monkeypatch):
    monkeypatch.setattr(ip_router, "ABUSEIPDB_API_KEY", "test-key")
    monkeypatch.setattr(ip_router, "_abuse_cache", {})
    client = AsyncMock()
    client.get.return_value = _response(429, {"errors": [{"detail": "quota"}]})
    with patch("routers.ip.httpx.AsyncClient") as cls:
        cls.return_value.__aenter__.return_value = client
        assert await ip_router.enrich_ip("8.8.8.8") is None
    assert ip_router._abuse_cache == {}   # the next lookup tries again


@pytest.mark.asyncio
async def test_an_ipinfo_error_body_is_not_geolocation():
    client = AsyncMock()
    client.get.return_value = _response(429, {"error": {"title": "Rate limit"}})
    assert await m.fetch_ipinfo(client, "8.8.8.8") is None


def test_geo_fallback_is_not_cached_when_ipinfo_may_recover(monkeypatch):
    async def failing(client, ip):
        return None
    monkeypatch.setattr(ip_router, "IPINFO_TOKEN", "test-token")
    monkeypatch.setattr(ip_router, "fetch_ipinfo", failing)
    monkeypatch.setattr(ip_router, "_geo_cache", {})
    r = session_client("alice", "analyst").get("/api/ip/8.8.4.4/geo")
    assert r.status_code == 200
    assert ip_router._geo_cache == {}


def test_lookup_caches_are_bounded(monkeypatch):
    monkeypatch.setattr(ip_router, "MAX_CACHED_IPS", 3)
    cache: dict = {}
    for i in range(5):
        ip_router._cache_put(cache, f"8.8.8.{i}", i)
    assert list(cache) == ["8.8.8.2", "8.8.8.3", "8.8.8.4"]   # oldest evicted


# ── Retry at the quota reset ──────────────────────────────────

def _quota_response(retry_after: str | None) -> httpx.Response:
    headers = {"Retry-After": retry_after} if retry_after is not None else {}
    return httpx.Response(429, headers=headers, request=httpx.Request("GET", "https://api.test"))


@pytest.mark.asyncio
@pytest.mark.parametrize("header, wait", [
    ("7200", 7200),                         # retry exactly at the reset
    ("0", m.MIN_RETRY_SECONDS),             # never hammer the API
    ("999999999", m.REFRESH_SECONDS),       # never freeze the feed
    (None, m.RETRY_SECONDS),                # no header: hourly
    ("soon", m.RETRY_SECONDS),              # unreadable: hourly
    ("", m.RETRY_SECONDS),
])
async def test_a_429_retries_when_the_quota_resets(header, wait):
    await _refresh_with(_quota_response(header), cache={}, allow_sample=True)
    assert m.next_refresh_in() == wait


@pytest.mark.asyncio
async def test_retry_after_as_an_http_date():
    from email.utils import format_datetime
    from datetime import datetime, timedelta, timezone
    reset = format_datetime(datetime.now(timezone.utc) + timedelta(hours=3), usegmt=True)
    await _refresh_with(_quota_response(reset), cache={}, allow_sample=True)
    assert abs(m.next_refresh_in() - 3 * 3600) <= 5


@pytest.mark.asyncio
async def test_retry_after_on_other_errors_is_ignored():
    response = httpx.Response(503, headers={"Retry-After": "7200"}, request=httpx.Request("GET", "https://api.test"))
    await _refresh_with(response, cache={}, allow_sample=True)
    assert m.next_refresh_in() == m.RETRY_SECONDS


@pytest.mark.asyncio
async def test_a_successful_fetch_forgets_the_old_reset_time():
    await _refresh_with(_quota_response("7200"), cache={}, allow_sample=True)
    body = {"data": [{"ipAddress": "8.8.8.8", "abuseConfidenceScore": 97}]}
    await _refresh_with(_response(200, body), cache={}, allow_sample=True)
    assert m.next_refresh_in() == m.REFRESH_SECONDS
    assert m._quota_resets_in is None
