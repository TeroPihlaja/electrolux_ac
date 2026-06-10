# Code Review Bug Fixes Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix 9 confirmed bugs found in code review of the Electrolux AC Home Assistant custom component.

**Architecture:** All fixes are in the existing four Python files (hub.py, climate.py, sensor.py, __init__.py). No new files are introduced. Changes are grouped by file to minimise context switching, with the most critical runtime bug (infinite hang) fixed first.

**Tech Stack:** Python 3.11+, Home Assistant custom component, pyelectroluxocp

---

## Files Modified

- Modify: `hub.py` — remove duplicate `discover_appliances` call from `__init__`, fix `wait_for_state` to not swallow exceptions, guard `state_update_callback` against missing appliance ID
- Modify: `sensor.py` — fix `wait_for_state` caller to await directly, migrate `SensorBase` from deprecated `Entity` to `SensorEntity`
- Modify: `climate.py` — fix `wait_for_state` caller, add missing `()` on three `async_write_ha_state` calls, add `return` after OFF handling, guard `None.capitalize()`, remove duplicate `_attr_supported_features`
- Modify: `__init__.py` — remove redundant `asyncio.sleep(60)`

---

## Task 1: Fix Hub double-initialization

**Files:**
- Modify: `hub.py:29`

The `Hub.__init__` fires `asyncio.ensure_future(self.discover_appliances())` unnecessarily. `__init__.py` already calls `await hub.discover_appliances()` explicitly, so this produces duplicate `Appliance` objects and duplicate WebSocket state-update listeners per appliance on every startup.

- [ ] **Step 1: Remove the ensure_future call from Hub.__init__**

In `hub.py`, delete line 29 and the commented-out update_loop lines (31-33) for clarity:

```python
class Hub:
    def __init__(self, hass: HomeAssistant, email: str, password: str):
        _LOGGER.info("Creating Electrolux hub with email %s", email)

        self._email = email
        self._password = password
        self._hass = hass
        self._name = email
        self._id = email.lower()
        self._client = None
        self.appliances = None
        self.online = False
```

(Remove the three lines starting at `asyncio.ensure_future(self.discover_appliances())` and the two commented-out update_loop lines.)

- [ ] **Step 2: Commit**

```bash
git -C /Users/teropihlaja/dev/electrolux_ac add hub.py
git -C /Users/teropihlaja/dev/electrolux_ac commit -m "fix: remove duplicate discover_appliances call from Hub.__init__"
```

---

## Task 2: Fix wait_for_state — exception swallowed, setup hangs forever

**Files:**
- Modify: `hub.py:103-112`
- Modify: `sensor.py:22-24`
- Modify: `climate.py:45-48`

The callers do `asyncio.create_task(appliance.wait_for_state(status_ready))` then immediately `await status_ready.wait()`. If `wait_for_state` raises, the task discards the exception and `status_ready` is never set — the `await` blocks forever. Fix: remove the `asyncio.Event` indirection entirely and await `wait_for_state` directly, so exceptions propagate to the caller.

- [ ] **Step 1: Refactor wait_for_state to return a bool instead of using an Event**

In `hub.py`, replace `wait_for_state` (lines 103-112):

```python
async def wait_for_state(self):
    STATE_MAX = 5
    for i in range(STATE_MAX):
        _LOGGER.warning("Waiting for initial state: %d/%d", i + 1, STATE_MAX)
        await asyncio.sleep(5)
        if self._states:
            return
    raise ApplianceStateNotReady(
        "Did not receive state information for appliance: %s" % self._id
    )
```

- [ ] **Step 2: Update the sensor.py caller**

In `sensor.py`, replace lines 22-24:

```python
  new_devices = []
  for appliance in hub.appliances:
    try:
      await appliance.wait_for_state()
    except Exception:
      _LOGGER.warning("Skipping appliance %s — state not ready", appliance.appliance_id)
      continue
    new_devices.append(TemperatureSensor(appliance))
```

- [ ] **Step 3: Update the climate.py caller**

In `climate.py`, replace lines 44-50:

```python
  new_devices = []
  for appliance in hub.appliances:
    try:
      await appliance.wait_for_state()
    except Exception:
      _LOGGER.warning("Skipping appliance %s — state not ready", appliance.appliance_id)
      continue
    if appliance.appliance_info.get("deviceType") == "PORTABLE_AIR_CONDITIONER":
      new_devices.append(ElectroluxClimate(appliance))
```

- [ ] **Step 4: Commit**

```bash
git -C /Users/teropihlaja/dev/electrolux_ac add hub.py sensor.py climate.py
git -C /Users/teropihlaja/dev/electrolux_ac commit -m "fix: await wait_for_state directly so exceptions propagate instead of hanging forever"
```

---

## Task 3: Guard state_update_callback against missing appliance ID

**Files:**
- Modify: `hub.py:120-127`

`state_update_callback` does `data[self._id]` without checking if the key exists. A WebSocket push for a different appliance or an error envelope raises `KeyError`, which propagates out of the callback and silences all future state updates.

- [ ] **Step 1: Add key guard**

In `hub.py`, replace `state_update_callback` (lines 120-127):

```python
    def state_update_callback(self, data):
        _LOGGER.info("appliance state updated: %s", json.dumps(data))
        if self._id not in data:
            return
        for key, value in data[self._id].items():
            self._states[key] = value
        _LOGGER.debug("current state: %s", self._states)
        self.publish_updates()
```

- [ ] **Step 2: Commit**

```bash
git -C /Users/teropihlaja/dev/electrolux_ac add hub.py
git -C /Users/teropihlaja/dev/electrolux_ac commit -m "fix: guard state_update_callback against missing appliance ID in push payload"
```

---

## Task 4: Fix missing () on async_write_ha_state in three climate handlers

**Files:**
- Modify: `climate.py:229, 246, 260`

`async_set_swing_mode` (line 229), `async_set_fan_mode` (line 246), and `async_set_temperature` (line 260) all end with `self.async_write_ha_state` as a bare attribute reference — the method is never called, so HA state is never pushed after these commands.

- [ ] **Step 1: Add parentheses on all three lines**

Line 229 — change:
```python
    self.async_write_ha_state
```
to:
```python
    self.async_write_ha_state()
```

Line 246 — same change.

Line 260 — same change.

- [ ] **Step 2: Commit**

```bash
git -C /Users/teropihlaja/dev/electrolux_ac add climate.py
git -C /Users/teropihlaja/dev/electrolux_ac commit -m "fix: call async_write_ha_state() in swing, fan, and temperature handlers"
```

---

## Task 5: Fix async_set_hvac_mode OFF fall-through

**Files:**
- Modify: `climate.py:182-196`

When `hvac_mode == HVACMode.OFF`, `async_turn_off()` is called, but there is no `return`, so `execute_command("mode", HVACMode.OFF)` always runs afterwards — sending a spurious second command to the device. The FAN_ONLY branch also sets `hvac_mode = "fanonly"` (lowercase) before the execute_command call — the API value should match the device's expected casing.

- [ ] **Step 1: Add early return after OFF, and fix FAN_ONLY casing**

Replace `async_set_hvac_mode` (lines 182-196):

```python
  async def async_set_hvac_mode(self, hvac_mode):
    """Set new target hvac mode."""
    _LOGGER.debug(
        "Setting HVAC mode to %s for device %s",
        hvac_mode,
        self._attr_name,
    )
    if hvac_mode == HVACMode.OFF:
      await self.async_turn_off()
      return
    await self.async_turn_on()
    if hvac_mode == HVACMode.FAN_ONLY:
      await self._appliance.execute_command("mode", "fanOnly")
    else:
      await self._appliance.execute_command("mode", hvac_mode)
    self.async_write_ha_state()
```

- [ ] **Step 2: Commit**

```bash
git -C /Users/teropihlaja/dev/electrolux_ac add climate.py
git -C /Users/teropihlaja/dev/electrolux_ac commit -m "fix: return after async_turn_off in set_hvac_mode, fix fanOnly casing"
```

---

## Task 6: Guard None.capitalize() in device_info

**Files:**
- Modify: `climate.py:97-106`

`device_info` calls `.capitalize()` directly on `appliance_info.get('model')` and `.get('brand')`. When either field is absent from the API response, `.get()` returns `None` and `.capitalize()` raises `AttributeError`, preventing entity registration.

- [ ] **Step 1: Add None guards**

Replace `device_info` (lines 96-106):

```python
  @property
  def device_info(self) -> DeviceInfo:
    """Information about this entity/device."""
    model = self._appliance.appliance_info.get('model')
    brand = self._appliance.appliance_info.get('brand')
    return DeviceInfo(
      identifiers={
        (DOMAIN, self._appliance.appliance_id)
      },
      name=self.name,
      model=model.capitalize() if model else None,
      manufacturer=brand.capitalize() if brand else None,
    )
```

- [ ] **Step 2: Commit**

```bash
git -C /Users/teropihlaja/dev/electrolux_ac add climate.py
git -C /Users/teropihlaja/dev/electrolux_ac commit -m "fix: guard None.capitalize() in device_info for missing model/brand"
```

---

## Task 7: Remove duplicate _attr_supported_features declaration

**Files:**
- Modify: `climate.py:58-73`

`_attr_supported_features` is declared twice on the class. The second declaration (line 73) overwrites the first and silently drops `PRESET_MODE`. Since preset mode is not implemented anywhere in the class, remove the first declaration (lines 58-65) and keep the second as the single source of truth.

- [ ] **Step 1: Delete the first _attr_supported_features block**

Remove lines 58-65 (the multi-line declaration that includes PRESET_MODE):

```python
  _attr_precision = PRECISION_WHOLE
  _attr_supported_features = ClimateEntityFeature.TARGET_TEMPERATURE | ClimateEntityFeature.FAN_MODE | ClimateEntityFeature.SWING_MODE | ClimateEntityFeature.TURN_ON | ClimateEntityFeature.TURN_OFF
  _attr_target_temperature_step = TARGET_TEMPERATURE_STEP
```

(The single-line declaration that was on line 73 becomes the only declaration.)

- [ ] **Step 2: Commit**

```bash
git -C /Users/teropihlaja/dev/electrolux_ac add climate.py
git -C /Users/teropihlaja/dev/electrolux_ac commit -m "fix: remove duplicate _attr_supported_features that was silently dropping PRESET_MODE"
```

---

## Task 8: Remove redundant asyncio.sleep(60) in __init__.py

**Files:**
- Modify: `__init__.py:26`

`ConfigEntryNotReady` already instructs HA to retry with its own backoff. The `await asyncio.sleep(60)` before raising it delays the HA event loop for 60 seconds on every failed startup attempt with no benefit.

- [ ] **Step 1: Remove the sleep**

In `__init__.py`, delete line 26 (`await asyncio.sleep(60)`). The except block becomes:

```python
    except aiohttp.client_exceptions.ClientResponseError as ex:
        _LOGGER.error("Error connecting to Electrolux OCP: %s", ex)
        await hass.data[DOMAIN][entry.entry_id].disconnect()
        raise ConfigEntryNotReady("Error connecting to Electrolux OCP: %s" % ex) from ex
```

- [ ] **Step 2: Commit**

```bash
git -C /Users/teropihlaja/dev/electrolux_ac add __init__.py
git -C /Users/teropihlaja/dev/electrolux_ac commit -m "fix: remove redundant asyncio.sleep(60) before ConfigEntryNotReady"
```

---

## Task 9: Migrate SensorBase from deprecated Entity to SensorEntity

**Files:**
- Modify: `sensor.py:1-107`

`SensorBase` inherits from the deprecated `homeassistant.helpers.entity.Entity` instead of `SensorEntity`. This loses native unit-of-measurement handling, `native_value`, and `state_class` support (required for HA long-term statistics). Migration involves changing the import, base class, and property name from `state` to `native_value`.

- [ ] **Step 1: Update imports**

Replace the import block at the top of `sensor.py`:

```python
"""Platform for sensor integration."""

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity, SensorStateClass

from homeassistant.const import UnitOfTemperature

from .const import DOMAIN
import logging
import asyncio

_LOGGER = logging.getLogger(__name__)
```

- [ ] **Step 2: Update SensorBase to extend SensorEntity**

Replace the `SensorBase` class definition line:

```python
class SensorBase(SensorEntity):
```

- [ ] **Step 3: Update TemperatureSensor to use native_unit_of_measurement and native_value**

Replace `TemperatureSensor.__init__` unit assignment and add `state_class`:

```python
class TemperatureSensor(SensorBase):
  """Representation of a Sensor."""

  device_class = SensorDeviceClass.TEMPERATURE
  state_class = SensorStateClass.MEASUREMENT

  def __init__(self, appliance):
    """Initialize the sensor."""
    super().__init__(appliance)

    self._attr_unique_id = f"{self._appliance.appliance_id}_temperature"
    self._attr_name = f"{self._appliance.name} Temperature"

    _LOGGER.warning("Creating temperature sensor with presentation: %s",
                    self._appliance._states.get('temperatureRepresentation'))
    if self._appliance._states.get('temperatureRepresentation') == 'celsius':
      self._attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
    else:
      self._attr_native_unit_of_measurement = UnitOfTemperature.FAHRENHEIT

  @property
  def native_value(self):
    """Return the state of the sensor."""
    if self._attr_native_unit_of_measurement == UnitOfTemperature.CELSIUS:
      temperature = self._appliance._states.get('ambientTemperatureC')
    else:
      temperature = self._appliance._states.get('ambientTemperatureF')
    _LOGGER.debug("Returning temperature: %s", temperature)
    return temperature
```

- [ ] **Step 4: Commit**

```bash
git -C /Users/teropihlaja/dev/electrolux_ac add sensor.py
git -C /Users/teropihlaja/dev/electrolux_ac commit -m "fix: migrate SensorBase to SensorEntity with native_value and state_class"
```

---

## Task 10: Push all fixes to GitLab

- [ ] **Step 1: Push**

```bash
git -C /Users/teropihlaja/dev/electrolux_ac push origin main
```

- [ ] **Step 2: Verify on the remote server**

```bash
ssh crazyguy@home.crazyguy.info "cd /home/crazyguy/homeassistant/config/custom_components/electrolux_ac && git pull origin main"
```
