import pytest
from unittest.mock import patch
from homeassistant.components.climate import PRESET_NONE, PRESET_SLEEP
from custom_components.electrolux_ac.climate import ElectroluxClimate


def _make_climate(mock_appliance):
    mock_appliance._states = {
        "temperatureRepresentation": "celsius",
        "sleepMode": "off",
    }
    mock_appliance.appliance_info = {
        "model": "comfort600",
        "brand": "electrolux",
        "deviceType": "PORTABLE_AIR_CONDITIONER",
    }
    return ElectroluxClimate(mock_appliance)


def test_preset_mode_is_none_when_sleep_off(mock_appliance):
    climate = _make_climate(mock_appliance)
    mock_appliance._states["sleepMode"] = "off"
    assert climate.preset_mode == PRESET_NONE


def test_preset_mode_is_sleep_when_sleep_on(mock_appliance):
    climate = _make_climate(mock_appliance)
    mock_appliance._states["sleepMode"] = "on"
    assert climate.preset_mode == PRESET_SLEEP


def test_preset_mode_is_sleep_when_sleep_on_uppercase(mock_appliance):
    climate = _make_climate(mock_appliance)
    mock_appliance._states["sleepMode"] = "ON"
    assert climate.preset_mode == PRESET_SLEEP


def test_preset_mode_is_none_when_key_missing(mock_appliance):
    climate = _make_climate(mock_appliance)
    del mock_appliance._states["sleepMode"]
    assert climate.preset_mode == PRESET_NONE


async def test_set_preset_sleep_sends_on(mock_appliance):
    climate = _make_climate(mock_appliance)
    with patch.object(climate, "async_write_ha_state"):
        await climate.async_set_preset_mode(PRESET_SLEEP)
    mock_appliance.execute_command.assert_called_once_with("sleepMode", "ON")


async def test_set_preset_none_sends_off(mock_appliance):
    climate = _make_climate(mock_appliance)
    with patch.object(climate, "async_write_ha_state"):
        await climate.async_set_preset_mode(PRESET_NONE)
    mock_appliance.execute_command.assert_called_once_with("sleepMode", "OFF")


async def test_set_preset_sleep_updates_local_state_after_successful_command(mock_appliance):
    """sleepMode doesn't push live via SSE for all devices - reflect a confirmed
    successful command locally so the UI doesn't wait for the next poll."""
    climate = _make_climate(mock_appliance)
    with patch.object(climate, "async_write_ha_state"):
        await climate.async_set_preset_mode(PRESET_SLEEP)
    assert mock_appliance._states["sleepMode"] == "ON"
    assert climate.preset_mode == PRESET_SLEEP


async def test_set_preset_none_updates_local_state_after_successful_command(mock_appliance):
    climate = _make_climate(mock_appliance)
    mock_appliance._states["sleepMode"] = "on"
    with patch.object(climate, "async_write_ha_state"):
        await climate.async_set_preset_mode(PRESET_NONE)
    assert mock_appliance._states["sleepMode"] == "OFF"
    assert climate.preset_mode == PRESET_NONE


async def test_set_preset_does_not_update_local_state_when_command_fails(mock_appliance):
    """If execute_command raises, the exception must propagate and local state
    must NOT be mutated to reflect a command that was never confirmed sent."""
    climate = _make_climate(mock_appliance)
    mock_appliance.execute_command.side_effect = RuntimeError("API error")
    with patch.object(climate, "async_write_ha_state"):
        with pytest.raises(RuntimeError):
            await climate.async_set_preset_mode(PRESET_SLEEP)
    assert mock_appliance._states["sleepMode"] == "off"


def test_preset_modes_list(mock_appliance):
    climate = _make_climate(mock_appliance)
    assert climate.preset_modes == [PRESET_NONE, PRESET_SLEEP]


def test_min_temp_from_capabilities(mock_appliance):
    climate = _make_climate(mock_appliance)
    mock_appliance.capabilities = {"targetTemperatureC": {"min": 16, "max": 32}}
    assert climate.min_temp == 16


def test_max_temp_from_capabilities(mock_appliance):
    climate = _make_climate(mock_appliance)
    mock_appliance.capabilities = {"targetTemperatureC": {"min": 16, "max": 32}}
    assert climate.max_temp == 32


def test_min_temp_fallback_when_no_capabilities(mock_appliance):
    climate = _make_climate(mock_appliance)
    mock_appliance.capabilities = {}
    assert climate.min_temp == 16


def test_max_temp_fallback_when_no_capabilities(mock_appliance):
    climate = _make_climate(mock_appliance)
    mock_appliance.capabilities = {}
    assert climate.max_temp == 32
