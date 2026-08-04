from unittest.mock import MagicMock, patch, AsyncMock
import pytest
from custom_components.electrolux_ac.hub import Hub, Appliance
from electrolux_group_developer_sdk.client.dto.appliance_state import ApplianceState


def make_entry(data=None):
    entry = MagicMock()
    entry.data = data or {
        "api_key": "test_api_key",
        "access_token": "test_access_token",
        "refresh_token": "test_refresh_token",
    }
    entry.entry_id = "test_entry_id"
    return entry


def make_hub(hass=None, entry=None):
    hass = hass or MagicMock()
    entry = entry or make_entry()
    return Hub(hass, entry)


@pytest.mark.asyncio
async def test_connect_builds_client_with_entry_credentials():
    entry = make_entry()
    hub = make_hub(entry=entry)
    with patch("custom_components.electrolux_ac.hub.TokenManager") as mock_tm_cls, \
         patch("custom_components.electrolux_ac.hub.ApplianceClient") as mock_client_cls:
        await hub.connect()
    _, kwargs = mock_tm_cls.call_args
    assert kwargs["access_token"] == "test_access_token"
    assert kwargs["refresh_token"] == "test_refresh_token"
    assert kwargs["api_key"] == "test_api_key"
    mock_client_cls.assert_called_once_with(token_manager=mock_tm_cls.return_value)
    assert hub.online is True


@pytest.mark.asyncio
async def test_connect_persists_rotated_tokens_via_on_token_update():
    entry = make_entry()
    hass = MagicMock()
    hub = make_hub(hass=hass, entry=entry)
    with patch("custom_components.electrolux_ac.hub.TokenManager") as mock_tm_cls, \
         patch("custom_components.electrolux_ac.hub.ApplianceClient"):
        await hub.connect()
    _, kwargs = mock_tm_cls.call_args
    on_token_update = kwargs["on_token_update"]
    on_token_update("new_access", "new_refresh", "test_api_key")
    hass.config_entries.async_update_entry.assert_called_once_with(
        entry,
        data={
            "api_key": "test_api_key",
            "access_token": "new_access",
            "refresh_token": "new_refresh",
        },
    )


def _make_appliance_data(appliance_id="test_id", name="Test AC", connection_state="connected"):
    from unittest.mock import MagicMock
    data = MagicMock()
    data.appliance.applianceId = appliance_id
    data.appliance.applianceName = name
    data.details.capabilities = {"targetTemperatureC": {"min": 16, "max": 32}}
    data.details.applianceInfo.model = "COMFORT600"
    data.details.applianceInfo.brand = "ELECTROLUX"
    data.details.applianceInfo.deviceType = "PORTABLE_AIR_CONDITIONER"
    data.state.properties = {"reported": {"mode": "COOL", "ambientTemperatureC": 22}}
    data.state.connectionState = connection_state
    return data


@pytest.mark.asyncio
async def test_discover_appliances_builds_appliance_from_sdk_data():
    hub = make_hub()
    hub.online = True
    hub._client = AsyncMock()
    hub._client.get_appliance_data.return_value = [_make_appliance_data()]
    with patch("custom_components.electrolux_ac.hub.asyncio.ensure_future", side_effect=lambda c: c.close()):
        await hub.discover_appliances()
    assert len(hub.appliances) == 1
    appliance = hub.appliances[0]
    assert appliance.appliance_id == "test_id"
    assert appliance.name == "Test AC"
    assert appliance.capabilities == {"targetTemperatureC": {"min": 16, "max": 32}}
    assert appliance._states == {"mode": "COOL", "ambientTemperatureC": 22}
    assert appliance._connected is True
    assert appliance.appliance_info == {
        "model": "COMFORT600", "brand": "ELECTROLUX", "deviceType": "PORTABLE_AIR_CONDITIONER",
    }


@pytest.mark.asyncio
async def test_discover_appliances_marks_disconnected_appliance():
    hub = make_hub()
    hub.online = True
    hub._client = AsyncMock()
    hub._client.get_appliance_data.return_value = [_make_appliance_data(connection_state="disconnected")]
    with patch("custom_components.electrolux_ac.hub.asyncio.ensure_future", side_effect=lambda c: c.close()):
        await hub.discover_appliances()
    assert hub.appliances[0]._connected is False


@pytest.mark.asyncio
async def test_discover_appliances_handles_missing_details_and_state():
    from unittest.mock import MagicMock
    hub = make_hub()
    hub.online = True
    hub._client = AsyncMock()
    data = MagicMock()
    data.appliance.applianceId = "id1"
    data.appliance.applianceName = "Test AC"
    data.details = None
    data.state = None
    hub._client.get_appliance_data.return_value = [data]
    with patch("custom_components.electrolux_ac.hub.asyncio.ensure_future", side_effect=lambda c: c.close()):
        await hub.discover_appliances()
    appliance = hub.appliances[0]
    assert appliance.capabilities == {}
    assert appliance._states == {}
    assert appliance._connected is False
    assert appliance.appliance_info is None


def make_appliance(connected=True):
    hub = MagicMock()
    hub._client = MagicMock()
    appliance = Appliance("test_id", "Test AC", hub)
    appliance._sdk_state = ApplianceState(
        applianceId="test_id",
        connectionState="connected" if connected else "disconnected",
        status="enabled",
        properties={"reported": {"mode": "COOL"}},
    )
    appliance._states = appliance._sdk_state.properties["reported"]
    appliance._connected = connected
    return appliance


def test_appliance_online_false_when_not_connected():
    appliance = make_appliance(connected=False)
    assert appliance.online is False


def test_appliance_online_true_when_connected():
    appliance = make_appliance(connected=True)
    assert appliance.online is True


def test_state_update_callback_applies_property_event():
    appliance = make_appliance(connected=True)
    appliance._callbacks = set()
    appliance.state_update_callback({"property": "mode", "value": "DRY"})
    assert appliance._states["mode"] == "DRY"


def test_state_update_callback_updates_connection_state():
    appliance = make_appliance(connected=True)
    appliance._callbacks = set()
    appliance.state_update_callback({"property": "connectionState", "value": "disconnected"})
    assert appliance._connected is False


def test_state_update_callback_publishes_to_registered_callbacks():
    appliance = make_appliance(connected=True)
    appliance._callbacks = set()
    callback = MagicMock()
    appliance.register_callback(callback)
    appliance.state_update_callback({"property": "mode", "value": "DRY"})
    callback.assert_called_once()


def test_state_update_callback_ignored_before_initial_state():
    appliance = make_appliance(connected=True)
    appliance._sdk_state = None
    appliance._callbacks = set()
    callback = MagicMock()
    appliance.register_callback(callback)
    appliance.state_update_callback({"property": "mode", "value": "DRY"})
    callback.assert_not_called()


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
    appliance = make_appliance(connected=True)
    appliance._sdk_state = ApplianceState(
        applianceId="test_id", connectionState="connected", status="enabled",
        properties={"reported": {"alerts": []}},
    )
    appliance._callbacks = set()
    import logging
    with caplog.at_level(logging.WARNING, logger="custom_components.electrolux_ac.hub"):
        appliance.state_update_callback({"property": "alerts", "value": ["DRAIN_PAN_FULL"]})
    assert any("DRAIN_PAN_FULL" in r.message for r in caplog.records)


def test_state_update_no_warning_when_alerts_empty(caplog):
    appliance = make_appliance(connected=True)
    appliance._sdk_state = ApplianceState(
        applianceId="test_id", connectionState="connected", status="enabled",
        properties={"reported": {"alerts": ["DRAIN_PAN_FULL"]}},
    )
    appliance._callbacks = set()
    import logging
    with caplog.at_level(logging.WARNING, logger="custom_components.electrolux_ac.hub"):
        appliance.state_update_callback({"property": "alerts", "value": []})
    assert not any("alert" in r.message.lower() for r in caplog.records)


@pytest.mark.asyncio
async def test_execute_command_propagates_api_exception():
    appliance = make_appliance()
    appliance._callbacks = set()
    appliance.hub._client.send_command = AsyncMock(side_effect=RuntimeError("API error"))
    with pytest.raises(RuntimeError, match="API error"):
        await appliance.execute_command("mode", "cool")


@pytest.mark.asyncio
async def test_wait_for_state_returns_immediately_without_sleeping_when_already_ready():
    appliance = make_appliance()
    appliance._callbacks = set()
    appliance._states = {"applianceState": "running"}
    appliance.capabilities = {"targetTemperatureC": {"min": 16, "max": 32}}
    sleep_was_called = False

    async def mock_sleep(_):
        nonlocal sleep_was_called
        sleep_was_called = True

    with patch("custom_components.electrolux_ac.hub.asyncio.sleep", side_effect=mock_sleep):
        await appliance.wait_for_state()

    assert not sleep_was_called
