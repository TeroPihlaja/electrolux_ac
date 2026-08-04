"""The Electrolux AC integration."""
from __future__ import annotations

from homeassistant.config_entries import ConfigEntry, ConfigEntryNotReady
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed

from electrolux_group_developer_sdk.client.bad_credentials_exception import BadCredentialsException
from electrolux_group_developer_sdk.client.client_exception import ApplianceClientException

from . import hub
from .const import DOMAIN
from .coordinator import ElectroluxSafetyNetCoordinator
import logging

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[str] = ["sensor", "climate"]

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Electrolux AC from a config entry."""
    electrolux_hub = hub.Hub(hass, entry)
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = electrolux_hub

    try:
        await electrolux_hub.discover_appliances()
    except BadCredentialsException as ex:
        await electrolux_hub.disconnect()
        raise ConfigEntryAuthFailed("Electrolux credentials are invalid") from ex
    except ApplianceClientException as ex:
        _LOGGER.error("Error connecting to Electrolux: %s", ex)
        await electrolux_hub.disconnect()
        raise ConfigEntryNotReady(f"Error connecting to Electrolux: {ex}") from ex

    coordinator = ElectroluxSafetyNetCoordinator(hass, entry, electrolux_hub)
    await coordinator.async_config_entry_first_refresh()
    electrolux_hub.coordinator = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    electrolux_hub = hass.data[DOMAIN][entry.entry_id]
    await electrolux_hub.coordinator.async_shutdown()
    await electrolux_hub.disconnect()

    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok
