"""A demonstration 'hub' that connects several devices."""
from __future__ import annotations

import asyncio
import json

from homeassistant.core import HomeAssistant
from homeassistant import exceptions
from collections.abc import Callable

from pyelectroluxocp import OneAppApi
import logging

_LOGGER = logging.getLogger(__name__)

# Capabilities we handle or knowingly ignore. Anything else is logged as unsupported.
_KNOWN_CAPABILITIES = {
    # Controlled by the climate entity
    "executeCommand", "targetTemperatureC", "fanSpeedSetting",
    "mode", "verticalSwing", "sleepMode",
    # Read-only / exposed as sensors
    "applianceState", "fanSpeedState", "networkInterface", "ambientTemperatureC",
    "alerts",
    # Known but not yet implemented
    "uiLockMode", "startTime", "stopTime",
}

_ISSUE_TRACKER = "https://github.com/TeroPihlaja/electrolux_ac/issues"

class Hub:
    def __init__(self, hass: HomeAssistant, email: str, password: str, country_code: str = "fi"):
        _LOGGER.debug("Creating Electrolux hub with email %s", email)

        self._email = email
        self._password = password
        self._hass = hass
        self._name = email
        self._id = email.lower()
        self._client = None
        self.appliances = None
        self.online = False
        self._country_code = country_code
        self._update_task = None

    @property
    def hub_id(self) -> str:
        """ID for dummy hub."""
        return self._id

    async def connect(self) -> any:
        """Connect to the hub."""
        _LOGGER.debug("Connecting to Electrolux hub")
        self._client = OneAppApi(self._email, self._password, self._country_code, logger=_LOGGER)
        self.online = True

    async def disconnect(self):
        """Disconnect from the hub."""
        _LOGGER.debug("Disconnecting from Electrolux hub")
        if self._update_task is not None:
            self._update_task.cancel()
            self._update_task = None
        if self._client is not None:
            await self._client.close()
        self._client = None
        self.online = False

    async def discover_appliances(self):
        if not self.online:
          await self.connect()
        appliances_raw = await self._client.get_appliances_list()
        appliances_out = []
        for appliance_data in appliances_raw:
          appliance = Appliance(
              appliance_data.get("applianceId"),
              appliance_data.get("applianceData", {}).get("applianceName"),
              self,
          )
          appliance._connected = (appliance_data.get("connectionState") == "Connected")
          appliances_out.append(appliance)
        self.appliances = appliances_out
        if self._update_task is None:
            self._update_task = asyncio.ensure_future(self.update_loop())

    async def refresh_connection_state(self):
        """Poll connectionState for all known appliances and update _connected in-place."""
        try:
            appliances_raw = await self._client.get_appliances_list()
            state_by_id = {a.get("applianceId"): a for a in appliances_raw}
            for appliance in (self.appliances or []):
                raw = state_by_id.get(appliance.appliance_id, {})
                was_connected = appliance._connected
                appliance._connected = (raw.get("connectionState") == "Connected")
                if appliance._connected != was_connected:
                    _LOGGER.debug(
                        "Appliance %s is now %s",
                        appliance.appliance_id,
                        "connected" if appliance._connected else "disconnected",
                    )
                    appliance.publish_updates()
        except Exception:
            _LOGGER.debug("Failed to refresh connection state", exc_info=True)

    async def test_connection(self) -> bool:
        try:
          if not self.online:
            await self.connect()
        except Exception:  # pylint: disable=broad-except
          _LOGGER.exception("Unable to connect")
          return False
        return True

    async def update_loop(self):
        """Poll appliance connection state every 10 minutes."""
        while True:
            await asyncio.sleep(600)
            await self.refresh_connection_state()

class Appliance:
    """Dummy appliance (device for HA) for Hello World example."""

    def __init__(self, applianceid: str, name: str, hub: Hub):
        """Init dummy appliance."""
        self._id = applianceid
        self.hub = hub
        self.name = name
        self._callbacks = set()

        self.capabilities = {}

        self._states = {}
        self.appliance_info = None

        self.manufacturer = None
        self.firmware_version = None
        self.model = None

        self._following_changes = False
        self._connected = False

        asyncio.ensure_future(self.update_appliance_info())
        asyncio.ensure_future(self.watch_for_state_updates())

    async def wait_for_state(self):
        STATE_MAX = 5
        for i in range(STATE_MAX):
            if self._states and self.capabilities:
                return
            _LOGGER.debug("Waiting for initial state: %d/%d", i + 1, STATE_MAX)
            await asyncio.sleep(5)
        raise ApplianceStateNotReady(
            "Did not receive state information for appliance: %s" % self._id
        )

    async def watch_for_state_updates(self):
      if self._following_changes:
        return
      await self.hub._client.watch_for_appliance_state_updates([self._id], self.state_update_callback)
      self._following_changes = True

    def state_update_callback(self, data):
      _LOGGER.debug("appliance state updated: %s", json.dumps(data))
      if self._id not in data:
        return
      self._connected = True
      for key, value in data[self._id].items():
        self._states[key] = value
      alerts = self._states.get("alerts")
      if alerts:
          _LOGGER.warning(
              "Appliance %s has active alerts: %s — "
              "please report the format at %s",
              self._id, alerts, _ISSUE_TRACKER,
          )
      _LOGGER.debug("current state: %s", self._states)
      self.publish_updates()

    async def update_appliance_info(self):
      info = await self.hub._client.get_appliances_info([self._id])
      _LOGGER.debug("appliance info: %s", json.dumps(info))
      if not info:
          _LOGGER.warning("No info returned for appliance %s — skipping info/capabilities fetch", self._id)
          return
      self.appliance_info = info[0]

      capab = await self.hub._client.get_appliance_capabilities(self._id)
      _LOGGER.debug("appliance capabilities: %s", json.dumps(capab))

      self.capabilities = capab

      unknown = sorted(set(capab.keys()) - _KNOWN_CAPABILITIES)
      for key in unknown:
          _LOGGER.warning(
              "Unsupported capability '%s' found on appliance %s. "
              "Please open an issue at %s so it can be added.",
              key, self._id, _ISSUE_TRACKER,
          )

    @property
    def appliance_id(self) -> str:
        """Return ID for appliance."""
        return self._id

    async def execute_command(self, command: str, value: str):
      await self.hub._client.execute_appliance_command(self._id, {command: value})
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
