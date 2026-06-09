# Sensors and Sleep Preset Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add five new sensors (filter state, filter runtime, total runtime, compressor state, WiFi RSSI) and a sleep mode preset to the Electrolux AC Home Assistant custom component, with a full pytest test suite.

**Architecture:** A single parameterised `GenericSensor(SensorBase)` class handles all five new sensors using dot-notation key resolution for nested state values. Sleep mode is exposed as `PRESET_NONE`/`PRESET_SLEEP` on the existing `ElectroluxClimate` entity. Test infrastructure uses `pytest-homeassistant-custom-component` with a namespace shim so the repo root is importable as `custom_components.electrolux_ac` without restructuring the repo.

**Tech Stack:** Python 3.11+, Home Assistant custom component, pytest, pytest-homeassistant-custom-component, pytest-asyncio

---

## Files

- Create: `requirements_test.txt`
- Create: `conftest.py` (repo root — pytest namespace shim)
- Create: `setup.cfg` (pytest config)
- Create: `tests/__init__.py`
- Create: `tests/conftest.py` (shared fixtures)
- Create: `tests/test_sensor.py`
- Create: `tests/test_climate_preset.py`
- Modify: `sensor.py` — add `GenericSensor`, register 5 sensors in `async_setup_entry`
- Modify: `climate.py` — add `PRESET_MODE` support

---

## Task 1: Test infrastructure

**Files:**
- Create: `requirements_test.txt`
- Create: `conftest.py`
- Create: `setup.cfg`
- Create: `tests/__init__.py`
- Create: `tests/conftest.py`

- [ ] **Step 1: Create `requirements_test.txt`**

```
pytest
pytest-asyncio
pytest-homeassistant-custom-component
```

- [ ] **Step 2: Create root `conftest.py`**

This shim makes `custom_components.electrolux_ac` importable without moving files.  
`Path(__file__).parent` is the repo root (e.g. `.../electrolux_ac/`).  
`Path(__file__).parent.parent` is its parent (e.g. `.../dev/`), which contains the `electrolux_ac` directory — so Python can resolve `custom_components.electrolux_ac` → `.../dev/electrolux_ac/`.

```python
import sys
import types
from pathlib import Path

if "custom_components" not in sys.modules:
    cc = types.ModuleType("custom_components")
    cc.__path__ = [str(Path(__file__).parent.parent)]
    sys.modules["custom_components"] = cc

pytest_plugins = "pytest_homeassistant_custom_component"
```

- [ ] **Step 3: Create `setup.cfg`**

```ini
[tool:pytest]
testpaths = tests
asyncio_mode = auto
```

- [ ] **Step 4: Create `tests/__init__.py`**

Empty file.

- [ ] **Step 5: Create `tests/conftest.py`**

```python
from unittest.mock import AsyncMock, MagicMock
import pytest


@pytest.fixture
def mock_appliance():
    appliance = MagicMock()
    appliance.appliance_id = "test_appliance_id"
    appliance.name = "Test AC"
    appliance.online = True
    appliance.hub = MagicMock()
    appliance.hub.online = True
    appliance._states = {}
    appliance.execute_command = AsyncMock()
    appliance.register_callback = MagicMock()
    appliance.remove_callback = MagicMock()
    return appliance
```

- [ ] **Step 6: Install dependencies and verify pytest runs**

```bash
cd /Users/teropihlaja/dev/electrolux_ac
pip install -r requirements_test.txt
pytest tests/ -v
```

Expected: `no tests ran` (or 0 passed, no errors).

- [ ] **Step 7: Commit**

```bash
git -C /Users/teropihlaja/dev/electrolux_ac add requirements_test.txt conftest.py setup.cfg tests/
git -C /Users/teropihlaja/dev/electrolux_ac commit -m "test: add pytest-homeassistant-custom-component infrastructure"
```

---

## Task 2: GenericSensor — implementation (TDD)

**Files:**
- Create: `tests/test_sensor.py`
- Modify: `sensor.py`

- [ ] **Step 1: Write all failing tests in `tests/test_sensor.py`**

```python
import pytest
from homeassistant.components.sensor import SensorDeviceClass, SensorStateClass
from custom_components.electrolux_ac.sensor import GenericSensor


def test_simple_key(mock_appliance):
    mock_appliance._states = {"filterState": "clean"}
    sensor = GenericSensor(
        mock_appliance, "filterState", "Filter State", "filter_state",
        None, None, None,
    )
    assert sensor.native_value == "clean"


def test_nested_key(mock_appliance):
    mock_appliance._states = {"networkInterface": {"rssi": -40}}
    sensor = GenericSensor(
        mock_appliance, "networkInterface.rssi", "WiFi Signal", "rssi",
        SensorDeviceClass.SIGNAL_STRENGTH, "dBm", None,
    )
    assert sensor.native_value == -40


def test_missing_top_level_key_returns_none(mock_appliance):
    mock_appliance._states = {}
    sensor = GenericSensor(
        mock_appliance, "filterState", "Filter State", "filter_state",
        None, None, None,
    )
    assert sensor.native_value is None


def test_missing_nested_key_returns_none(mock_appliance):
    mock_appliance._states = {"networkInterface": {}}
    sensor = GenericSensor(
        mock_appliance, "networkInterface.rssi", "WiFi Signal", "rssi",
        SensorDeviceClass.SIGNAL_STRENGTH, "dBm", None,
    )
    assert sensor.native_value is None


def test_attributes_set_correctly(mock_appliance):
    sensor = GenericSensor(
        mock_appliance, "filterRuntime", "Filter Runtime", "filter_runtime",
        SensorDeviceClass.DURATION, "s", SensorStateClass.TOTAL_INCREASING,
    )
    assert sensor.device_class == SensorDeviceClass.DURATION
    assert sensor.native_unit_of_measurement == "s"
    assert sensor.state_class == SensorStateClass.TOTAL_INCREASING
    assert sensor.unique_id == "test_appliance_id_filter_runtime"
    assert sensor.name == "Test AC Filter Runtime"
```

- [ ] **Step 2: Run tests to verify they all fail**

```bash
cd /Users/teropihlaja/dev/electrolux_ac
pytest tests/test_sensor.py -v
```

Expected: 5 FAILED with `ImportError: cannot import name 'GenericSensor'`.

- [ ] **Step 3: Add `GenericSensor` to `sensor.py`**

Add this import near the top of `sensor.py`:

```python
from homeassistant.const import UnitOfTime, SIGNAL_STRENGTH_DECIBELS_MILLIWATT
```

Add this class after `SensorBase` (before `TemperatureSensor`):

```python
class GenericSensor(SensorBase):
  """Sensor that reads a single key from appliance state, with dot-notation nested access."""

  def __init__(self, appliance, state_key, name_suffix, unique_id_suffix,
               device_class, native_unit, state_class):
    super().__init__(appliance)
    self._state_key = state_key
    self._attr_unique_id = f"{appliance.appliance_id}_{unique_id_suffix}"
    self._attr_name = f"{appliance.name} {name_suffix}"
    self._attr_device_class = device_class
    self._attr_native_unit_of_measurement = native_unit
    self._attr_state_class = state_class

  @property
  def native_value(self):
    value = self._appliance._states
    for part in self._state_key.split('.'):
      if not isinstance(value, dict):
        return None
      value = value.get(part)
      if value is None:
        return None
    return value
```

- [ ] **Step 4: Run tests to verify they all pass**

```bash
pytest tests/test_sensor.py -v
```

Expected: 5 PASSED.

- [ ] **Step 5: Commit**

```bash
git -C /Users/teropihlaja/dev/electrolux_ac add tests/test_sensor.py sensor.py
git -C /Users/teropihlaja/dev/electrolux_ac commit -m "feat: add GenericSensor with dot-notation nested key support"
```

---

## Task 3: Register the five new sensors in `async_setup_entry`

**Files:**
- Modify: `sensor.py:12-25`

- [ ] **Step 1: Update `async_setup_entry` in `sensor.py`**

Replace the existing `async_setup_entry` function:

```python
async def async_setup_entry(hass, config_entry, async_add_entities):
  """Add sensors for passed config_entry in HA."""
  hub = hass.data[DOMAIN][config_entry.entry_id]

  new_devices = []
  for appliance in hub.appliances:
    try:
      await appliance.wait_for_state()
    except Exception:
      _LOGGER.warning("Skipping appliance %s — state not ready", appliance.appliance_id)
      continue
    new_devices.append(TemperatureSensor(appliance))
    new_devices.append(GenericSensor(
      appliance, "filterState", "Filter State", "filter_state",
      None, None, None,
    ))
    new_devices.append(GenericSensor(
      appliance, "filterRuntime", "Filter Runtime", "filter_runtime",
      SensorDeviceClass.DURATION, UnitOfTime.SECONDS, SensorStateClass.TOTAL_INCREASING,
    ))
    new_devices.append(GenericSensor(
      appliance, "totalRuntime", "Total Runtime", "total_runtime",
      SensorDeviceClass.DURATION, UnitOfTime.SECONDS, SensorStateClass.TOTAL_INCREASING,
    ))
    new_devices.append(GenericSensor(
      appliance, "compressorState", "Compressor State", "compressor_state",
      None, None, None,
    ))
    new_devices.append(GenericSensor(
      appliance, "networkInterface.rssi", "WiFi Signal", "rssi",
      SensorDeviceClass.SIGNAL_STRENGTH, SIGNAL_STRENGTH_DECIBELS_MILLIWATT, None,
    ))
  if new_devices:
    async_add_entities(new_devices)
```

- [ ] **Step 2: Run the full test suite to confirm nothing broke**

```bash
cd /Users/teropihlaja/dev/electrolux_ac
pytest tests/ -v
```

Expected: all existing tests still PASS.

- [ ] **Step 3: Commit**

```bash
git -C /Users/teropihlaja/dev/electrolux_ac add sensor.py
git -C /Users/teropihlaja/dev/electrolux_ac commit -m "feat: register filter, runtime, compressor, and RSSI sensors"
```

---

## Task 4: Sleep preset on the climate entity (TDD)

**Files:**
- Create: `tests/test_climate_preset.py`
- Modify: `climate.py`

- [ ] **Step 1: Write all failing tests in `tests/test_climate_preset.py`**

```python
import pytest
from unittest.mock import patch
from homeassistant.components.climate import PRESET_NONE, PRESET_SLEEP
from custom_components.electrolux_ac.climate import ElectroluxClimate


def _make_climate(mock_appliance):
    mock_appliance._states = {
        "temperatureRepresentation": "celsius",
        "sleepMode": "off",
    }
    mock_appliance.appliance_info = {
        "model": "comfort600",
        "brand": "electrolux",
        "deviceType": "PORTABLE_AIR_CONDITIONER",
    }
    return ElectroluxClimate(mock_appliance)


def test_preset_mode_is_none_when_sleep_off(mock_appliance):
    climate = _make_climate(mock_appliance)
    mock_appliance._states["sleepMode"] = "off"
    assert climate.preset_mode == PRESET_NONE


def test_preset_mode_is_sleep_when_sleep_on(mock_appliance):
    climate = _make_climate(mock_appliance)
    mock_appliance._states["sleepMode"] = "on"
    assert climate.preset_mode == PRESET_SLEEP


def test_preset_mode_is_none_when_key_missing(mock_appliance):
    climate = _make_climate(mock_appliance)
    del mock_appliance._states["sleepMode"]
    assert climate.preset_mode == PRESET_NONE


async def test_set_preset_sleep_sends_on(mock_appliance):
    climate = _make_climate(mock_appliance)
    with patch.object(climate, "async_write_ha_state"):
        await climate.async_set_preset_mode(PRESET_SLEEP)
    mock_appliance.execute_command.assert_called_once_with("sleepMode", "on")


async def test_set_preset_none_sends_off(mock_appliance):
    climate = _make_climate(mock_appliance)
    with patch.object(climate, "async_write_ha_state"):
        await climate.async_set_preset_mode(PRESET_NONE)
    mock_appliance.execute_command.assert_called_once_with("sleepMode", "off")


def test_preset_modes_list(mock_appliance):
    climate = _make_climate(mock_appliance)
    assert climate.preset_modes == [PRESET_NONE, PRESET_SLEEP]
```

- [ ] **Step 2: Run tests to verify they all fail**

```bash
cd /Users/teropihlaja/dev/electrolux_ac
pytest tests/test_climate_preset.py -v
```

Expected: 6 FAILED — `AttributeError: 'ElectroluxClimate' object has no attribute 'preset_mode'` (or similar).

- [ ] **Step 3: Update `climate.py` imports**

Add `PRESET_NONE, PRESET_SLEEP` to the existing climate import block:

```python
from homeassistant.components.climate import (
  FAN_AUTO,
  FAN_HIGH,
  FAN_LOW,
  FAN_MEDIUM,
  PRESET_NONE,
  PRESET_SLEEP,
  SWING_OFF,
  SWING_VERTICAL,
  ClimateEntity,
  ClimateEntityFeature,
  HVACMode,
)
```

Also remove the duplicate `ClimateEntity` and `ClimateEntityFeature` imports that are currently in the block (lines 14-15 duplicate lines 11-12).

- [ ] **Step 4: Add `PRESET_MODE` to `_attr_supported_features` and add `_attr_preset_modes`**

Replace the existing `_attr_supported_features` line (currently line 59) with:

```python
  _attr_supported_features = (
    ClimateEntityFeature.TARGET_TEMPERATURE
    | ClimateEntityFeature.FAN_MODE
    | ClimateEntityFeature.SWING_MODE
    | ClimateEntityFeature.PRESET_MODE
    | ClimateEntityFeature.TURN_ON
    | ClimateEntityFeature.TURN_OFF
  )
  _attr_preset_modes = [PRESET_NONE, PRESET_SLEEP]
```

- [ ] **Step 5: Add `preset_mode` property and `async_set_preset_mode` to `ElectroluxClimate`**

Add these two methods after `temperature_unit` (before `async_set_hvac_mode`):

```python
  @property
  def preset_mode(self) -> str:
    if self._appliance._states.get('sleepMode') == 'on':
      return PRESET_SLEEP
    return PRESET_NONE

  async def async_set_preset_mode(self, preset_mode: str) -> None:
    """Set sleep mode on or off."""
    value = "on" if preset_mode == PRESET_SLEEP else "off"
    await self._appliance.execute_command("sleepMode", value)
    self.async_write_ha_state()
```

- [ ] **Step 6: Run tests to verify they all pass**

```bash
pytest tests/ -v
```

Expected: all tests PASS (5 sensor + 6 preset = 11 total).

- [ ] **Step 7: Commit**

```bash
git -C /Users/teropihlaja/dev/electrolux_ac add tests/test_climate_preset.py climate.py
git -C /Users/teropihlaja/dev/electrolux_ac commit -m "feat: add sleep mode preset to climate entity"
```

---

## Task 5: Deploy

- [ ] **Step 1: Run full test suite one final time**

```bash
cd /Users/teropihlaja/dev/electrolux_ac
pytest tests/ -v
```

Expected: all 11 tests PASS.

- [ ] **Step 2: Push to GitLab**

```bash
git -C /Users/teropihlaja/dev/electrolux_ac push origin main
```

- [ ] **Step 3: Pull and restart on the remote server**

```bash
ssh crazyguy@home.crazyguy.info "cd /home/crazyguy/homeassistant/config/custom_components/electrolux_ac && git pull origin main"
```

Then restart HA:

```bash
ssh crazyguy@home.crazyguy.info "cd /home/crazyguy/homeassistant && docker compose restart homeassistant"
```

- [ ] **Step 4: Verify new sensors appear in logs**

```bash
ssh crazyguy@home.crazyguy.info "sleep 60 && cd /home/crazyguy/homeassistant && docker compose logs --since=2m homeassistant 2>&1 | grep -i electrolux"
```

Expected: no errors; `Creating temperature sensor` log and no tracebacks.
