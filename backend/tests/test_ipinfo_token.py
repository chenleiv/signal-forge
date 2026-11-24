"""The ipinfo token is sent in the Authorization header, never in the URL,
and a failed lookup is logged without the token or any response text."""
from __future__ import annotations
import logging

import httpx
import pytest

import simulation

TOKEN = "ipinfo-test-token-5f3a9c"
GEO = {"ip": "8.8.8.8", "city": "Mountain View", "country": "US", "loc": "37.4,-122.1",
       "org": "AS15169 Google LLC", "timezone": "America/Los_Angeles"}


@pytest.fixture(autouse=True)
def _token(monkeypatch):
    monkeypatch.setattr(simulation, "IPINFO_TOKEN", TOKEN)


def _client(handler) -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


@pytest.mark.asyncio
async def test_the_token_is_a_header_not_a_query_parameter():
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, json=GEO)

    async with _client(handler) as client:
        data = await simulation.fetch_ipinfo(client, "8.8.8.8")

    assert data is not None and data["city"] == "Mountain View" and data["lat"] == 37.4
    (request,) = seen
    assert str(request.url) == "https://ipinfo.io/8.8.8.8/json"
    assert request.url.query == b""
    assert TOKEN not in str(request.url)
    assert request.headers["authorization"] == f"Bearer {TOKEN}"


@pytest.mark.asyncio
@pytest.mark.parametrize("status", [401, 403, 429, 500])
async def test_an_error_status_is_logged_without_the_token(caplog, status):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(status, json={"error": {"title": f"bad token {TOKEN}"}})

    with caplog.at_level(logging.WARNING, logger="uvicorn.error"):
        async with _client(handler) as client:
            assert await simulation.fetch_ipinfo(client, "8.8.8.8") is None

    lines = [r.getMessage() for r in caplog.records if r.name == "uvicorn.error"]
    assert lines == [f"ipinfo lookup failed for 8.8.8.8: HTTPStatusError status={status}"]
    assert TOKEN not in caplog.text
    assert "ipinfo.io" not in caplog.text


@pytest.mark.asyncio
async def test_a_network_error_is_logged_without_the_token(caplog):
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError(f"failed for {request.url} {request.headers['authorization']}")

    with caplog.at_level(logging.WARNING, logger="uvicorn.error"):
        async with _client(handler) as client:
            assert await simulation.fetch_ipinfo(client, "8.8.8.8") is None

    lines = [r.getMessage() for r in caplog.records if r.name == "uvicorn.error"]
    assert lines == ["ipinfo lookup failed for 8.8.8.8: ConnectError status=None"]
    assert TOKEN not in caplog.text
