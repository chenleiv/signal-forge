"""The AI summary client fails fast: a 10 s timeout and no retries."""
from __future__ import annotations

from types import SimpleNamespace

import groq
import pytest

from routers import ip as ip_router
from tests.conftest import session_client

IP = "8.8.4.4"


class FakeGroq:
    calls: list[dict] = []
    fail = False

    def __init__(self, **kwargs):
        FakeGroq.calls.append(kwargs)
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._create))

    async def _create(self, **_):
        if FakeGroq.fail:
            raise TimeoutError("slow upstream")
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content="A summary."))])


@pytest.fixture
def fake_groq(monkeypatch):
    FakeGroq.calls = []
    FakeGroq.fail = False
    monkeypatch.setattr(groq, "AsyncGroq", FakeGroq)
    monkeypatch.setattr(ip_router, "GROQ_API_KEY", "test-key")
    monkeypatch.setattr(ip_router, "_ai_summary_cache", {})
    return FakeGroq


def test_client_has_a_short_timeout_and_no_retries(fake_groq):
    r = session_client("alice", "analyst").get(f"/api/ip/{IP}/ai-summary")
    assert r.status_code == 200 and r.json() == {"summary": "A summary."}
    assert fake_groq.calls == [{"api_key": "test-key", "timeout": 10.0, "max_retries": 0}]


def test_a_timeout_returns_no_summary_and_is_not_cached(fake_groq):
    fake_groq.fail = True
    client = session_client("alice", "analyst")
    assert client.get(f"/api/ip/{IP}/ai-summary").json() == {"summary": None}
    fake_groq.fail = False
    assert client.get(f"/api/ip/{IP}/ai-summary").json() == {"summary": "A summary."}
