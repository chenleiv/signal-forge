import pytest
from unittest.mock import AsyncMock, patch, MagicMock


@pytest.mark.asyncio
async def test_refresh_uses_api_when_key_set(monkeypatch):
    import main as m

    monkeypatch.setattr(m, "ABUSEIPDB_API_KEY", "test-key")
    monkeypatch.setattr(m, "THREAT_IPS", ["0.0.0.0"])

    mock_response = MagicMock()
    mock_response.json.return_value = {
        "data": [
            {"ipAddress": "1.1.1.1", "abuseConfidenceScore": 95},
            {"ipAddress": "2.2.2.2", "abuseConfidenceScore": 92},
        ]
    }
    mock_client = AsyncMock()
    mock_client.get.return_value = mock_response

    with patch("httpx.AsyncClient") as mock_cls:
        mock_cls.return_value.__aenter__.return_value = mock_client
        await m._refresh_threat_ips()

    assert "1.1.1.1" in m.THREAT_IPS
    assert "2.2.2.2" in m.THREAT_IPS
    assert "0.0.0.0" not in m.THREAT_IPS


@pytest.mark.asyncio
async def test_refresh_keeps_fallback_when_no_key(monkeypatch):
    import main as m

    original = list(m._FALLBACK_THREAT_IPS)
    monkeypatch.setattr(m, "ABUSEIPDB_API_KEY", "")
    monkeypatch.setattr(m, "THREAT_IPS", ["9.9.9.9"])

    await m._refresh_threat_ips()

    assert m.THREAT_IPS == original


@pytest.mark.asyncio
async def test_refresh_keeps_fallback_on_error(monkeypatch):
    import main as m

    original = list(m._FALLBACK_THREAT_IPS)
    monkeypatch.setattr(m, "ABUSEIPDB_API_KEY", "test-key")

    with patch("httpx.AsyncClient") as mock_cls:
        mock_cls.return_value.__aenter__.return_value.get.side_effect = Exception("network error")
        await m._refresh_threat_ips()

    assert m.THREAT_IPS == original
