# Country Code, Online Detection, and Alerts Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add country code to the config flow, fix the hardcoded `"fi"` in the API client, detect appliance online/offline status from the API response, and expose alerts as a sensor with a warning log.

**Architecture:** Country code is stored in the config entry and threaded through Hub → OneAppApi. Online status is derived from `connectionState` in `get_appliances_list()` at startup and updated to `True` on any state push (meaning the device is communicating). Alerts are exposed via the existing `GenericSensor` pattern and also logged at WARNING level when non-empty, since we can't trigger a real alert to verify the data format.

**Tech Stack:** Python 3.14, Home Assistant custom component, pyelectroluxocp, voluptuous, pytest

---

## Files

- Modify: `custom_components/electrolux_ac/const.py` — add `CONF_COUNTRY_CODE`
- Modify: `custom_components/electrolux_ac/hub.py` — accept `country_code`, fix OneAppApi call, add `_connected` to Appliance, alert warning in callback
- Modify: `custom_components/electrolux_ac/__init__.py` — pass country_code to Hub
- Modify: `custom_components/electrolux_ac/config_flow.py` — add country_code field with HA country default
- Modify: `custom_components/electrolux_ac/strings.json` — add country_code label
- Modify: `custom_components/electrolux_ac/translations/en.json` — add country_code label
- Modify: `custom_components/electrolux_ac/sensor.py` — register alerts sensor, add `alerts` to `_KNOWN_CAPABILITIES`
- Modify: `tests/test_hub.py` — new test file for online detection and alert warning

---

## Task 1: Country code constant and Hub wiring (TDD)

**Files:**
- Modify: `custom_components/electrolux_ac/const.py`
- Modify: `custom_components/electrolux_ac/hub.py`
- Create: `tests/test_hub.py`

- [ ] **Step 1: Write failing tests in `tests/test_hub.py`**

```python
from unittest.mock import MagicMock, patch, AsyncMock
import pytest
from custom_components.electrolux_ac.hub import Hub


def make_hub(hass=None, country_code="fi"):
    hass = hass or MagicMock()
    return Hub(hass, "test@example.com", "secret", country_code)


@pytest.mark.asyncio
async def test_hub_passes_country_code_to_api():
    hub = make_hub(country_code="de")
    with patch(
        "custom_components.electrolux_ac.hub.OneAppApi"
    ) as mock_api_cls:
        mock_api_cls.return_value = MagicMock()
        await hub.connect()
    mock_api_cls.assert_called_once()
    args, kwargs = mock_api_cls.call_args
    assert args[2] == "de"


@pytest.mark.asyncio
async def test_hub_defaults_country_code_fi():
    hub = Hub(MagicMock(), "test@example.com", "secret", "fi")
    with patch(
        "custom_components.electrolux_ac.hub.OneAppApi"
    ) as mock_api_cls:
        mock_api_cls.return_value = MagicMock()
        await hub.connect()
    args, _ = mock_api_cls.call_args
    assert args[2] == "fi"
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd /Users/teropihlaja/dev/electrolux_ac
.venv/bin/pytest tests/test_hub.py -v
```

Expected: `FAILED` — `Hub.__init__` does not accept `country_code`.

- [ ] **Step 3: Add `CONF_COUNTRY_CODE` to `const.py`**

```python
DOMAIN = "electrolux_ac"
TARGET_TEMPERATURE_STEP = 1
CONF_COUNTRY_CODE = "country_code"
```

- [ ] **Step 4: Update `Hub.__init__` and `connect()` in `hub.py`**

Change `Hub.__init__` signature and body:

```python
class Hub:
    def __init__(self, hass: HomeAssistant, email: str, password: str, country_code: str = "fi"):
        _LOGGER.debug("Creating Electrolux hub with email %s", email)

        self._email = email
        self._password = password
        self._country_code = country_code
        self._hass = hass
        self._name = email
        self._id = email.lower()
        self._client = None
        self.appliances = None
        self.online = False
```

Change `connect()`:

```python
    async def connect(self) -> any:
        """Connect to the hub."""
        _LOGGER.debug("Connecting to Electrolux hub")
        self._client = OneAppApi(self._email, self._password, self._country_code, logger=_LOGGER)
        self.online = True
```

- [ ] **Step 5: Run tests to verify they pass**

```bash
.venv/bin/pytest tests/test_hub.py -v
```

Expected: 2 PASSED.

- [ ] **Step 6: Commit**

```bash
git -C /Users/teropihlaja/dev/electrolux_ac add custom_components/electrolux_ac/const.py custom_components/electrolux_ac/hub.py tests/test_hub.py
git -C /Users/teropihlaja/dev/electrolux_ac commit -m "feat: make country code configurable in Hub"
```

---

## Task 2: Pass country code through config entry and config flow

**Files:**
- Modify: `custom_components/electrolux_ac/__init__.py`
- Modify: `custom_components/electrolux_ac/config_flow.py`
- Modify: `custom_components/electrolux_ac/strings.json`
- Modify: `custom_components/electrolux_ac/translations/en.json`

- [ ] **Step 1: Update `__init__.py` to pass country_code to Hub**

Replace the Hub construction line in `async_setup_entry`:

```python
from .const import DOMAIN, CONF_COUNTRY_CODE

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Hello World from a config entry."""
    country_code = entry.data.get(CONF_COUNTRY_CODE, "fi")
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = hub.Hub(
        hass, entry.data["email"], entry.data["password"], country_code
    )
    try:
        await hass.data[DOMAIN][entry.entry_id].discover_appliances()
    except aiohttp.client_exceptions.ClientResponseError as ex:
        _LOGGER.error("Error connecting to Electrolux OCP: %s", ex)
        await hass.data[DOMAIN][entry.entry_id].disconnect()
        raise ConfigEntryNotReady("Error connecting to Electrolux OCP: %s" % ex) from ex
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True
```

- [ ] **Step 2: Update `config_flow.py` to add country_code field**

Replace the entire `config_flow.py`:

```python
"""Config flow for Electrolux AC integration."""
from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol
import aiohttp

from homeassistant import config_entries, exceptions
from homeassistant.core import HomeAssistant

from .const import DOMAIN, CONF_COUNTRY_CODE
from .hub import Hub

_LOGGER = logging.getLogger(__name__)


async def validate_input(hass: HomeAssistant, data: dict) -> dict[str, Any]:
    hub = Hub(hass, data["email"], data["password"], data[CONF_COUNTRY_CODE])
    try:
        result = await hub.test_connection()
        if not result:
            raise CannotConnect
    except aiohttp.client_exceptions.ClientResponseError:
        raise InvalidAuth
    finally:
        await hub.disconnect()

    return {"title": data["email"]}


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Electrolux AC."""

    VERSION = 1

    async def async_step_user(self, user_input=None):
        """Handle the initial step."""
        default_country = (self.hass.config.country or "fi").lower()

        errors = {}
        if user_input is not None:
            try:
                info = await validate_input(self.hass, user_input)
                return self.async_create_entry(title=info["title"], data=user_input)
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except InvalidAuth:
                errors["base"] = "cannot_connect"
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"

        schema = vol.Schema({
            vol.Required("email"): str,
            vol.Required("password"): str,
            vol.Required(CONF_COUNTRY_CODE, default=default_country): str,
        })

        return self.async_show_form(
            step_id="user", data_schema=schema, errors=errors
        )


class CannotConnect(exceptions.HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidAuth(exceptions.HomeAssistantError):
    """Error to indicate there is an invalid credentials."""
```

- [ ] **Step 3: Update `strings.json`**

```json
{
  "config": {
    "step": {
      "user": {
        "title": "Login information",
        "description": "Please enter your login information. This is the same information you use to log in to the Electrolux mobile app.",
        "data": {
          "email": "Email address",
          "password": "Password",
          "country_code": "Country code (2 letters, e.g. fi, us, de)"
        }
      }
    },
    "error": {
      "cannot_connect": "[%key:common::config_flow::error::cannot_connect%]",
      "invalid_auth": "[%key:common::config_flow::error::invalid_auth%]",
      "unknown": "[%key:common::config_flow::error::unknown%]"
    },
    "abort": {
      "already_configured": "[%key:common::config_flow::abort::already_configured_device%]"
    }
  }
}
```

- [ ] **Step 4: Update `translations/en.json`** (same content as strings.json)

```json
{
  "config": {
    "step": {
      "user": {
        "title": "Login information",
        "description": "Please enter your login information. This is the same information you use to log in to the Electrolux mobile app.",
        "data": {
          "email": "Email address",
          "password": "Password",
          "country_code": "Country code (2 letters, e.g. fi, us, de)"
        }
      }
    },
    "error": {
      "cannot_connect": "[%key:common::config_flow::error::cannot_connect%]",
      "invalid_auth": "[%key:common::config_flow::error::invalid_auth%]",
      "unknown": "[%key:common::config_flow::error::unknown%]"
    },
    "abort": {
      "already_configured": "[%key:common::config_flow::abort::already_configured_device%]"
    }
  }
}
```

- [ ] **Step 5: Run full test suite**

```bash
.venv/bin/pytest tests/ -v
```

Expected: all 14 tests PASSED.

- [ ] **Step 6: Commit**

```bash
git -C /Users/teropihlaja/dev/electrolux_ac add custom_components/ tests/
git -C /Users/teropihlaja/dev/electrolux_ac commit -m "feat: add country code to config flow"
```

---

## Task 3: Online detection from connectionState + 30-min polling (TDD)

**Files:**
- Modify: `custom_components/electrolux_ac/hub.py`
- Modify: `custom_components/electrolux_ac/__init__.py`
- Modify: `tests/test_hub.py`

`Appliance.online` returns `True` unconditionally. Fix it to use `connectionState` from `get_appliances_list()` at startup, set to `True` on any incoming state update (device is clearly communicating), and refreshed every 30 minutes by a background poll loop.

The poll uses a new `refresh_connection_state()` method — lightweight, no appliance recreation, no callback loss. The loop is started after `discover_appliances()` and cancelled in `disconnect()`.

**Why `refresh_connection_state()` instead of re-calling `discover_appliances()`:** `discover_appliances()` creates new `Appliance` objects, which would lose all registered HA callbacks. `refresh_connection_state()` updates `_connected` in-place on existing objects.

- [ ] **Step 1: Add tests to `tests/test_hub.py`**

```python
from custom_components.electrolux_ac.hub import Appliance, Hub


def make_appliance(connected=True):
    hub = MagicMock()
    hub._client = MagicMock()
    with patch("custom_components.electrolux_ac.hub.asyncio.ensure_future"):
        appliance = Appliance("test_id", "Test AC", hub)
    appliance._connected = connected
    return appliance


def test_appliance_online_false_when_not_connected():
    appliance = make_appliance(connected=False)
    assert appliance.online is False


def test_appliance_online_true_when_connected():
    appliance = make_appliance(connected=True)
    assert appliance.online is True


def test_state_update_sets_connected():
    appliance = make_appliance(connected=False)
    appliance._callbacks = set()
    appliance.state_update_callback({"test_id": {"applianceState": "running"}})
    assert appliance._connected is True


@pytest.mark.asyncio
async def test_refresh_connection_state_updates_connected():
    hub = make_hub()
    with patch("custom_components.electrolux_ac.hub.asyncio.ensure_future"):
        appliance = Appliance("test_id", "Test AC", hub)
    appliance._connected = True
    hub.appliances = [appliance]
    hub._client = AsyncMock()
    hub._client.get_appliances_list.return_value = [
        {"applianceId": "test_id", "connectionState": "Disconnected",
         "applianceData": {"applianceName": "Test AC"}}
    ]
    await hub.refresh_connection_state()
    assert appliance._connected is False


@pytest.mark.asyncio
async def test_refresh_connection_state_publishes_on_change():
    hub = make_hub()
    with patch("custom_components.electrolux_ac.hub.asyncio.ensure_future"):
        appliance = Appliance("test_id", "Test AC", hub)
    appliance._connected = True
    callback = MagicMock()
    appliance.register_callback(callback)
    hub.appliances = [appliance]
    hub._client = AsyncMock()
    hub._client.get_appliances_list.return_value = [
        {"applianceId": "test_id", "connectionState": "Disconnected",
         "applianceData": {"applianceName": "Test AC"}}
    ]
    await hub.refresh_connection_state()
    callback.assert_called_once()
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
.venv/bin/pytest tests/test_hub.py::test_appliance_online_false_when_not_connected tests/test_hub.py::test_appliance_online_true_when_connected tests/test_hub.py::test_state_update_sets_connected tests/test_hub.py::test_refresh_connection_state_updates_connected tests/test_hub.py::test_refresh_connection_state_publishes_on_change -v
```

Expected: FAILED — `Appliance` has no `_connected`, Hub has no `refresh_connection_state`.

- [ ] **Step 3: Update `hub.py`**

In `Hub.__init__`, add `self._update_task = None`:

```python
        self._client = None
        self.appliances = None
        self.online = False
        self._update_task = None
```

In `Hub.disconnect()`, cancel the poll task:

```python
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
```

Add new `refresh_connection_state()` method to `Hub` (after `discover_appliances`):

```python
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
```

Replace `update_loop()` with:

```python
    async def update_loop(self):
        """Poll appliance connection state every 30 minutes."""
        while True:
            await asyncio.sleep(1800)
            await self.refresh_connection_state()
```

In `Appliance.__init__`, add `self._connected = False`:

```python
        self._following_changes = False
        self._connected = False
```

Change `Appliance.online` property:

```python
    @property
    def online(self) -> bool:
        """Return True if the appliance is connected to the cloud."""
        return self._connected
```

In `state_update_callback`, add `self._connected = True`:

```python
    def state_update_callback(self, data):
      _LOGGER.debug("appliance state updated: %s", json.dumps(data))
      if self._id not in data:
        return
      self._connected = True
      for key, value in data[self._id].items():
        self._states[key] = value
      _LOGGER.debug("current state: %s", self._states)
      self.publish_updates()
```

In `discover_appliances()`, set `_connected` from the API and start poll loop:

```python
    async def discover_appliances(self):
        if not self.online:
          await self.connect()
        appliances_raw = await self._client.get_appliances_list()
        appliances_out = []
        for appliance_data in appliances_raw:
          appliance = Appliance(
              appliance_data.get("applianceId"),
              appliance_data.get("applianceData").get("applianceName"),
              self,
          )
          appliance._connected = (appliance_data.get("connectionState") == "Connected")
          appliances_out.append(appliance)
        self.appliances = appliances_out
        if self._update_task is None:
            self._update_task = asyncio.ensure_future(self.update_loop())
```

- [ ] **Step 4: Run tests**

```bash
.venv/bin/pytest tests/ -v
```

Expected: all tests PASS.

- [ ] **Step 5: Commit**

```bash
git -C /Users/teropihlaja/dev/electrolux_ac add custom_components/electrolux_ac/hub.py tests/test_hub.py
git -C /Users/teropihlaja/dev/electrolux_ac commit -m "feat: detect appliance online status with 30-min polling"
```

---

## Task 4: Alerts sensor and warning log (TDD)

**Files:**
- Modify: `custom_components/electrolux_ac/sensor.py`
- Modify: `custom_components/electrolux_ac/hub.py`
- Modify: `tests/test_hub.py`

Add `alerts` as a `GenericSensor` so its value is visible in HA. Also log a WARNING in `state_update_callback` when `alerts` is non-empty, since we can't trigger a real alert to know the format.

- [ ] **Step 1: Add alert warning test to `tests/test_hub.py`**

```python
def test_state_update_logs_warning_for_non_empty_alerts(caplog):
    appliance = make_appliance()
    appliance._callbacks = set()
    import logging
    with caplog.at_level(logging.WARNING, logger="custom_components.electrolux_ac.hub"):
        appliance.state_update_callback({
            "test_id": {"alerts": ["DRAIN_PAN_FULL"], "applianceState": "running"}
        })
    assert any("DRAIN_PAN_FULL" in r.message for r in caplog.records)


def test_state_update_no_warning_when_alerts_empty(caplog):
    appliance = make_appliance()
    appliance._callbacks = set()
    import logging
    with caplog.at_level(logging.WARNING, logger="custom_components.electrolux_ac.hub"):
        appliance.state_update_callback({
            "test_id": {"alerts": [], "applianceState": "running"}
        })
    assert not any("alert" in r.message.lower() for r in caplog.records)
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
.venv/bin/pytest tests/test_hub.py::test_state_update_logs_warning_for_non_empty_alerts tests/test_hub.py::test_state_update_no_warning_when_alerts_empty -v
```

Expected: FAILED.

- [ ] **Step 3: Add alert warning to `state_update_callback` in `hub.py`**

After the state update loop, before `self.publish_updates()`:

```python
      alerts = self._states.get("alerts")
      if alerts:
          _LOGGER.warning(
              "Appliance %s has active alerts: %s — "
              "please report the format at %s",
              self._id, alerts, _ISSUE_TRACKER,
          )
```

- [ ] **Step 4: Run tests**

```bash
.venv/bin/pytest tests/test_hub.py -v
```

Expected: all hub tests PASS.

- [ ] **Step 5: Register alerts sensor in `sensor.py`**

In `async_setup_entry`, add after the HEPA filter lifetime sensor:

```python
    new_devices.append(GenericSensor(
      appliance, "alerts", "Alerts", "alerts",
      None, None, None,
    ))
```

Add `"alerts"` to `_KNOWN_CAPABILITIES` in `hub.py` (remove it from the "known but not implemented" set):

```python
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
```

- [ ] **Step 6: Run full test suite**

```bash
.venv/bin/pytest tests/ -v
```

Expected: all tests PASS.

- [ ] **Step 7: Commit**

```bash
git -C /Users/teropihlaja/dev/electrolux_ac add custom_components/ tests/test_hub.py
git -C /Users/teropihlaja/dev/electrolux_ac commit -m "feat: add alerts sensor and warning log"
```

---

## Task 5: Push and deploy

- [ ] **Step 1: Push to GitHub**

```bash
git -C /Users/teropihlaja/dev/electrolux_ac push github main
```

- [ ] **Step 2: Pull and restart on server**

```bash
ssh crazyguy@home.crazyguy.info "cd /home/crazyguy/homeassistant/electrolux_ac && git pull && cd /home/crazyguy/homeassistant && docker compose restart homeassistant"
```

- [ ] **Step 3: Verify startup logs**

```bash
ssh crazyguy@home.crazyguy.info "sleep 70 && cd /home/crazyguy/homeassistant && docker compose logs --since=2m homeassistant 2>&1 | grep 'custom_components.electrolux_ac\b' | grep -v 'pyelectrolux\|WebSocket\|OneApp\|Gigya\|aiohttp' | tail -10"
```

Expected: no errors, component loads, temperature sensor creates.
