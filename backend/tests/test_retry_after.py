"""Every rate-limit 429 carries Retry-After: the per-IP limits (slowapi) and
the per-key limits (KeyedLimit). The response bodies stay as they were."""
from __future__ import annotations

import time

from fastapi.testclient import TestClient

import main
import rate_limit
from rate_limit import KeyedLimit


def _login(client, username, password, xff):
    return client.post("/auth/login", json={"username": username, "password": password},
                       headers={"X-Forwarded-For": xff})


def _retry_after(response) -> int:
    value = response.headers.get("Retry-After")
    assert value is not None, "429 without Retry-After"
    assert value.isdigit(), value
    return int(value)


# ── per-IP limits (slowapi) ───────────────────────────────────

def test_per_ip_429_has_retry_after_within_the_window_and_the_same_body():
    client = TestClient(main.app)
    for _ in range(5):
        assert _login(client, "mallory", "guess", "198.51.100.10").status_code == 401
    r = _login(client, "mallory", "guess", "198.51.100.10")
    assert r.status_code == 429
    assert r.json() == {"error": "Rate limit exceeded: 5 per 1 minute"}
    assert 1 <= _retry_after(r) <= 60


def test_successful_responses_get_no_rate_limit_headers():
    r = _login(TestClient(main.app), "mallory", "guess", "198.51.100.11")
    assert r.status_code == 401
    assert "Retry-After" not in r.headers
    assert not any(h.lower().startswith("x-ratelimit") for h in r.headers)


# ── per-key limits (KeyedLimit) ───────────────────────────────

def test_keyed_retry_after_is_one_when_nothing_is_exceeded():
    limit = KeyedLimit("test-retry-free", "2/minute")
    assert limit.retry_after("k") == 1
    limit.hit("k")
    assert limit.retry_after("k") == 1


def test_keyed_retry_after_covers_the_minute_window():
    limit = KeyedLimit("test-retry-minute", "2/minute;100/hour")
    limit.hit("k")
    limit.hit("k")
    assert limit.exceeded("k")
    assert 1 <= limit.retry_after("k") <= 60


def test_keyed_retry_after_takes_the_longest_exceeded_window():
    limit = KeyedLimit("test-retry-hour", "50/minute;3/hour")
    for _ in range(3):
        limit.hit("k")
    assert limit.exceeded("k")
    assert 60 < limit.retry_after("k") <= 3600


def test_seconds_until_rounds_up_and_is_never_below_one():
    now = time.time()
    assert rate_limit.seconds_until(now - 10) == 1
    assert rate_limit.seconds_until(now + 30.2) in (31, 30)  # 30 only if the clock moved


def test_account_lockout_429_has_retry_after():
    client = TestClient(main.app)
    for i in range(10):
        assert _login(client, "alice", f"guess-{i}", f"192.0.2.{i}").status_code == 401
    r = _login(client, "alice", "guess-x", "192.0.2.100")
    assert r.status_code == 429
    assert r.json() == {"detail": "Too many login attempts, try again later"}
    assert 1 <= _retry_after(r) <= 60
