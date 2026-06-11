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
    with patch("custom_components.electrolux_ac.hub.asyncio.ensure_future", side_effect=lambda c: c.close()):
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


@pytest.mark.asyncio
async def test_wait_for_state_returns_when_states_and_capabilities_ready():
    appliance = make_appliance()
    appliance._callbacks = set()
    appliance._states = {"applianceState": "running"}
    appliance.capabilities = {"targetTemperatureC": {"min": 16, "max": 32}}
    with patch("custom_components.electrolux_ac.hub.asyncio.sleep", new_callable=AsyncMock):
        await appliance.wait_for_state()


@pytest.mark.asyncio
async def test_wait_for_state_raises_if_capabilities_never_set():
    from custom_components.electrolux_ac.hub import ApplianceStateNotReady
    appliance = make_appliance()
    appliance._callbacks = set()
    appliance._states = {"applianceState": "running"}
    appliance.capabilities = {}
    with patch("custom_components.electrolux_ac.hub.asyncio.sleep", new_callable=AsyncMock):
        with pytest.raises(ApplianceStateNotReady):
            await appliance.wait_for_state()


@pytest.mark.asyncio
async def test_wait_for_state_raises_if_states_never_set():
    from custom_components.electrolux_ac.hub import ApplianceStateNotReady
    appliance = make_appliance()
    appliance._callbacks = set()
    appliance._states = {}
    appliance.capabilities = {"targetTemperatureC": {"min": 16, "max": 32}}
    with patch("custom_components.electrolux_ac.hub.asyncio.sleep", new_callable=AsyncMock):
        with pytest.raises(ApplianceStateNotReady):
            await appliance.wait_for_state()


def test_state_update_logs_warning_for_non_empty_alerts(caplog):
    appliance = make_appliance()
    appliance._callbacks = set()
    import logging
    with caplog.at_level(logging.WARNING, logger="custom_components.electrolux_ac.hub"):
        appliance.state_update_callback({
            "test_id": {"alerts": ["DRAIN_PAN_FULL"], "applianceState": "running"}
        })
    assert any("DRAIN_PAN_FULL" in r.message for r in caplog.records)


def test_state_update_no_warning_when_alerts_empty(caplog):
    appliance = make_appliance()
    appliance._callbacks = set()
    import logging
    with caplog.at_level(logging.WARNING, logger="custom_components.electrolux_ac.hub"):
        appliance.state_update_callback({
            "test_id": {"alerts": [], "applianceState": "running"}
        })
    assert not any("alert" in r.message.lower() for r in caplog.records)


@pytest.mark.asyncio
async def test_discover_appliances_handles_missing_appliance_data():
    hub = make_hub()
    hub.online = True
    hub._client = AsyncMock()
    hub._client.get_appliances_list.return_value = [
        {"applianceId": "id1"}  # missing applianceData key
    ]
    # Patch ensure_future to prevent background tasks from running
    with patch("custom_components.electrolux_ac.hub.asyncio.ensure_future", side_effect=lambda c: c.close()):
        await hub.discover_appliances()
    assert len(hub.appliances) == 1
    assert hub.appliances[0].name is None


@pytest.mark.asyncio
async def test_update_appliance_info_handles_empty_info():
    appliance = make_appliance()
    appliance._callbacks = set()
    appliance.hub._client.get_appliances_info = AsyncMock(return_value=[])
    appliance.hub._client.get_appliance_capabilities = AsyncMock(return_value={})
    # Should not raise; appliance_info stays None
    await appliance.update_appliance_info()
    assert appliance.appliance_info is None


@pytest.mark.asyncio
async def test_execute_command_propagates_api_exception():
    appliance = make_appliance()
    appliance._callbacks = set()
    appliance.hub._client.execute_appliance_command = AsyncMock(side_effect=RuntimeError("API error"))
    with pytest.raises(RuntimeError, match="API error"):
        await appliance.execute_command("mode", "cool")
