import pytest
from unittest.mock import AsyncMock, patch, MagicMock


@pytest.mark.asyncio
async def test_fetch_otx_returns_data(monkeypatch):
    import main as m
    monkeypatch.setattr(m, "OTX_API_KEY", "test-key")

    mock_response = MagicMock()
    mock_response.json.return_value = {
        "pulse_info": {
            "count": 3,
            "pulses": [
                {"name": "APT28 C2", "tags": ["apt", "c2"], "author": {"username": "researcher1"}, "created": "2024-01-01T00:00:00"},
                {"name": "Cobalt Strike", "tags": ["cobalt"], "author": {"username": "researcher2"}, "created": "2024-01-02T00:00:00"},
            ]
        },
        "reputation": 2,
        "malware_families": [{"display_name": "CobaltStrike"}, {"id": "emotet"}],
    }
    mock_response.raise_for_status = MagicMock()

    mock_client = AsyncMock()
    mock_client.get.return_value = mock_response

    result = await m._fetch_otx(mock_client, "1.2.3.4")

    assert result is not None
    assert result["pulse_count"] == 3
    assert result["reputation"] == 2
    assert len(result["pulses"]) == 2
    assert result["pulses"][0]["name"] == "APT28 C2"
    assert result["pulses"][0]["tags"] == ["apt", "c2"]
    assert "CobaltStrike" in result["malware_families"]


@pytest.mark.asyncio
async def test_fetch_otx_returns_none_on_error(monkeypatch):
    import main as m
    monkeypatch.setattr(m, "OTX_API_KEY", "test-key")

    mock_client = AsyncMock()
    mock_client.get.side_effect = Exception("network error")

    result = await m._fetch_otx(mock_client, "1.2.3.4")
    assert result is None


@pytest.mark.asyncio
async def test_fetch_otx_returns_empty_when_no_key(monkeypatch):
    import main as m
    monkeypatch.setattr(m, "OTX_API_KEY", "")

    mock_client = AsyncMock()
    result = await m._fetch_otx(mock_client, "1.2.3.4")

    assert result == {"pulse_count": 0, "reputation": 0, "pulses": [], "malware_families": []}
    mock_client.get.assert_not_called()
