"""Demo backfill: a fresh demo process records the last minutes of simulated
sample events at startup, so the stats charts are not empty. It must never
run on live or cached threat data, or outside demo mode, and must never raise
alerts."""
from collections import defaultdict, deque
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from tests.conftest import session_client

import main
import simulation as m
import store

# The bundled sample: spread over its IPs, the backfill stays far below the
# per-IP store cap (200), so no backfilled event is evicted.
SAMPLE = m._load_sample()


@pytest.fixture(autouse=True)
def _isolated_state(monkeypatch):
    """Fresh in-memory state, so the backfill cannot leak into other tests."""
    monkeypatch.setattr(store, "ip_store", defaultdict(lambda: deque(maxlen=200)))
    monkeypatch.setattr(store, "minute_buckets", deque(maxlen=15))
    monkeypatch.setattr(store, "alerts_store", deque(maxlen=100))
    monkeypatch.setattr(store, "_current_minute", "")
    monkeypatch.setattr(store, "_current_bucket_count", 0)
    monkeypatch.setattr(m, "THREAT_IPS", dict(SAMPLE))
    monkeypatch.setattr(m, "FEED_STATUS", {"state": "sample", "reason": "no_key"})


def _event_count() -> int:
    return sum(len(events) for events in store.ip_store.values())


def test_backfill_runs_in_demo_mode_on_sample_data():
    count = m.backfill_demo_events(True)
    assert count == m.MAX_BACKFILL_EVENTS
    assert _event_count() == count
    assert set(store.ip_store) <= set(SAMPLE)


def test_backfill_total_is_bounded():
    assert m.MAX_BACKFILL_EVENTS <= 1000
    m.backfill_demo_events(True)
    assert _event_count() <= m.MAX_BACKFILL_EVENTS
    # The backfill also stays inside the stores' own caps.
    assert len(store.minute_buckets) <= store.minute_buckets.maxlen
    assert all(len(events) <= events.maxlen for events in store.ip_store.values())


def test_backfill_timestamps_and_buckets_cover_the_past_window():
    before = datetime.now(timezone.utc).replace(second=0, microsecond=0)
    m.backfill_demo_events(True)
    stamps = [datetime.fromisoformat(e["timestamp"]) for es in store.ip_store.values() for e in es]
    assert min(stamps) >= before - timedelta(minutes=m.BACKFILL_MINUTES)
    # Past minutes only (one minute of slack if the clock ticks over mid-test).
    assert max(stamps) < before + timedelta(minutes=1)

    buckets = list(store.minute_buckets)
    assert len(buckets) == m.BACKFILL_MINUTES
    assert all(b["count"] == m.BACKFILL_PER_MINUTE for b in buckets)
    assert sum(b["count"] for b in buckets) == _event_count()
    assert store._current_minute == ""  # the live minute is left to the stream


@pytest.mark.parametrize("status", [
    {"state": "live", "reason": None},
    {"state": "cached", "reason": "quota"},
    {"state": "unavailable", "reason": "no_key"},
])
def test_backfill_never_runs_on_non_sample_feeds(monkeypatch, status):
    monkeypatch.setattr(m, "FEED_STATUS", status)
    assert m.backfill_demo_events(True) == 0
    assert _event_count() == 0
    assert not store.minute_buckets


def test_backfill_never_runs_outside_demo_mode():
    assert m.backfill_demo_events(False) == 0
    assert _event_count() == 0
    assert not store.minute_buckets


def test_backfill_evaluates_no_rules_and_creates_no_alerts(monkeypatch):
    def fail(_event):
        raise AssertionError("the backfill must not evaluate alert rules")
    monkeypatch.setattr(store, "_evaluate_rules", fail)
    m.backfill_demo_events(True)
    assert _event_count() > 0
    assert len(store.alerts_store) == 0


# ── Startup ───────────────────────────────────────────────────

async def _sample_refresh(**_) -> None:
    m.THREAT_IPS = dict(SAMPLE)
    m.FEED_STATUS.update(state="sample", reason="no_key")


def test_demo_startup_fills_stats_without_alerts(monkeypatch):
    monkeypatch.setattr(main, "DEMO_MODE", True)
    monkeypatch.setattr(main, "refresh_threat_ips", _sample_refresh)

    with TestClient(main.app):
        assert len(store.alerts_store) == 0
        stats = session_client("alice", "analyst").get("/api/stats").json()

    assert sum(stats["severity_counts"].values()) == m.MAX_BACKFILL_EVENTS
    assert sum(stats["attack_types"].values()) == m.MAX_BACKFILL_EVENTS
    assert len(stats["events_per_min"]) == m.BACKFILL_MINUTES
    assert {row["ip"] for row in stats["top_ips"]} <= set(SAMPLE)


def test_non_demo_startup_backfills_nothing(monkeypatch):
    monkeypatch.setattr(main, "DEMO_MODE", False)
    monkeypatch.setattr(main, "refresh_threat_ips", _sample_refresh)

    with TestClient(main.app):
        stats = session_client("alice", "analyst").get("/api/stats").json()

    assert sum(stats["severity_counts"].values()) == 0
    assert stats["events_per_min"] == []
