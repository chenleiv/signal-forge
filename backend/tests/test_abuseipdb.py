import pytest
from unittest.mock import AsyncMock, patch, MagicMock
import simulation as m


@pytest.mark.asyncio
async def test_refresh_uses_api_when_key_set(monkeypatch):
    monkeypatch.setattr(m, "ABUSEIPDB_API_KEY", "test-key")
    monkeypatch.setattr(m, "THREAT_IPS", {})

    mock_response = MagicMock()
    mock_response.json.return_value = {
        "data": [
            {"ipAddress": "1.1.1.1", "abuseConfidenceScore": 95},
            {"ipAddress": "2.2.2.2", "abuseConfidenceScore": 92},
        ]
    }
    mock_response.raise_for_status = MagicMock()
    mock_client = AsyncMock()
    mock_client.get.return_value = mock_response

    with patch("simulation.httpx.AsyncClient") as mock_cls, \
         patch("simulation._save_cache"):
        mock_cls.return_value.__aenter__.return_value = mock_client
        await m.refresh_threat_ips()

    assert "1.1.1.1" in m.THREAT_IPS
    assert "2.2.2.2" in m.THREAT_IPS
    assert m.THREAT_IPS["1.1.1.1"] == 95


@pytest.mark.asyncio
async def test_refresh_keeps_fallback_when_no_key(monkeypatch):
    monkeypatch.setattr(m, "ABUSEIPDB_API_KEY", "")

    cached = {"10.0.0.1": 75, "10.0.0.2": 80}
    with patch("simulation._load_cache", return_value=cached):
        await m.refresh_threat_ips()

    assert m.THREAT_IPS == cached


@pytest.mark.asyncio
async def test_refresh_keeps_fallback_on_error(monkeypatch):
    monkeypatch.setattr(m, "ABUSEIPDB_API_KEY", "test-key")

    cached = {"10.0.0.1": 75}
    with patch("simulation.httpx.AsyncClient") as mock_cls, \
         patch("simulation._load_cache", return_value=cached):
        mock_cls.return_value.__aenter__.return_value.get.side_effect = Exception("network error")
        await m.refresh_threat_ips()

    assert m.THREAT_IPS == cached
