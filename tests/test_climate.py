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
