from unittest.mock import MagicMock, patch, AsyncMock
import pytest
from custom_components.electrolux_ac.hub import Hub


def make_hub(hass=None, country_code="fi"):
    hass = hass or MagicMock()
    return Hub(hass, "test@example.com", "secret", country_code)


@pytest.mark.asyncio
async def test_hub_passes_country_code_to_api():
    hub = make_hub(country_code="de")
    with patch("custom_components.electrolux_ac.hub.OneAppApi") as mock_api_cls:
        mock_api_cls.return_value = MagicMock()
        await hub.connect()
    args, _ = mock_api_cls.call_args
    assert args[2] == "de"


@pytest.mark.asyncio
async def test_hub_defaults_country_code_fi():
    hub = Hub(MagicMock(), "test@example.com", "secret", "fi")
    with patch("custom_components.electrolux_ac.hub.OneAppApi") as mock_api_cls:
        mock_api_cls.return_value = MagicMock()
        await hub.connect()
    args, _ = mock_api_cls.call_args
    assert args[2] == "fi"
