# Sensors and Sleep Preset Design

## Goal

Add five diagnostic/operational sensors and a sleep mode preset to the Electrolux AC Home Assistant custom component.

## Confirmed Device State Values

From live device state capture (2026-06-09):

```json
{
  "filterState": "clean",
  "filterRuntime": 900000,
  "totalRuntime": 11799800,
  "compressorState": "off",
  "sleepMode": "off",
  "networkInterface": { "rssi": -40 }
}
```

Runtime values are in seconds (`filterRuntime` = 900000 s = 250 h, `totalRuntime` = 11799800 s = ~3278 h).

---

## Sensors (`sensor.py`)

### Generic sensor class

A single `GenericSensor(SensorBase)` replaces five near-identical classes. It is constructed with:

| Parameter | Type | Purpose |
|-----------|------|---------|
| `appliance` | `Appliance` | parent appliance |
| `state_key` | `str` | key in `_states` dict (supports `"a.b"` dot-notation for nested keys) |
| `name_suffix` | `str` | appended to appliance name, e.g. `"Filter State"` |
| `unique_id_suffix` | `str` | appended to appliance ID for unique_id |
| `device_class` | `SensorDeviceClass \| None` | HA device class |
| `native_unit` | `str \| None` | unit of measurement |
| `state_class` | `SensorStateClass \| None` | for statistics |

`native_value` resolves `state_key` against `_states`, splitting on `.` for nested access (e.g. `"networkInterface.rssi"` → `_states["networkInterface"]["rssi"]`). Returns `None` if any part of the path is missing.

### Sensors registered per appliance

| Name suffix | state_key | device_class | unit | state_class |
|-------------|-----------|--------------|------|-------------|
| Filter State | `filterState` | none | — | none |
| Filter Runtime | `filterRuntime` | `DURATION` | `UnitOfTime.SECONDS` | `TOTAL_INCREASING` |
| Total Runtime | `totalRuntime` | `DURATION` | `UnitOfTime.SECONDS` | `TOTAL_INCREASING` |
| Compressor State | `compressorState` | none | — | none |
| WiFi Signal | `networkInterface.rssi` | `SIGNAL_STRENGTH` | `SIGNAL_STRENGTH_DECIBELS_MILLIWATT` | none |

### `async_setup_entry` change

After constructing `TemperatureSensor`, also append one `GenericSensor` per entry in the table above for the same appliance.

---

## Sleep Preset (`climate.py`)

### Imports added

```python
from homeassistant.components.climate import PRESET_NONE, PRESET_SLEEP
```

### Class attribute changes

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

### New property

```python
@property
def preset_mode(self) -> str:
    if self._appliance._states.get('sleepMode') == 'on':
        return PRESET_SLEEP
    return PRESET_NONE
```

### New service handler

```python
async def async_set_preset_mode(self, preset_mode: str) -> None:
    value = "on" if preset_mode == PRESET_SLEEP else "off"
    await self._appliance.execute_command("sleepMode", value)
    self.async_write_ha_state()
```

---

## Tests

### Infrastructure

The repo has no existing tests. This work introduces the full test stack.

**New files:**
- `requirements_test.txt` — test dependencies
- `conftest.py` — root-level pytest config; makes `custom_components.electrolux_ac` importable without restructuring the repo
- `tests/__init__.py` — empty
- `tests/conftest.py` — shared fixtures (mock Appliance, mock Hub)
- `tests/test_sensor.py` — GenericSensor tests
- `tests/test_climate_preset.py` — sleep preset tests

**`requirements_test.txt`:**
```
pytest
pytest-asyncio
pytest-homeassistant-custom-component
```

**Root `conftest.py`** (makes the repo importable as `custom_components.electrolux_ac`):
```python
import sys, types
from pathlib import Path

# Inject a 'custom_components' namespace package pointing to the parent of the repo root,
# so that 'custom_components.electrolux_ac' resolves to this repo's files.
if "custom_components" not in sys.modules:
    cc = types.ModuleType("custom_components")
    cc.__path__ = [str(Path(__file__).parent.parent)]
    sys.modules["custom_components"] = cc

pytest_plugins = "pytest_homeassistant_custom_component"
```

**`tests/conftest.py`** — shared mock Appliance fixture:
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

### `tests/test_sensor.py` — GenericSensor

```python
from custom_components.electrolux_ac.sensor import GenericSensor
from homeassistant.components.sensor import SensorDeviceClass, SensorStateClass

def test_simple_key(mock_appliance):
    mock_appliance._states = {"filterState": "clean"}
    sensor = GenericSensor(mock_appliance, "filterState", "Filter State", "filter_state", None, None, None)
    assert sensor.native_value == "clean"

def test_nested_key(mock_appliance):
    mock_appliance._states = {"networkInterface": {"rssi": -40}}
    sensor = GenericSensor(mock_appliance, "networkInterface.rssi", "WiFi Signal", "rssi",
                           SensorDeviceClass.SIGNAL_STRENGTH, "dBm", None)
    assert sensor.native_value == -40

def test_missing_key_returns_none(mock_appliance):
    mock_appliance._states = {}
    sensor = GenericSensor(mock_appliance, "filterState", "Filter State", "filter_state", None, None, None)
    assert sensor.native_value is None

def test_missing_nested_key_returns_none(mock_appliance):
    mock_appliance._states = {"networkInterface": {}}
    sensor = GenericSensor(mock_appliance, "networkInterface.rssi", "WiFi Signal", "rssi",
                           SensorDeviceClass.SIGNAL_STRENGTH, "dBm", None)
    assert sensor.native_value is None

def test_attributes(mock_appliance):
    sensor = GenericSensor(mock_appliance, "filterRuntime", "Filter Runtime", "filter_runtime",
                           SensorDeviceClass.DURATION, "s", SensorStateClass.TOTAL_INCREASING)
    assert sensor.device_class == SensorDeviceClass.DURATION
    assert sensor.native_unit_of_measurement == "s"
    assert sensor.state_class == SensorStateClass.TOTAL_INCREASING
    assert sensor.unique_id == "test_appliance_id_filter_runtime"
    assert sensor.name == "Test AC Filter Runtime"
```

### `tests/test_climate_preset.py` — Sleep preset

```python
import pytest
from unittest.mock import patch
from homeassistant.components.climate import PRESET_NONE, PRESET_SLEEP
from custom_components.electrolux_ac.climate import ElectroluxClimate

def make_climate(mock_appliance):
    mock_appliance._states = {
        "temperatureRepresentation": "celsius",
        "sleepMode": "off",
    }
    mock_appliance.appliance_info = {"model": "comfort600", "brand": "electrolux", "deviceType": "PORTABLE_AIR_CONDITIONER"}
    return ElectroluxClimate(mock_appliance)

def test_preset_none_when_sleep_off(mock_appliance):
    climate = make_climate(mock_appliance)
    mock_appliance._states["sleepMode"] = "off"
    assert climate.preset_mode == PRESET_NONE

def test_preset_sleep_when_sleep_on(mock_appliance):
    climate = make_climate(mock_appliance)
    mock_appliance._states["sleepMode"] = "on"
    assert climate.preset_mode == PRESET_SLEEP

@pytest.mark.asyncio
async def test_set_preset_sleep(mock_appliance):
    climate = make_climate(mock_appliance)
    with patch.object(climate, "async_write_ha_state"):
        await climate.async_set_preset_mode(PRESET_SLEEP)
    mock_appliance.execute_command.assert_called_once_with("sleepMode", "on")

@pytest.mark.asyncio
async def test_set_preset_none(mock_appliance):
    climate = make_climate(mock_appliance)
    with patch.object(climate, "async_write_ha_state"):
        await climate.async_set_preset_mode(PRESET_NONE)
    mock_appliance.execute_command.assert_called_once_with("sleepMode", "off")
```

---

## Files Changed

- `requirements_test.txt` — new: test dependencies
- `conftest.py` — new: root pytest config + custom_components namespace shim
- `tests/__init__.py` — new: empty
- `tests/conftest.py` — new: shared mock_appliance fixture
- `tests/test_sensor.py` — new: GenericSensor tests
- `tests/test_climate_preset.py` — new: sleep preset tests
- `sensor.py` — add `GenericSensor` class; update `async_setup_entry` to register 5 new sensors per appliance
- `climate.py` — add `PRESET_NONE`/`PRESET_SLEEP` imports, add `PRESET_MODE` to supported features, add `_attr_preset_modes`, `preset_mode` property, `async_set_preset_mode` handler
