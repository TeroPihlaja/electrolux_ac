"""Hub (API connection) and Appliance (state + callbacks) for the Electrolux AC integration."""
from __future__ import annotations

import asyncio
import json

from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant import exceptions
from collections.abc import Callable

from electrolux_group_developer_sdk.auth.token_manager import TokenManager
from electrolux_group_developer_sdk.client.appliance_client import (
    ApplianceClient,
    apply_sse_update,
)
import logging

_LOGGER = logging.getLogger(__name__)

_ISSUE_TRACKER = "https://github.com/TeroPihlaja/electrolux_ac/issues"

class Hub:
    def __init__(self, hass: HomeAssistant, entry: ConfigEntry):
        _LOGGER.debug("Creating Electrolux hub for entry %s", entry.entry_id)

        self._hass = hass
        self._entry = entry
        self._id = entry.entry_id
        self._client: ApplianceClient | None = None
        self.appliances = None
        self.online = False
        self._update_task = None
        self.coordinator = None

    @property
    def hub_id(self) -> str:
        """ID for dummy hub."""
        return self._id

    def _persist_tokens(self, access_token: str, refresh_token: str, api_key: str) -> None:
        """Persist rotated tokens so they survive a restart."""
        self._hass.config_entries.async_update_entry(
            self._entry,
            data={
                "api_key": api_key,
                "access_token": access_token,
                "refresh_token": refresh_token,
            },
        )

    async def connect(self) -> any:
        """Connect to the hub."""
        _LOGGER.debug("Connecting to Electrolux hub")
        token_manager = TokenManager(
            access_token=self._entry.data["access_token"],
            refresh_token=self._entry.data["refresh_token"],
            api_key=self._entry.data["api_key"],
            on_token_update=self._persist_tokens,
        )
        self._client = ApplianceClient(token_manager=token_manager)
        self.online = True

    async def disconnect(self):
        """Disconnect from the hub."""
        _LOGGER.debug("Disconnecting from Electrolux hub")
        if self._update_task is not None:
            self._update_task.cancel()
            try:
                await self._update_task
            except asyncio.CancelledError:
                pass
            self._update_task = None
        self._client = None
        self.online = False

    async def discover_appliances(self):
        if not self.online:
            await self.connect()
        appliances_data = await self._client.get_appliance_data()
        appliances_out = []
        for data in appliances_data:
            appliance = Appliance(
                data.appliance.applianceId,
                data.appliance.applianceName,
                self,
            )
            self._apply_appliance_data(appliance, data)
            appliances_out.append(appliance)
        self.appliances = appliances_out
        if self._update_task is None:
            self._update_task = asyncio.ensure_future(self._start_streaming())

    def _apply_appliance_data(self, appliance: "Appliance", data) -> None:
        # data.details is transiently absent on some refreshes (SSE reconnect, safety-net
        # poll); keep the last-known capabilities/appliance_info rather than blanking an
        # already-populated entity back to None/{}.
        if data.details:
            appliance.capabilities = data.details.capabilities
            appliance.appliance_info = {
                "model": data.details.applianceInfo.model,
                "brand": data.details.applianceInfo.brand,
                "deviceType": data.details.applianceInfo.deviceType,
            }
        appliance._sdk_state = data.state
        appliance._states = (
            data.state.properties.get("reported", {}) if data.state else {}
        )
        appliance._connected = bool(
            data.state and data.state.connectionState.lower() == "connected"
        )

    async def _start_streaming(self):
        """Register SSE listeners for all appliances and open the livestream."""
        for appliance in self.appliances or []:
            self._client.add_listener(appliance.appliance_id, appliance.state_update_callback)
        await self._client.start_event_stream(
            do_on_livestream_opening_list=[self.full_refresh]
        )

    async def full_refresh(self):
        """Re-fetch full appliance data. Used on every SSE (re)connect and by the safety-net coordinator."""
        if self._client is None:
            return
        appliances_data = await self._client.get_appliance_data()
        by_id = {data.appliance.applianceId: data for data in appliances_data}
        for appliance in self.appliances or []:
            data = by_id.get(appliance.appliance_id)
            if data is not None:
                self._apply_appliance_data(appliance, data)
                appliance.publish_updates()

    async def test_connection(self) -> None:
        """Verify credentials are valid. Raises BadCredentialsException if not."""
        if not self.online:
            await self.connect()
        await self._client.test_connection()


class Appliance:
    """Represents one Electrolux appliance."""

    def __init__(self, applianceid: str, name: str, hub: Hub):
        """Init appliance. Data (capabilities/_states/appliance_info) is populated by the caller."""
        self._id = applianceid
        self.hub = hub
        self.name = name
        self._callbacks = set()

        self.capabilities = {}
        self._states = {}
        self._sdk_state = None
        self.appliance_info = None

        self._connected = False

    async def wait_for_state(self):
        # capabilities is intentionally not required here: it's optional (properties that
        # use it, like min/max temperature, already fall back to sane defaults), and
        # requiring it caused appliances with valid state but transiently-missing details
        # to be skipped forever.
        STATE_MAX = 5
        for i in range(STATE_MAX):
            if self._states:
                return
            _LOGGER.debug("Waiting for initial state: %d/%d", i + 1, STATE_MAX)
            await asyncio.sleep(5)
        raise ApplianceStateNotReady(
            "Did not receive state information for appliance: %s" % self._id
        )

    def state_update_callback(self, event: dict) -> None:
        """Handle a single SSE property-update event for this appliance."""
        _LOGGER.debug("appliance state event: %s", json.dumps(event))
        if self._sdk_state is None:
            return
        self._sdk_state = apply_sse_update(self._sdk_state, event)
        self._states = self._sdk_state.properties.get("reported", {})
        self._connected = self._sdk_state.connectionState.lower() == "connected"
        alerts = self._states.get("alerts")
        if alerts:
            _LOGGER.warning(
                "Appliance %s has active alerts: %s — "
                "please report the format at %s",
                self._id, alerts, _ISSUE_TRACKER,
            )
        _LOGGER.debug("current state: %s", self._states)
        self.publish_updates()

    @property
    def appliance_id(self) -> str:
        """Return ID for appliance."""
        return self._id

    async def execute_command(self, command: str, value: str):
        client = self.hub._client
        if client is None:
            raise ApplianceNotConnected(
                "Cannot send command %s to appliance %s: not connected" % (command, self._id)
            )
        await client.send_command(self._id, {command: value})
        return True

    def register_callback(self, callback: Callable[[], None]):
        """Register callback, called when appliance changes state."""
        self._callbacks.add(callback)

    def remove_callback(self, callback: Callable[[], None]):
        """Remove previously registered callback."""
        self._callbacks.discard(callback)

    def publish_updates(self):
        """Schedule call all registered callbacks."""
        for callback in self._callbacks:
            callback()

    @property
    def online(self) -> bool:
        """Return True if the appliance is connected to the cloud."""
        return self._connected


class ApplianceStateNotReady(exceptions.HomeAssistantError):
    """Error to indicate we cannot find state information for appliance."""


class ApplianceNotConnected(exceptions.HomeAssistantError):
    """Error to indicate a command was attempted while the hub is disconnected."""
