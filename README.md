# Electrolux AC — Home Assistant Custom Integration

Control and monitor your Electrolux portable air conditioner from Home Assistant via the official Electrolux OneApp cloud API.

## Features

**Climate entity**
- On/Off
- Modes: Cool, Dry, Fan Only
- Fan speed: Auto, Low, Medium, High
- Vertical swing
- Target temperature (°C/°F)
- Sleep mode preset

**Sensors**
- Ambient temperature
- Filter state (clean/dirty)
- Filter runtime
- Total compressor runtime
- Compressor state
- WiFi signal strength (RSSI)

## Requirements

- Home Assistant 2024.1 or newer
- Electrolux account credentials (the same ones used in the Electrolux mobile app)
- Supported device: tested on Electrolux COMFORT600 portable AC (`PORTABLE_AIR_CONDITIONER` device type)

## Installation

1. Copy the `electrolux_ac` folder into your Home Assistant `config/custom_components/` directory.
2. Restart Home Assistant.
3. Go to **Settings → Devices & Services → Add Integration** and search for **Electrolux AC**.
4. Enter your Electrolux account email and password.

### Via Git (recommended for updates)

```bash
cd config/custom_components
git clone git@gitlab.com:TeroPihlaja/electrolux_ac.git electrolux_ac
```

To update:
```bash
cd config/custom_components/electrolux_ac
git pull
```

Then restart Home Assistant.

## Development

### Running tests

```bash
python3.14 -m venv .venv
.venv/bin/pip install -r requirements_test.txt
.venv/bin/pip install pyelectroluxocp
.venv/bin/pytest tests/ -v
```

### Project layout

```
electrolux_ac/
  __init__.py        # HA integration entry point
  hub.py             # Hub and Appliance classes (API connection, state management)
  climate.py         # Climate entity (HVAC control + sleep preset)
  sensor.py          # Temperature + generic sensors
  config_flow.py     # UI config flow (credentials entry)
  const.py           # Constants
  manifest.json      # Integration metadata
  tests/             # pytest test suite
```

## Known limitations

- Sleep mode is disabled by the device when in DRY or FAN_ONLY mode
- Temperature range is 16–32°C (device capability)
- WebSocket token refresh may fail after extended idle periods — restart HA if state stops updating
