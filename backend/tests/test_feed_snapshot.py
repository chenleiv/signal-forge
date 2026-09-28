"""The AbuseIPDB list is stored in the database, so a restart (Render wipes
the disk) does not spend the small daily blacklist quota."""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, patch

import httpx
import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

import simulation as m
import store
from database import Base
from models import ThreatFeedSnapshot

STORED = {"8.8.8.8": 90, "1.1.1.1": 70}


@pytest_asyncio.fixture
async def factory(tmp_path):
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'feed.db'}")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    await engine.dispose()


@pytest.fixture(autouse=True)
def _feed(monkeypatch, tmp_path):
    monkeypatch.setattr(m, "ABUSEIPDB_API_KEY", "test-key")
    monkeypatch.setattr(m, "THREAT_IPS", {})
    monkeypatch.setattr(m, "FEED_STATUS", {"state": "unavailable", "reason": None})
    monkeypatch.setattr(m, "_CACHE_FILE", tmp_path / "cache.json")   # no file cache: a fresh Render disk


async def _store(factory, ips: object, age: timedelta = timedelta(0)) -> None:
    async with factory() as session:
        session.add(ThreatFeedSnapshot(id=1, ips=json.dumps(ips), saved_at=datetime.now(timezone.utc) - age))
        await session.commit()


async def _stored(factory) -> dict:
    async with factory() as session:
        return json.loads((await session.execute(select(ThreatFeedSnapshot))).scalar_one().ips)


def _api(response: httpx.Response | Exception):
    client = AsyncMock()
    if isinstance(response, Exception):
        client.get.side_effect = response
    else:
        client.get.return_value = response
    return client


def _response(status: int, body: dict | None = None) -> httpx.Response:
    return httpx.Response(status, json=body or {}, request=httpx.Request("GET", "https://api.test"))


async def _refresh(factory, client, *, allow_sample: bool = True) -> None:
    with patch("simulation.httpx.AsyncClient") as cls:
        cls.return_value.__aenter__.return_value = client
        await m.refresh_threat_ips(allow_sample=allow_sample, session_factory=factory)


@pytest.mark.asyncio
async def test_a_restart_with_a_fresh_snapshot_spends_no_quota(factory):
    await _store(factory, STORED, age=timedelta(hours=3))
    client = _api(_response(200))
    await _refresh(factory, client)
    client.get.assert_not_called()
    assert m.THREAT_IPS == STORED
    assert m.FEED_STATUS == {"state": "live", "reason": None}


@pytest.mark.asyncio
async def test_a_day_old_snapshot_is_refreshed_and_the_new_list_stored(factory):
    await _store(factory, STORED, age=timedelta(hours=25))
    client = _api(_response(200, {"data": [{"ipAddress": "9.9.9.9", "abuseConfidenceScore": 88}]}))
    await _refresh(factory, client)
    client.get.assert_called_once()
    assert m.THREAT_IPS == {"9.9.9.9": 88}
    assert await _stored(factory) == {"9.9.9.9": 88}


@pytest.mark.asyncio
async def test_the_first_successful_fetch_is_stored(factory):
    client = _api(_response(200, {"data": [{"ipAddress": "9.9.9.9", "abuseConfidenceScore": 88}]}))
    await _refresh(factory, client)
    assert await _stored(factory) == {"9.9.9.9": 88}


@pytest.mark.asyncio
async def test_quota_exhausted_streams_the_old_snapshot_not_the_sample(factory):
    await _store(factory, STORED, age=timedelta(days=5))
    await _refresh(factory, _api(_response(429)))
    assert m.THREAT_IPS == STORED
    assert m.FEED_STATUS == {"state": "cached", "reason": "quota"}


@pytest.mark.asyncio
async def test_no_api_key_still_streams_the_snapshot(factory, monkeypatch):
    monkeypatch.setattr(m, "ABUSEIPDB_API_KEY", "")
    await _store(factory, STORED, age=timedelta(days=5))
    await _refresh(factory, _api(_response(200)))
    assert m.FEED_STATUS == {"state": "cached", "reason": "no_key"}


@pytest.mark.asyncio
async def test_a_tampered_snapshot_streams_only_valid_public_ips(factory):
    await _store(factory, {
        "8.8.8.8": 90,           # kept
        "10.0.0.1": 90,          # private
        "127.0.0.1": 90,         # loopback
        "not-an-ip": 90,
        "1.1.1.1": 500,          # score out of range
        "9.9.9.9": "90",         # not an int
        "8.8.4.4": True,         # bool is not a score
    }, age=timedelta(hours=1))
    await _refresh(factory, _api(_response(200)))
    assert m.THREAT_IPS == {"8.8.8.8": 90}


@pytest.mark.asyncio
@pytest.mark.parametrize("junk", [[], "x", {"10.0.0.1": 90}])
async def test_an_unusable_snapshot_is_ignored(factory, junk):
    await _store(factory, junk, age=timedelta(hours=1))
    await _refresh(factory, _api(_response(429)))
    assert m.FEED_STATUS == {"state": "sample", "reason": "quota"}


@pytest.mark.asyncio
async def test_the_snapshot_size_is_capped(factory, monkeypatch):
    monkeypatch.setattr(m, "MAX_FEED_IPS", 2)
    await _store(factory, {"8.8.8.8": 90, "1.1.1.1": 70, "9.9.9.9": 50}, age=timedelta(hours=1))
    await _refresh(factory, _api(_response(200)))
    assert len(m.THREAT_IPS) == 2


@pytest.mark.asyncio
async def test_api_entries_are_validated_too(factory):
    body = {"data": [
        {"ipAddress": "9.9.9.9", "abuseConfidenceScore": 88},
        {"ipAddress": "192.168.1.1", "abuseConfidenceScore": 99},
        {"ipAddress": "8.8.8.8", "abuseConfidenceScore": None},
        "garbage",
    ]}
    await _refresh(factory, _api(_response(200, body)))
    assert m.THREAT_IPS == {"9.9.9.9": 88}


@pytest.mark.asyncio
async def test_a_database_outage_does_not_stop_the_feed(monkeypatch):
    def broken():
        raise ConnectionError("database down")
    await _refresh(broken, _api(_response(200, {"data": [{"ipAddress": "9.9.9.9", "abuseConfidenceScore": 88}]})))
    assert m.THREAT_IPS == {"9.9.9.9": 88}
    assert m.FEED_STATUS == {"state": "live", "reason": None}


@pytest.mark.parametrize("ip", ["8.8.8.8", "2001:4860:4860::8888", "10.0.0.1", "127.0.0.1", "169.254.1.1",
                                "224.0.0.1", "240.0.0.1", "::1", "bad", ""])
def test_is_public_ip_agrees_with_route_validation(ip):
    try:
        store.validate_ip(ip)
        accepted = True
    except Exception:
        accepted = False
    assert store.is_public_ip(ip) is accepted
