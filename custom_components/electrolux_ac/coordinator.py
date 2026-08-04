"""Periodic safety-net poll: verifies credentials and refreshes state as a fallback to the SSE stream."""
from __future__ import annotations

from datetime import timedelta
import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from electrolux_group_developer_sdk.client.bad_credentials_exception import BadCredentialsException

_LOGGER = logging.getLogger(__name__)


class ElectroluxSafetyNetCoordinator(DataUpdateCoordinator[None]):
    """Runs every 10 minutes: checks credentials are still valid, then refreshes full appliance state.

    The SSE stream (see hub.py's _start_streaming) is the primary source of updates. This
    coordinator exists because the SSE stream's own reconnect loop swallows every exception
    (including a dead refresh token) into an indefinite retry — it never surfaces auth failure.
    This is the only path in the integration that can raise ConfigEntryAuthFailed after initial
    setup, which is why it uses DataUpdateCoordinator even though no entity reads its data.
    """

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry, hub) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name="electrolux_ac_safety_net",
            config_entry=entry,
            update_interval=timedelta(minutes=10),
        )
        self._hub = hub

    async def _async_update_data(self) -> None:
        try:
            await self._hub.test_connection()
        except BadCredentialsException as ex:
            raise ConfigEntryAuthFailed("Electrolux credentials are no longer valid") from ex
        except Exception as ex:
            raise UpdateFailed(f"Error verifying Electrolux connection: {ex}") from ex
        try:
            await self._hub.full_refresh()
        except Exception as ex:
            raise UpdateFailed(f"Error refreshing Electrolux appliance data: {ex}") from ex
