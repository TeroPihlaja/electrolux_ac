# Migrate to the Official Electrolux Developer SDK Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace `pyelectroluxocp` (archived upstream) with the officially maintained `electrolux-group-developer-sdk`, keeping push-based updates (SSE instead of WebSocket) and fixing the reauth-detection gap that caused the 2026-07-28 outage.

**Architecture:** `hub.py` and a new `coordinator.py` wrap `electrolux_group_developer_sdk`'s `ApplianceClient`/`TokenManager`. `Appliance` keeps exposing `._states` (flat dict) and `.capabilities` (dict) so `climate.py`/`sensor.py` need only a narrow case-insensitivity fix, not a rewrite. `config_flow.py` collects `api_key`/`access_token`/`refresh_token` instead of `email`/`password`/`country_code`, and gains a reauth step.

**Tech Stack:** Python 3.14, Home Assistant 2026.6.1, `electrolux-group-developer-sdk` 0.6.1 (PyPI), `pytest` + `pytest-asyncio`, `pytest-homeassistant-custom-component`.

## Global Constraints

- Spec: `docs/superpowers/specs/2026-08-04-official-sdk-migration-design.md`
- Breaking change is acceptable — sole current user, no migration shim for old config entries.
- `climate.py`/`sensor.py` get exactly one change each: case-insensitive string comparisons. No other changes to those two files.
- `iot_class` in `manifest.json` stays `cloud_push`.
- Every task's tests must pass via `.venv/bin/pytest tests/ -v` before moving to the next task.
- The SDK is imported as `electrolux_group_developer_sdk` (PyPI distribution name `electrolux-group-developer-sdk`); exact import paths are given per-task below — don't guess alternates.
- `main` is what the live HA server tracks (see `CLAUDE.md`'s deploy notes). This entire plan runs on a feature branch — nothing merges to `main` until Task 10 Step 6's manual end-to-end verification passes against the real AC.

---

### Task 0: Create the feature branch

**Files:** none — git operation only.

- [ ] **Step 1: Create and switch to the feature branch**

Run: `git checkout -b feat/official-sdk-migration`
Expected: `Switched to a new branch 'feat/official-sdk-migration'`

All subsequent tasks' commits happen on this branch.

---

### Task 1: Add SDK dependency and new config constants

**Files:**
- Modify: `custom_components/electrolux_ac/const.py`
- Modify: `requirements_test.txt`
- Modify: `.venv` (install SDK)

**Interfaces:**
- Produces: `CONF_API_KEY = "api_key"`, `CONF_ACCESS_TOKEN = "access_token"`, `CONF_REFRESH_TOKEN = "refresh_token"` (used by every later task)

- [ ] **Step 1: Install the SDK in the local venv**

Run: `.venv/bin/pip install electrolux-group-developer-sdk==0.6.1`
Expected: `Successfully installed electrolux-group-developer-sdk-0.6.1` (plus `pydantic`, `pyjwt`, `tzdata` if not already present)

- [ ] **Step 2: Add it to `requirements_test.txt`**

Replace the file's contents with:

```
pytest
pytest-asyncio
pytest-homeassistant-custom-component
electrolux-group-developer-sdk==0.6.1
```

- [ ] **Step 3: Update `const.py`**

Replace the full contents of `custom_components/electrolux_ac/const.py` with:

```python
DOMAIN = "electrolux_ac"
TARGET_TEMPERATURE_STEP = 1
CONF_API_KEY = "api_key"
CONF_ACCESS_TOKEN = "access_token"
CONF_REFRESH_TOKEN = "refresh_token"
```

- [ ] **Step 4: Run the full test suite to confirm nothing broke**

Run: `.venv/bin/pytest tests/ -v`
Expected: FAIL — `config_flow.py` and `__init__.py` still do `from .const import DOMAIN, CONF_COUNTRY_CODE`, which no longer exists, so both modules fail to import (collection errors in `test_config_flow.py`). `hub.py` doesn't import `CONF_COUNTRY_CODE` at all (it took `country_code` as a plain constructor parameter instead), so `test_hub.py` still collects fine at this point.

This is expected. `config_flow.py`'s import is fixed in Task 7, `__init__.py`'s in Task 8. Do not commit yet — continue directly to Task 2's first step.

---

### Task 2: Rewrite `Hub.connect`/`disconnect` for the new client

**Files:**
- Modify: `custom_components/electrolux_ac/hub.py:1-65` (imports, class `Hub` through `connect`/`disconnect`)
- Test: `tests/test_hub.py:1-28` (replace `test_hub_passes_country_code_to_api`/`test_hub_defaults_country_code_fi`)

**Interfaces:**
- Consumes: `electrolux_group_developer_sdk.auth.token_manager.TokenManager(access_token, refresh_token, api_key, on_token_update=None)`, `electrolux_group_developer_sdk.client.appliance_client.ApplianceClient(token_manager)`
- Produces: `Hub(hass, entry)`, `Hub.connect()`, `Hub.disconnect()`, `Hub._client` (an `ApplianceClient`), `Hub.online` (bool)

- [ ] **Step 1: Write the failing tests**

Replace `tests/test_hub.py` lines 1-28 (the `make_hub` helper and the two country-code tests) with:

```python
from unittest.mock import MagicMock, patch, AsyncMock
import pytest
from custom_components.electrolux_ac.hub import Hub, Appliance


def make_entry(data=None):
    entry = MagicMock()
    entry.data = data or {
        "api_key": "test_api_key",
        "access_token": "test_access_token",
        "refresh_token": "test_refresh_token",
    }
    entry.entry_id = "test_entry_id"
    return entry


def make_hub(hass=None, entry=None):
    hass = hass or MagicMock()
    entry = entry or make_entry()
    return Hub(hass, entry)


@pytest.mark.asyncio
async def test_connect_builds_client_with_entry_credentials():
    entry = make_entry()
    hub = make_hub(entry=entry)
    with patch("custom_components.electrolux_ac.hub.TokenManager") as mock_tm_cls, \
         patch("custom_components.electrolux_ac.hub.ApplianceClient") as mock_client_cls:
        await hub.connect()
    _, kwargs = mock_tm_cls.call_args
    assert kwargs["access_token"] == "test_access_token"
    assert kwargs["refresh_token"] == "test_refresh_token"
    assert kwargs["api_key"] == "test_api_key"
    mock_client_cls.assert_called_once_with(token_manager=mock_tm_cls.return_value)
    assert hub.online is True


@pytest.mark.asyncio
async def test_connect_persists_rotated_tokens_via_on_token_update():
    entry = make_entry()
    hass = MagicMock()
    hub = make_hub(hass=hass, entry=entry)
    with patch("custom_components.electrolux_ac.hub.TokenManager") as mock_tm_cls, \
         patch("custom_components.electrolux_ac.hub.ApplianceClient"):
        await hub.connect()
    _, kwargs = mock_tm_cls.call_args
    on_token_update = kwargs["on_token_update"]
    on_token_update("new_access", "new_refresh", "test_api_key")
    hass.config_entries.async_update_entry.assert_called_once_with(
        entry,
        data={
            "api_key": "test_api_key",
            "access_token": "new_access",
            "refresh_token": "new_refresh",
        },
    )
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `.venv/bin/pytest tests/test_hub.py -v -k test_connect_`
Expected: FAIL (collection error) — `hub.py` doesn't import `TokenManager`/`ApplianceClient` yet and `Hub.__init__` doesn't accept `(hass, entry)`.

- [ ] **Step 3: Rewrite the top of `hub.py`**

Replace `custom_components/electrolux_ac/hub.py` lines 1-65 (everything from the module docstring through the end of `Hub.disconnect`) with:

```python
"""A demonstration 'hub' that connects several devices."""
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
    def __init__(self, hass: HomeAssistant, entry: ConfigEntry):
        _LOGGER.debug("Creating Electrolux hub for entry %s", entry.entry_id)

        self._hass = hass
        self._entry = entry
        self._id = entry.entry_id
        self._client: ApplianceClient | None = None
        self.appliances = None
        self.online = False
        self._update_task = None

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
            self._update_task = None
        self._client = None
        self.online = False
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `.venv/bin/pytest tests/test_hub.py -v -k test_connect_`
Expected: 2 PASS

- [ ] **Step 5: Commit**

```bash
git add custom_components/electrolux_ac/hub.py custom_components/electrolux_ac/const.py requirements_test.txt tests/test_hub.py
git commit -m "feat: rewrite Hub.connect/disconnect for electrolux-group-developer-sdk"
```

---

### Task 3: Rewrite `discover_appliances` and appliance data mapping

**Files:**
- Modify: `custom_components/electrolux_ac/hub.py` (add `discover_appliances`, `_apply_appliance_data`, rewrite `Appliance.__init__`)
- Test: `tests/test_hub.py`

**Interfaces:**
- Consumes: `ApplianceClient.get_appliance_data() -> list[ApplianceData]` where each `ApplianceData` has `.appliance.applianceId: str`, `.appliance.applianceName: str`, `.details.capabilities: dict`, `.details.applianceInfo.model/.brand/.deviceType: str`, `.state.properties: dict` (with `.get("reported", {})`), `.state.connectionState: str`
- Produces: `Hub.discover_appliances()`, `Hub.appliances: list[Appliance]`, `Appliance(applianceid, name, hub)` (now a plain constructor with no background tasks — `capabilities`/`_states`/`appliance_info`/`_connected` are set by the caller, not fetched internally)

This task removes `Appliance.update_appliance_info()` and `Appliance.watch_for_state_updates()` entirely: `get_appliance_data()` already returns capabilities + state + info in one call per appliance, so there's no longer an async race to guard against between construction and data arriving. `Appliance.__init__` no longer spawns any background tasks.

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_hub.py` (after the two tests from Task 2):

```python
def _make_appliance_data(appliance_id="test_id", name="Test AC", connection_state="connected"):
    from unittest.mock import MagicMock
    data = MagicMock()
    data.appliance.applianceId = appliance_id
    data.appliance.applianceName = name
    data.details.capabilities = {"targetTemperatureC": {"min": 16, "max": 32}}
    data.details.applianceInfo.model = "COMFORT600"
    data.details.applianceInfo.brand = "ELECTROLUX"
    data.details.applianceInfo.deviceType = "PORTABLE_AIR_CONDITIONER"
    data.state.properties = {"reported": {"mode": "COOL", "ambientTemperatureC": 22}}
    data.state.connectionState = connection_state
    return data


@pytest.mark.asyncio
async def test_discover_appliances_builds_appliance_from_sdk_data():
    hub = make_hub()
    hub.online = True
    hub._client = AsyncMock()
    hub._client.get_appliance_data.return_value = [_make_appliance_data()]
    with patch("custom_components.electrolux_ac.hub.asyncio.ensure_future", side_effect=lambda c: c.close()):
        await hub.discover_appliances()
    assert len(hub.appliances) == 1
    appliance = hub.appliances[0]
    assert appliance.appliance_id == "test_id"
    assert appliance.name == "Test AC"
    assert appliance.capabilities == {"targetTemperatureC": {"min": 16, "max": 32}}
    assert appliance._states == {"mode": "COOL", "ambientTemperatureC": 22}
    assert appliance._connected is True
    assert appliance.appliance_info == {
        "model": "COMFORT600", "brand": "ELECTROLUX", "deviceType": "PORTABLE_AIR_CONDITIONER",
    }


@pytest.mark.asyncio
async def test_discover_appliances_marks_disconnected_appliance():
    hub = make_hub()
    hub.online = True
    hub._client = AsyncMock()
    hub._client.get_appliance_data.return_value = [_make_appliance_data(connection_state="disconnected")]
    with patch("custom_components.electrolux_ac.hub.asyncio.ensure_future", side_effect=lambda c: c.close()):
        await hub.discover_appliances()
    assert hub.appliances[0]._connected is False


@pytest.mark.asyncio
async def test_discover_appliances_handles_missing_details_and_state():
    from unittest.mock import MagicMock
    hub = make_hub()
    hub.online = True
    hub._client = AsyncMock()
    data = MagicMock()
    data.appliance.applianceId = "id1"
    data.appliance.applianceName = "Test AC"
    data.details = None
    data.state = None
    hub._client.get_appliance_data.return_value = [data]
    with patch("custom_components.electrolux_ac.hub.asyncio.ensure_future", side_effect=lambda c: c.close()):
        await hub.discover_appliances()
    appliance = hub.appliances[0]
    assert appliance.capabilities == {}
    assert appliance._states == {}
    assert appliance._connected is False
    assert appliance.appliance_info is None
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `.venv/bin/pytest tests/test_hub.py -v -k discover_appliances`
Expected: FAIL — `Hub` has no `discover_appliances` method yet (old one was removed in Task 2's rewrite of lines 1-65; the rest of the file — old `discover_appliances`, `refresh_connection_state`, `test_connection`, `update_loop`, and the `Appliance` class — is still the pre-migration code below line 65 and references `self._client.get_appliances_list`, which no longer exists on `ApplianceClient`).

- [ ] **Step 3: Replace the rest of `hub.py`**

Replace everything in `custom_components/electrolux_ac/hub.py` from the old `async def discover_appliances(self):` line through the end of the file with:

```python
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
        appliance.capabilities = data.details.capabilities if data.details else {}
        appliance._sdk_state = data.state
        appliance._states = (
            data.state.properties.get("reported", {}) if data.state else {}
        )
        appliance._connected = bool(
            data.state and data.state.connectionState.lower() == "connected"
        )
        appliance.appliance_info = (
            {
                "model": data.details.applianceInfo.model,
                "brand": data.details.applianceInfo.brand,
                "deviceType": data.details.applianceInfo.deviceType,
            }
            if data.details
            else None
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
        STATE_MAX = 5
        for i in range(STATE_MAX):
            if self._states and self.capabilities:
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
        await self.hub._client.send_command(self._id, {command: value})
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
```

Note the unknown-capabilities warning loop from the old `update_appliance_info` (logging unsupported capability keys) is intentionally dropped here — it required a stable `capabilities` snapshot at construction time, which no longer exists as a discrete step. Capability keys are now recomputed on every `full_refresh`/SSE event, so this check moves to Task 4 as part of `_apply_appliance_data` if kept. **Do not add it back** — the spec doesn't require it, and re-checking on every SSE event would spam the log every time an unrelated property changes. It's dropped, not deferred; do not add a TODO for it.

- [ ] **Step 4: Run the tests to verify they pass**

Run: `.venv/bin/pytest tests/test_hub.py -v`
Expected: all tests in the file PASS. Some old tests (e.g. `test_refresh_connection_state_updates_connected`, `test_update_appliance_info_handles_empty_info`) reference methods that no longer exist (`refresh_connection_state`, `update_appliance_info`) — delete those specific old test functions now, since the methods they test were intentionally removed in this task. Keep `test_appliance_online_false_when_not_connected`, `test_appliance_online_true_when_connected`, `test_state_update_sets_connected` but update them to call `state_update_callback` with the new event-dict shape (see Task 4).

- [ ] **Step 5: Commit**

```bash
git add custom_components/electrolux_ac/hub.py tests/test_hub.py
git commit -m "feat: rewrite discover_appliances to use ApplianceClient.get_appliance_data"
```

---

### Task 4: SSE event handling and connection state

**Files:**
- Modify: `tests/test_hub.py` (fix the tests flagged in Task 3 Step 4, using the real `apply_sse_update`/`ApplianceState` shape)

**Interfaces:**
- Consumes: `electrolux_group_developer_sdk.client.dto.appliance_state.ApplianceState(applianceId, connectionState, status, properties)`, `electrolux_group_developer_sdk.client.appliance_client.apply_sse_update(state, event) -> ApplianceState`
- Produces: nothing new — this task verifies `Appliance.state_update_callback` (already written in Task 3) against the SDK's real objects instead of mocks

- [ ] **Step 1: Write the failing tests**

Replace the old `test_appliance_online_false_when_not_connected`, `test_appliance_online_true_when_connected`, `test_state_update_sets_connected`, `test_state_update_logs_warning_for_non_empty_alerts`, `test_state_update_no_warning_when_alerts_empty` in `tests/test_hub.py` with:

```python
from electrolux_group_developer_sdk.client.dto.appliance_state import ApplianceState


def make_appliance(connected=True):
    hub = MagicMock()
    hub._client = MagicMock()
    appliance = Appliance("test_id", "Test AC", hub)
    appliance._sdk_state = ApplianceState(
        applianceId="test_id",
        connectionState="connected" if connected else "disconnected",
        status="enabled",
        properties={"reported": {"mode": "COOL"}},
    )
    appliance._states = appliance._sdk_state.properties["reported"]
    appliance._connected = connected
    return appliance


def test_appliance_online_false_when_not_connected():
    appliance = make_appliance(connected=False)
    assert appliance.online is False


def test_appliance_online_true_when_connected():
    appliance = make_appliance(connected=True)
    assert appliance.online is True


def test_state_update_callback_applies_property_event():
    appliance = make_appliance(connected=True)
    appliance._callbacks = set()
    appliance.state_update_callback({"property": "mode", "value": "DRY"})
    assert appliance._states["mode"] == "DRY"


def test_state_update_callback_updates_connection_state():
    appliance = make_appliance(connected=True)
    appliance._callbacks = set()
    appliance.state_update_callback({"property": "connectionState", "value": "disconnected"})
    assert appliance._connected is False


def test_state_update_callback_publishes_to_registered_callbacks():
    appliance = make_appliance(connected=True)
    appliance._callbacks = set()
    callback = MagicMock()
    appliance.register_callback(callback)
    appliance.state_update_callback({"property": "mode", "value": "DRY"})
    callback.assert_called_once()


def test_state_update_callback_ignored_before_initial_state():
    appliance = make_appliance(connected=True)
    appliance._sdk_state = None
    appliance._callbacks = set()
    callback = MagicMock()
    appliance.register_callback(callback)
    appliance.state_update_callback({"property": "mode", "value": "DRY"})
    callback.assert_not_called()


def test_state_update_logs_warning_for_non_empty_alerts(caplog):
    appliance = make_appliance(connected=True)
    appliance._sdk_state = ApplianceState(
        applianceId="test_id", connectionState="connected", status="enabled",
        properties={"reported": {"alerts": []}},
    )
    appliance._callbacks = set()
    import logging
    with caplog.at_level(logging.WARNING, logger="custom_components.electrolux_ac.hub"):
        appliance.state_update_callback({"property": "alerts", "value": ["DRAIN_PAN_FULL"]})
    assert any("DRAIN_PAN_FULL" in r.message for r in caplog.records)


def test_state_update_no_warning_when_alerts_empty(caplog):
    appliance = make_appliance(connected=True)
    appliance._sdk_state = ApplianceState(
        applianceId="test_id", connectionState="connected", status="enabled",
        properties={"reported": {"alerts": ["DRAIN_PAN_FULL"]}},
    )
    appliance._callbacks = set()
    import logging
    with caplog.at_level(logging.WARNING, logger="custom_components.electrolux_ac.hub"):
        appliance.state_update_callback({"property": "alerts", "value": []})
    assert not any("alert" in r.message.lower() for r in caplog.records)
```

Also delete the now-obsolete `make_appliance` usages that patched `asyncio.ensure_future` in `__init__` (no longer spawns tasks) — search `tests/test_hub.py` for `patch("custom_components.electrolux_ac.hub.asyncio.ensure_future", side_effect=lambda c: c.close())` used around `Appliance(...)` construction (not around `discover_appliances`) and remove that `with` wrapper, calling `Appliance(...)` directly instead.

- [ ] **Step 2: Run the tests to verify they fail**

Run: `.venv/bin/pytest tests/test_hub.py -v`
Expected: FAIL on the new/changed tests — `apply_sse_update` import works (real SDK function), but `Appliance.state_update_callback` was already written correctly in Task 3, so most should already pass. If any fail, it's because Task 3's `state_update_callback` used `self._states.get("alerts")` read straight after reassignment, which is correct — if this step reports failures, re-check for typos against Task 3 Step 3's exact code before changing behavior.

- [ ] **Step 3: Confirm all pass**

Run: `.venv/bin/pytest tests/test_hub.py -v`
Expected: all PASS. (This task is primarily about testing Task 3's code against real SDK objects instead of `MagicMock()`, so no production code should need changes here. If a test fails, fix `hub.py`, not the test.)

- [ ] **Step 4: Commit**

```bash
git add tests/test_hub.py
git commit -m "test: exercise Appliance.state_update_callback against real ApplianceState/apply_sse_update"
```

---

### Task 5: `Appliance.execute_command` via `send_command`

**Files:**
- Modify: `tests/test_hub.py`

**Interfaces:**
- Consumes: `ApplianceClient.send_command(appliance_id: str, commands: dict) -> Any` (already wired in Task 3's `execute_command`)

- [ ] **Step 1: Write the failing test**

Add to `tests/test_hub.py`:

```python
@pytest.mark.asyncio
async def test_execute_command_calls_send_command():
    appliance = make_appliance()
    appliance._callbacks = set()
    appliance.hub._client.send_command = AsyncMock()
    await appliance.execute_command("mode", "cool")
    appliance.hub._client.send_command.assert_called_once_with("test_id", {"mode": "cool"})


@pytest.mark.asyncio
async def test_execute_command_propagates_api_exception():
    appliance = make_appliance()
    appliance._callbacks = set()
    appliance.hub._client.send_command = AsyncMock(side_effect=RuntimeError("API error"))
    with pytest.raises(RuntimeError, match="API error"):
        await appliance.execute_command("mode", "cool")
```

(Remove the old `test_execute_command_propagates_api_exception` that referenced `execute_appliance_command` if it wasn't already removed in Task 3/4.)

- [ ] **Step 2: Run to verify current behavior**

Run: `.venv/bin/pytest tests/test_hub.py -v -k execute_command`
Expected: both PASS immediately — `execute_command` was already written to call `send_command` in Task 3. This task exists to lock that behavior in with an explicit test, since Task 3's test suite didn't cover it directly.

- [ ] **Step 3: Commit**

```bash
git add tests/test_hub.py
git commit -m "test: cover Appliance.execute_command against send_command"
```

---

### Task 6: New `coordinator.py` — safety-net poll and reauth trigger

**Files:**
- Create: `custom_components/electrolux_ac/coordinator.py`
- Test: `tests/test_coordinator.py`

**Interfaces:**
- Consumes: `Hub.test_connection()` (raises `BadCredentialsException` on dead credentials, from Task 3), `Hub.full_refresh()` (from Task 3)
- Produces: `ElectroluxSafetyNetCoordinator(hass, entry, hub)`, used by `__init__.py` in Task 9

- [ ] **Step 1: Write the failing tests**

Create `tests/test_coordinator.py`:

```python
from unittest.mock import MagicMock, AsyncMock
import pytest
from homeassistant.exceptions import ConfigEntryAuthFailed
from electrolux_group_developer_sdk.client.bad_credentials_exception import BadCredentialsException
from custom_components.electrolux_ac.coordinator import ElectroluxSafetyNetCoordinator


def make_coordinator(hub=None):
    hass = MagicMock()
    entry = MagicMock()
    hub = hub or MagicMock()
    return ElectroluxSafetyNetCoordinator(hass, entry, hub)


@pytest.mark.asyncio
async def test_update_data_raises_config_entry_auth_failed_on_bad_credentials():
    hub = MagicMock()
    hub.test_connection = AsyncMock(side_effect=BadCredentialsException("dead token"))
    coordinator = make_coordinator(hub)
    with pytest.raises(ConfigEntryAuthFailed):
        await coordinator._async_update_data()


@pytest.mark.asyncio
async def test_update_data_calls_full_refresh_after_successful_connection_test():
    hub = MagicMock()
    hub.test_connection = AsyncMock()
    hub.full_refresh = AsyncMock()
    coordinator = make_coordinator(hub)
    await coordinator._async_update_data()
    hub.full_refresh.assert_called_once()


@pytest.mark.asyncio
async def test_update_data_does_not_call_full_refresh_on_bad_credentials():
    hub = MagicMock()
    hub.test_connection = AsyncMock(side_effect=BadCredentialsException("dead token"))
    hub.full_refresh = AsyncMock()
    coordinator = make_coordinator(hub)
    with pytest.raises(ConfigEntryAuthFailed):
        await coordinator._async_update_data()
    hub.full_refresh.assert_not_called()
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `.venv/bin/pytest tests/test_coordinator.py -v`
Expected: FAIL — `custom_components/electrolux_ac/coordinator.py` doesn't exist yet.

- [ ] **Step 3: Write `coordinator.py`**

Create `custom_components/electrolux_ac/coordinator.py`:

```python
"""Periodic safety-net poll: verifies credentials and refreshes state as a fallback to the SSE stream."""
from __future__ import annotations

from datetime import timedelta
import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

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
        await self._hub.full_refresh()
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `.venv/bin/pytest tests/test_coordinator.py -v`
Expected: all 3 PASS

- [ ] **Step 5: Commit**

```bash
git add custom_components/electrolux_ac/coordinator.py tests/test_coordinator.py
git commit -m "feat: add ElectroluxSafetyNetCoordinator for reauth detection"
```

---

### Task 7: Rewrite `config_flow.py` — new fields, validation, reauth

**Files:**
- Modify: `custom_components/electrolux_ac/config_flow.py` (full rewrite)
- Modify: `custom_components/electrolux_ac/strings.json`
- Modify: `custom_components/electrolux_ac/translations/en.json`
- Test: `tests/test_config_flow.py`

**Interfaces:**
- Consumes: `TokenManager(access_token, refresh_token, api_key)`, `ApplianceClient(token_manager).test_connection()`, `ApplianceClient(token_manager).get_user_email() -> Email` (with `.email: str`), `BadCredentialsException`
- Produces: `ConfigFlow` with `async_step_user`, `async_step_reauth`, `async_step_reauth_confirm`; `InvalidAuth`, `CannotConnect` (unchanged names, so Task 9's `__init__.py` and existing error-key wiring keep working)

- [ ] **Step 1: Write the failing tests**

Replace `tests/test_config_flow.py` with:

```python
import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from electrolux_group_developer_sdk.client.bad_credentials_exception import BadCredentialsException
from custom_components.electrolux_ac.config_flow import ConfigFlow, InvalidAuth, CannotConnect, validate_input


def _flow():
    flow = ConfigFlow()
    flow.hass = MagicMock()
    flow.context = {}
    return flow


@pytest.mark.asyncio
async def test_config_flow_maps_invalid_auth_to_invalid_auth_error_key():
    flow = _flow()
    with patch(
        "custom_components.electrolux_ac.config_flow.validate_input",
        side_effect=InvalidAuth,
    ):
        result = await flow.async_step_user(
            {"api_key": "k", "access_token": "a", "refresh_token": "r"}
        )
    assert result["errors"]["base"] == "invalid_auth"


@pytest.mark.asyncio
async def test_config_flow_maps_cannot_connect_to_cannot_connect_error_key():
    flow = _flow()
    with patch(
        "custom_components.electrolux_ac.config_flow.validate_input",
        side_effect=CannotConnect,
    ):
        result = await flow.async_step_user(
            {"api_key": "k", "access_token": "a", "refresh_token": "r"}
        )
    assert result["errors"]["base"] == "cannot_connect"


@pytest.mark.asyncio
async def test_validate_input_raises_invalid_auth_on_bad_credentials():
    with patch("custom_components.electrolux_ac.config_flow.ApplianceClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.test_connection = AsyncMock(side_effect=BadCredentialsException("bad"))
        mock_client_cls.return_value = mock_client
        with pytest.raises(InvalidAuth):
            await validate_input(MagicMock(), {"api_key": "k", "access_token": "a", "refresh_token": "r"})


@pytest.mark.asyncio
async def test_validate_input_returns_email_as_title():
    with patch("custom_components.electrolux_ac.config_flow.ApplianceClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.test_connection = AsyncMock()
        mock_email = MagicMock()
        mock_email.email = "user@example.com"
        mock_client.get_user_email = AsyncMock(return_value=mock_email)
        mock_client_cls.return_value = mock_client
        result = await validate_input(MagicMock(), {"api_key": "k", "access_token": "a", "refresh_token": "r"})
    assert result["title"] == "user@example.com"


@pytest.mark.asyncio
async def test_reauth_confirm_updates_entry_on_success():
    flow = _flow()
    reauth_entry = MagicMock()
    flow._get_reauth_entry = MagicMock(return_value=reauth_entry)
    flow.async_update_reload_and_abort = MagicMock(return_value={"type": "abort", "reason": "reauth_successful"})
    with patch(
        "custom_components.electrolux_ac.config_flow.validate_input",
        return_value={"title": "user@example.com"},
    ):
        result = await flow.async_step_reauth_confirm(
            {"api_key": "new_k", "access_token": "new_a", "refresh_token": "new_r"}
        )
    flow.async_update_reload_and_abort.assert_called_once_with(
        reauth_entry,
        data_updates={"api_key": "new_k", "access_token": "new_a", "refresh_token": "new_r"},
    )
    assert result["reason"] == "reauth_successful"


@pytest.mark.asyncio
async def test_reauth_confirm_shows_error_on_invalid_auth():
    flow = _flow()
    with patch(
        "custom_components.electrolux_ac.config_flow.validate_input",
        side_effect=InvalidAuth,
    ):
        result = await flow.async_step_reauth_confirm(
            {"api_key": "k", "access_token": "a", "refresh_token": "r"}
        )
    assert result["errors"]["base"] == "invalid_auth"
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `.venv/bin/pytest tests/test_config_flow.py -v`
Expected: FAIL — `config_flow.py` still has the old email/password fields and no reauth steps.

- [ ] **Step 3: Rewrite `config_flow.py`**

Replace the full contents of `custom_components/electrolux_ac/config_flow.py` with:

```python
"""Config flow for Electrolux AC integration."""
from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant import config_entries, exceptions
from homeassistant.core import HomeAssistant

from electrolux_group_developer_sdk.auth.token_manager import TokenManager
from electrolux_group_developer_sdk.client.appliance_client import ApplianceClient
from electrolux_group_developer_sdk.client.bad_credentials_exception import BadCredentialsException

from .const import DOMAIN, CONF_API_KEY, CONF_ACCESS_TOKEN, CONF_REFRESH_TOKEN

_LOGGER = logging.getLogger(__name__)

_SCHEMA = vol.Schema({
    vol.Required(CONF_API_KEY): str,
    vol.Required(CONF_ACCESS_TOKEN): str,
    vol.Required(CONF_REFRESH_TOKEN): str,
})


async def validate_input(hass: HomeAssistant, data: dict) -> dict[str, Any]:
    token_manager = TokenManager(
        access_token=data[CONF_ACCESS_TOKEN],
        refresh_token=data[CONF_REFRESH_TOKEN],
        api_key=data[CONF_API_KEY],
    )
    client = ApplianceClient(token_manager=token_manager)
    try:
        await client.test_connection()
        email = await client.get_user_email()
    except BadCredentialsException as ex:
        raise InvalidAuth from ex
    except Exception as ex:
        raise CannotConnect from ex

    return {"title": email.email}


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Electrolux AC."""

    VERSION = 2

    async def async_step_user(self, user_input=None):
        """Handle the initial step."""
        errors = {}
        if user_input is not None:
            try:
                info = await validate_input(self.hass, user_input)
                return self.async_create_entry(title=info["title"], data=user_input)
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"

        return self.async_show_form(
            step_id="user", data_schema=_SCHEMA, errors=errors
        )

    async def async_step_reauth(self, entry_data: dict[str, Any]):
        """Handle reauthorization triggered by ConfigEntryAuthFailed."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(self, user_input=None):
        """Ask the user for a fresh api_key/access_token/refresh_token."""
        errors = {}
        if user_input is not None:
            try:
                await validate_input(self.hass, user_input)
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                reauth_entry = self._get_reauth_entry()
                return self.async_update_reload_and_abort(
                    reauth_entry, data_updates=user_input
                )

        return self.async_show_form(
            step_id="reauth_confirm", data_schema=_SCHEMA, errors=errors
        )


class CannotConnect(exceptions.HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidAuth(exceptions.HomeAssistantError):
    """Error to indicate there is an invalid credentials."""
```

- [ ] **Step 4: Update `strings.json`**

Replace the full contents of `custom_components/electrolux_ac/strings.json` with:

```json
{
  "config": {
    "step": {
      "user": {
        "title": "Login information",
        "description": "Generate an API key, access token, and refresh token at https://developer.electrolux.one/ (log in with your existing Electrolux account, create an API key, then generate a token pair).",
        "data": {
          "api_key": "API key",
          "access_token": "Access token",
          "refresh_token": "Refresh token"
        }
      },
      "reauth_confirm": {
        "title": "Reauthenticate Electrolux AC",
        "description": "Your Electrolux credentials are no longer valid. Generate a fresh API key, access token, and refresh token at https://developer.electrolux.one/ and enter them below.",
        "data": {
          "api_key": "API key",
          "access_token": "Access token",
          "refresh_token": "Refresh token"
        }
      }
    },
    "error": {
      "cannot_connect": "[%key:common::config_flow::error::cannot_connect%]",
      "invalid_auth": "[%key:common::config_flow::error::invalid_auth%]",
      "unknown": "[%key:common::config_flow::error::unknown%]"
    },
    "abort": {
      "already_configured": "[%key:common::config_flow::abort::already_configured_device%]",
      "reauth_successful": "[%key:common::config_flow::abort::reauth_successful%]"
    }
  }
}
```

- [ ] **Step 5: Update `translations/en.json`**

Replace `custom_components/electrolux_ac/translations/en.json` with the identical contents as `strings.json` from Step 4 (this repo keeps them in sync manually — confirm by diffing the two files after this step; they should be byte-identical).

- [ ] **Step 6: Run the tests to verify they pass**

Run: `.venv/bin/pytest tests/test_config_flow.py -v`
Expected: all 6 PASS

- [ ] **Step 7: Commit**

```bash
git add custom_components/electrolux_ac/config_flow.py custom_components/electrolux_ac/strings.json custom_components/electrolux_ac/translations/en.json tests/test_config_flow.py
git commit -m "feat: rewrite config flow for api_key/access_token/refresh_token, add reauth step"
```

---

### Task 8: Wire `__init__.py` — new Hub construction, coordinator, auth-failure handling

**Files:**
- Modify: `custom_components/electrolux_ac/__init__.py` (full rewrite)

**Interfaces:**
- Consumes: `Hub(hass, entry)` (Task 2), `Hub.discover_appliances()` (Task 3), `ElectroluxSafetyNetCoordinator(hass, entry, hub)` (Task 6), `BadCredentialsException`, `electrolux_group_developer_sdk.client.client_exception.ApplianceClientException`

- [ ] **Step 1: Rewrite `__init__.py`**

There's no existing `test_init.py` in this repo (integration setup isn't unit-tested at this layer today — consistent with existing convention). Replace the full contents of `custom_components/electrolux_ac/__init__.py` with:

```python
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
```

Note the `electrolux_hub.coordinator = coordinator` assignment above: `Hub` doesn't declare a `coordinator` attribute in `__init__` — Python allows this dynamically, but to keep `Hub`'s public surface explicit, add `self.coordinator = None` to `Hub.__init__` in `hub.py` (right after `self._update_task = None`) in this same step.

- [ ] **Step 2: Add the `coordinator` attribute to `Hub.__init__`**

In `custom_components/electrolux_ac/hub.py`, in `Hub.__init__`, change:

```python
        self._update_task = None
```

to:

```python
        self._update_task = None
        self.coordinator = None
```

- [ ] **Step 3: Run the full test suite**

Run: `.venv/bin/pytest tests/ -v`
Expected: all tests PASS (this task has no dedicated unit tests, matching existing convention — verify by running the full suite and confirming no regressions).

- [ ] **Step 4: Commit**

```bash
git add custom_components/electrolux_ac/__init__.py custom_components/electrolux_ac/hub.py
git commit -m "feat: wire Hub construction, safety-net coordinator, and auth-failure handling in async_setup_entry"
```

---

### Task 9: Case-insensitive state comparisons in `climate.py` and `sensor.py`

**Files:**
- Modify: `custom_components/electrolux_ac/climate.py` (lines 50, 83-86, 125-134, 142-151, 174-179, 187-190, 194)
- Modify: `custom_components/electrolux_ac/sensor.py` (line 135)
- Test: `tests/test_climate.py`, `tests/test_climate_preset.py`, `tests/test_sensor.py`

**Interfaces:**
- No interface changes — same method signatures, same return values, just tolerant of uppercase input in addition to lowercase.

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_climate.py`:

```python
def test_temperature_unit_is_fahrenheit_when_representation_is_uppercase(mock_appliance):
    mock_appliance._states = {"temperatureRepresentation": "FAHRENHEIT"}
    mock_appliance.appliance_info = {"model": "comfort600", "brand": "electrolux"}
    mock_appliance.capabilities = {}
    climate = ElectroluxClimate(mock_appliance)
    assert climate.temperature_unit == UnitOfTemperature.FAHRENHEIT


def test_hvac_mode_is_cool_when_mode_uppercase(mock_appliance):
    climate = _make_climate(mock_appliance)
    mock_appliance._states["applianceState"] = "RUNNING"
    mock_appliance._states["mode"] = "COOL"
    assert climate.hvac_mode == HVACMode.COOL
```

Add to `tests/test_climate_preset.py`:

```python
def test_preset_mode_is_sleep_when_sleep_on_uppercase(mock_appliance):
    climate = _make_climate(mock_appliance)
    mock_appliance._states["sleepMode"] = "ON"
    assert climate.preset_mode == PRESET_SLEEP
```

Add to `tests/test_sensor.py`:

```python
def test_temperature_sensor_unit_is_fahrenheit_when_representation_uppercase(mock_appliance):
    from custom_components.electrolux_ac.sensor import TemperatureSensor
    from homeassistant.const import UnitOfTemperature
    mock_appliance._states = {"temperatureRepresentation": "FAHRENHEIT"}
    sensor = TemperatureSensor(mock_appliance)
    assert sensor.native_unit_of_measurement == UnitOfTemperature.FAHRENHEIT
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `.venv/bin/pytest tests/test_climate.py tests/test_climate_preset.py tests/test_sensor.py -v -k uppercase`
Expected: FAIL — all 3 new tests fail because the comparisons are exact-lowercase today.

- [ ] **Step 3: Make `climate.py` comparisons case-insensitive**

In `custom_components/electrolux_ac/climate.py`:

Change line 83-86 from:

```python
    if self._appliance._states.get('temperatureRepresentation') == 'fahrenheit':
      self._attr_unit_of_measurement = UnitOfTemperature.FAHRENHEIT
    else:
      self._attr_unit_of_measurement = UnitOfTemperature.CELSIUS
```

to:

```python
    if (self._appliance._states.get('temperatureRepresentation') or '').lower() == 'fahrenheit':
      self._attr_unit_of_measurement = UnitOfTemperature.FAHRENHEIT
    else:
      self._attr_unit_of_measurement = UnitOfTemperature.CELSIUS
```

Change line 50 from:

```python
    if appliance.appliance_info.get("deviceType") == "PORTABLE_AIR_CONDITIONER":
```

to:

```python
    if (appliance.appliance_info.get("deviceType") or '').upper() == "PORTABLE_AIR_CONDITIONER":
```

Change lines 124-134 (`fan_mode` property) from:

```python
  @property
  def fan_mode(self) -> str | None:
    if self._appliance._states.get('fanSpeedSetting') == 'auto':
      return FAN_AUTO
    elif self._appliance._states.get('fanSpeedSetting') == 'low':
      return FAN_LOW
    elif self._appliance._states.get('fanSpeedSetting') == 'middle':
      return FAN_MEDIUM
    elif self._appliance._states.get('fanSpeedSetting') == 'high':
      return FAN_HIGH
    else:
      return None
```

to:

```python
  @property
  def fan_mode(self) -> str | None:
    fan_speed = (self._appliance._states.get('fanSpeedSetting') or '').lower()
    if fan_speed == 'auto':
      return FAN_AUTO
    elif fan_speed == 'low':
      return FAN_LOW
    elif fan_speed == 'middle':
      return FAN_MEDIUM
    elif fan_speed == 'high':
      return FAN_HIGH
    else:
      return None
```

Change lines 141-151 (`hvac_mode` property) from:

```python
  @property
  def hvac_mode(self) -> HVACMode | None:
    if self._appliance._states.get('applianceState') == 'off':
      return HVACMode.OFF
    if self._appliance._states.get('mode') == 'cool':
      return HVACMode.COOL
    elif self._appliance._states.get('mode') == 'dry':
      return HVACMode.DRY
    elif self._appliance._states.get('mode') == 'fanOnly':
      return HVACMode.FAN_ONLY
    else:
      return HVACMode.OFF
```

to:

```python
  @property
  def hvac_mode(self) -> HVACMode | None:
    appliance_state = (self._appliance._states.get('applianceState') or '').lower()
    mode = (self._appliance._states.get('mode') or '').lower()
    if appliance_state == 'off':
      return HVACMode.OFF
    if mode == 'cool':
      return HVACMode.COOL
    elif mode == 'dry':
      return HVACMode.DRY
    elif mode == 'fanonly':
      return HVACMode.FAN_ONLY
    else:
      return HVACMode.OFF
```

Change lines 173-179 (`swing_mode` property) from:

```python
  @property
  def swing_mode(self) -> str | None:
    if self._appliance._states.get('verticalSwing') == 'off':
      return SWING_OFF
    elif self._appliance._states.get('verticalSwing') == 'on':
      return SWING_VERTICAL
    else:
      return None
```

to:

```python
  @property
  def swing_mode(self) -> str | None:
    swing = (self._appliance._states.get('verticalSwing') or '').lower()
    if swing == 'off':
      return SWING_OFF
    elif swing == 'on':
      return SWING_VERTICAL
    else:
      return None
```

Change lines 186-190 (`temperature_unit` property) — this one reads `self._attr_unit_of_measurement`, an internal enum set in `__init__` (already normalized by the Step 3 change above), so it needs no change. Leave lines 186-190 as-is.

Change line 194 (`preset_mode` property) from:

```python
    if self._appliance._states.get('sleepMode') == 'on':
```

to:

```python
    if (self._appliance._states.get('sleepMode') or '').lower() == 'on':
```

- [ ] **Step 4: Make `sensor.py` comparison case-insensitive**

In `custom_components/electrolux_ac/sensor.py`, change line 135 from:

```python
    if self._appliance._states.get('temperatureRepresentation') == 'fahrenheit':
```

to:

```python
    if (self._appliance._states.get('temperatureRepresentation') or '').lower() == 'fahrenheit':
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `.venv/bin/pytest tests/test_climate.py tests/test_climate_preset.py tests/test_sensor.py -v`
Expected: all PASS, including the 3 new uppercase tests and all pre-existing lowercase tests (no regression).

- [ ] **Step 6: Run the full suite**

Run: `.venv/bin/pytest tests/ -v`
Expected: all tests PASS.

- [ ] **Step 7: Commit**

```bash
git add custom_components/electrolux_ac/climate.py custom_components/electrolux_ac/sensor.py tests/test_climate.py tests/test_climate_preset.py tests/test_sensor.py
git commit -m "fix: make state-value string comparisons case-insensitive

The new SDK's fixtures use uppercase enum values where the old API used
lowercase; comparisons must tolerate either."
```

---

### Task 10: `manifest.json`, `CHANGELOG.md`, `CLAUDE.md`, and final verification

**Files:**
- Modify: `custom_components/electrolux_ac/manifest.json`
- Modify: `CHANGELOG.md`
- Modify: `CLAUDE.md`

**Interfaces:** none — documentation and packaging only.

- [ ] **Step 1: Update `manifest.json`**

Replace `custom_components/electrolux_ac/manifest.json` line `"requirements": [...]` and `"version": ...` — full file becomes:

```json
{
  "domain": "electrolux_ac",
  "name": "Electrolux AC",
  "codeowners": ["@TeroPihlaja"],
  "config_flow": true,
  "dependencies": [],
  "documentation": "https://github.com/TeroPihlaja/electrolux_ac",
  "integration_type": "hub",
  "iot_class": "cloud_push",
  "issue_tracker": "https://github.com/TeroPihlaja/electrolux_ac/issues",
  "requirements": ["electrolux-group-developer-sdk==0.6.1"],
  "version": "2.0.0"
}
```

- [ ] **Step 2: Add a CHANGELOG entry**

Add to the top of `CHANGELOG.md`, right after the `The format is based on...` line:

```markdown

## [2.0.0] - 2026-08-04

### Changed
- **Breaking:** migrated from `pyelectroluxocp` (archived upstream) to the officially maintained `electrolux-group-developer-sdk`. Authentication now uses an API key + access/refresh token pair generated at https://developer.electrolux.one/ instead of your Electrolux app email/password. Existing installs must remove and re-add the integration with the new credentials.
- Push updates now arrive via Server-Sent Events instead of WebSocket (same real-time behavior, different transport).
- Added a periodic (10 min) safety-net check that distinguishes invalid credentials from transient connectivity issues and triggers Home Assistant's reauth flow when credentials are revoked — the underlying reliability gap behind the 2026-07-28 outage.
```

- [ ] **Step 3: Update `CLAUDE.md`**

In `CLAUDE.md`, replace the `## Device` section's API line and the reinstall-caveat paragraph added earlier (about `--force-reinstall` for the `pyelectroluxocp` fork) with:

```markdown
API: [Electrolux Developer Portal API](https://developer.electrolux.one/) via `electrolux-group-developer-sdk` (official, PyPI). Requires an API key + access/refresh token pair generated manually via the developer portal (log in with your Electrolux account, create an API key, generate tokens) — see `config_flow.py`.
Live state arrives via Server-Sent Events (SSE); a 10-minute safety-net poll (`coordinator.py`) additionally verifies credentials and re-fetches full state.
```

Also update the `.venv` setup instructions (the `pip install "git+https://github.com/TeroPihlaja/py-electrolux-ocp.git@..."` line) to:

```bash
.venv/bin/pip install electrolux-group-developer-sdk==0.6.1
```

- [ ] **Step 4: Run the full test suite one final time**

Run: `.venv/bin/pytest tests/ -v`
Expected: all tests PASS (this repo's `.githooks/pre-commit` will also run this automatically on commit).

- [ ] **Step 5: Commit**

```bash
git add custom_components/electrolux_ac/manifest.json CHANGELOG.md CLAUDE.md
git commit -m "chore: prepare 2.0.0 release — switch manifest requirement to electrolux-group-developer-sdk"
```

- [ ] **Step 6: Manual end-to-end verification (do not skip — this cannot be caught by unit tests)**

This step requires your own Electrolux Developer Portal credentials (api_key, access_token, refresh_token) generated at https://developer.electrolux.one/. On a feature branch (not `main`, since `main` is what the live HA server tracks):

1. Copy the branch's `custom_components/electrolux_ac/` directory to a test Home Assistant instance (or the real one, accepting the risk since you're the sole user).
2. Remove the existing config entry (old `email`/`password` entries are incompatible) and add it again via the UI, entering the generated `api_key`/`access_token`/`refresh_token`.
3. Confirm the climate entity shows the correct HVAC mode, fan speed, swing, and current/target temperature matching the physical AC.
4. Change a setting from the physical AC's own remote and confirm the HA entity updates within a few seconds (proves the SSE stream is live).
5. Check the HA log for `custom_components.electrolux_ac` — confirm no `ClientResponseError`/`BadCredentialsException` spam, and that the periodic coordinator log line appears roughly every 10 minutes without errors.

If step 3 shows wrong/missing values, it's the uppercase/lowercase mismatch investigated in Task 9 — check the actual live value casing and confirm the `.lower()` normalization in `climate.py`/`sensor.py` covers it (it should, by design, regardless of casing).
