import pytest
from unittest.mock import patch, AsyncMock
from homeassistant.const import UnitOfTemperature
from homeassistant.components.climate import HVACMode
from custom_components.electrolux_ac.climate import ElectroluxClimate


def _make_climate(mock_appliance):
    mock_appliance._states = {
        "temperatureRepresentation": "celsius",
        "applianceState": "off",
        "mode": "cool",
        "sleepMode": "off",
    }
    mock_appliance.appliance_info = {
        "model": "comfort600",
        "brand": "electrolux",
        "deviceType": "PORTABLE_AIR_CONDITIONER",
    }
    mock_appliance.capabilities = {}
    return ElectroluxClimate(mock_appliance)


@pytest.mark.asyncio
async def test_turn_on_does_not_mutate_appliance_states(mock_appliance):
    climate = _make_climate(mock_appliance)
    mock_appliance._states["applianceState"] = "off"
    with patch.object(climate, "async_write_ha_state"):
        await climate.async_turn_on()
    assert mock_appliance._states["applianceState"] == "off"


@pytest.mark.asyncio
async def test_turn_off_does_not_mutate_appliance_states(mock_appliance):
    climate = _make_climate(mock_appliance)
    mock_appliance._states["applianceState"] = "running"
    with patch.object(climate, "async_write_ha_state"):
        await climate.async_turn_off()
    assert mock_appliance._states["applianceState"] == "running"


@pytest.mark.asyncio
async def test_set_temperature_no_op_when_temperature_kwarg_absent(mock_appliance):
    climate = _make_climate(mock_appliance)
    with patch.object(climate, "async_write_ha_state"):
        await climate.async_set_temperature()  # no kwargs — simulates HA passing only range bounds
    mock_appliance.execute_command.assert_not_called()


def test_temperature_unit_defaults_to_celsius_when_representation_absent(mock_appliance):
    mock_appliance._states = {}  # no temperatureRepresentation key
    mock_appliance.appliance_info = {"model": "comfort600", "brand": "electrolux"}
    mock_appliance.capabilities = {}
    climate = ElectroluxClimate(mock_appliance)
    assert climate.temperature_unit == UnitOfTemperature.CELSIUS


def test_temperature_unit_is_fahrenheit_when_representation_is_fahrenheit(mock_appliance):
    mock_appliance._states = {"temperatureRepresentation": "fahrenheit"}
    mock_appliance.appliance_info = {"model": "comfort600", "brand": "electrolux"}
    mock_appliance.capabilities = {}
    climate = ElectroluxClimate(mock_appliance)
    assert climate.temperature_unit == UnitOfTemperature.FAHRENHEIT
