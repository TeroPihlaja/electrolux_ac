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

class Hub:
    def __init__(self, hass: HomeAssistant, email: str, password: str):
        _LOGGER.debug("Creating Electrolux hub with email %s", email)

        self._email = email
        self._password = password
        self._hass = hass
        self._name = email
        self._id = email.lower()
        self._client = None
        self.appliances = None
        self.online = False

    @property
    def hub_id(self) -> str:
        """ID for dummy hub."""
        return self._id

    async def connect(self) -> any:
        """Connect to the hub."""
        _LOGGER.debug("Connecting to Electrolux hub")
        self._client = OneAppApi(self._email, self._password,"fi" , logger=_LOGGER)
        self.online = True

    async def disconnect(self):
        """Disconnect from the hub."""
        _LOGGER.debug("Disconnecting from Electrolux hub")
        if self._client is not None:
            await self._client.close()
        self._client = None
        self.online = False

    async def discover_appliances(self):
        if not self.online:
          await self.connect()
        appliances = await self._client.get_appliances_list()
        appliances_out = []
        for appliance in appliances:
          appliances_out.extend([Appliance(appliance.get("applianceId"), appliance.get("applianceData").get("applianceName"), self)])
        self.appliances = appliances_out
    
    async def test_connection(self) -> bool:
        try:
          if not self.online:
            await self.connect()
        except Exception:  # pylint: disable=broad-except
          _LOGGER.exception("Unable to connect")
          return False
        return True

    async def update_loop(self):
        """Update loop for the hub."""
        while True:
            await asyncio.sleep(1800)
            if not self.online:
                await self.connect()
            await self.discover_appliances()

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

        asyncio.ensure_future(self.update_appliance_info())
        asyncio.ensure_future(self.watch_for_state_updates())

    async def wait_for_state(self):
        STATE_MAX = 5
        for i in range(STATE_MAX):
            _LOGGER.debug("Waiting for initial state: %d/%d", i + 1, STATE_MAX)
            await asyncio.sleep(5)
            if self._states:
                return
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
      for key, value in data[self._id].items():
        self._states[key] = value
      _LOGGER.debug("current state: %s", self._states)
      self.publish_updates()

    async def update_appliance_info(self):
      info = await self.hub._client.get_appliances_info([self._id])
      _LOGGER.debug("appliance info: %s", json.dumps(info))
      self.appliance_info = info[0]
      
      capab = await self.hub._client.get_appliance_capabilities(self._id)
      _LOGGER.debug("appliance capabilities: %s", json.dumps(capab))

      self.capabilities = capab

    @property
    def appliance_id(self) -> str:
        """Return ID for appliance."""
        return self._id

    async def execute_command(self, command: str, value: str):
      await asyncio.ensure_future(self.hub._client.execute_appliance_command(self._id, {command: value}))
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
    def online(self) -> float:
        """appliance is online."""
        return True

class ApplianceStateNotReady(exceptions.HomeAssistantError):
    """Error to indicate we cannot find state information for appliance."""
