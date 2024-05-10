"""The Detailed Hello World Push integration."""
from __future__ import annotations

from homeassistant.config_entries import ConfigEntry, ConfigEntryNotReady
from homeassistant.core import HomeAssistant

from . import hub
from .const import DOMAIN
import aiohttp
import asyncio

import logging

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[str] = ["sensor", "climate"]

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Hello World from a config entry."""
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = hub.Hub(hass, entry.data["email"], entry.data["password"])
    try:
        await hass.data[DOMAIN][entry.entry_id].discover_appliances()
    except aiohttp.client_exceptions.ClientResponseError as ex:
        _LOGGER.error("Error connecting to Electrolux OCP: %s", ex)
        await hass.data[DOMAIN][entry.entry_id].disconnect()
        await asyncio.sleep(60)
        raise ConfigEntryNotReady("Error connecting to Electrolux OCP: %s", ex) from ex
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    await hass.data[DOMAIN][entry.entry_id].disconnect()

    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok