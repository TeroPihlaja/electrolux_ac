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

## Files Changed

- `sensor.py` — add `GenericSensor` class; update `async_setup_entry` to register 5 new sensors per appliance
- `climate.py` — add `PRESET_NONE`/`PRESET_SLEEP` imports, add `PRESET_MODE` to supported features, add `_attr_preset_modes`, `preset_mode` property, `async_set_preset_mode` handler
