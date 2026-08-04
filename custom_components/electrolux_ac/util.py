"""Shared helpers for resolving the appliance's configured temperature unit."""
from __future__ import annotations

from homeassistant.const import UnitOfTemperature


def temperature_unit(states: dict) -> str:
    """Return CELSIUS or FAHRENHEIT based on the appliance's temperatureRepresentation state."""
    if (states.get("temperatureRepresentation") or "").lower() == "fahrenheit":
        return UnitOfTemperature.FAHRENHEIT
    return UnitOfTemperature.CELSIUS


def unit_suffix(unit: str) -> str:
    """Return the "C"/"F" suffix used in state and capability keys for the given unit."""
    return "F" if unit == UnitOfTemperature.FAHRENHEIT else "C"
