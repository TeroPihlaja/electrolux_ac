from unittest.mock import MagicMock, patch, AsyncMock
import pytest
from custom_components.electrolux_ac.hub import Hub, Appliance


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


def make_appliance(connected=True):
    hub = MagicMock()
    hub._client = MagicMock()
    with patch("custom_components.electrolux_ac.hub.asyncio.ensure_future"):
        appliance = Appliance("test_id", "Test AC", hub)
    appliance._connected = connected
    return appliance


def test_appliance_online_false_when_not_connected():
    appliance = make_appliance(connected=False)
    assert appliance.online is False


def test_appliance_online_true_when_connected():
    appliance = make_appliance(connected=True)
    assert appliance.online is True


def test_state_update_sets_connected():
    appliance = make_appliance(connected=False)
    appliance._callbacks = set()
    appliance.state_update_callback({"test_id": {"applianceState": "running"}})
    assert appliance._connected is True


@pytest.mark.asyncio
async def test_refresh_connection_state_updates_connected():
    hub = make_hub()
    appliance = make_appliance(connected=True)
    hub.appliances = [appliance]
    hub._client = AsyncMock()
    hub._client.get_appliances_list.return_value = [
        {"applianceId": "test_id", "connectionState": "Disconnected",
         "applianceData": {"applianceName": "Test AC"}}
    ]
    await hub.refresh_connection_state()
    assert appliance._connected is False


@pytest.mark.asyncio
async def test_refresh_connection_state_publishes_on_change():
    hub = make_hub()
    appliance = make_appliance(connected=True)
    callback = MagicMock()
    appliance.register_callback(callback)
    hub.appliances = [appliance]
    hub._client = AsyncMock()
    hub._client.get_appliances_list.return_value = [
        {"applianceId": "test_id", "connectionState": "Disconnected",
         "applianceData": {"applianceName": "Test AC"}}
    ]
    await hub.refresh_connection_state()
    callback.assert_called_once()
