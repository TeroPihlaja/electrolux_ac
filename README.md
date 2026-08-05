# Electrolux AC — Home Assistant Custom Integration

Control and monitor your Electrolux portable air conditioner from Home Assistant via the official [Electrolux Developer Portal API](https://developer.electrolux.one/).

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
- Filter runtime (hours)
- Total compressor runtime (hours)
- Compressor state
- WiFi signal strength (RSSI)
- HEPA filter lifetime
- Alerts

## Requirements

- Home Assistant 2024.1 or newer
- An API key and access/refresh token pair from the [Electrolux Developer Portal](https://developer.electrolux.one/) (log in with your Electrolux account, create an API key, then generate a token pair)
- Supported device: tested on Electrolux COMFORT600 portable AC. Other Electrolux portable AC models exposed by the API as `PORTABLE_AIR_CONDITIONER` should work too, since the integration doesn't check the specific model — untested, so please report back if you try one

## Installation

1. Copy the `electrolux_ac` folder into your Home Assistant `config/custom_components/` directory.
2. Restart Home Assistant.
3. Go to **Settings → Devices & Services → Add Integration** and search for **Electrolux AC**.
4. Enter the API key, access token, and refresh token generated at the [Electrolux Developer Portal](https://developer.electrolux.one/).

### Via Git

```bash
cd config/custom_components
git clone git@github.com:TeroPihlaja/electrolux_ac.git electrolux_ac
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
python3 -m venv .venv
.venv/bin/pip install -r requirements_test.txt
.venv/bin/pip install electrolux-group-developer-sdk==0.6.1
.venv/bin/pytest tests/ -v
```

### Project layout

```
custom_components/electrolux_ac/
  __init__.py         # HA integration entry point
  hub.py              # Hub and Appliance classes (API connection, state management)
  coordinator.py      # 10-minute safety-net poll (credential + connectivity checks)
  climate.py          # Climate entity (HVAC control + sleep preset)
  sensor.py           # Temperature + generic sensors
  config_flow.py      # UI config flow (API key/token entry)
  const.py            # Constants
  manifest.json       # Integration metadata
tests/                # pytest test suite
```

## Known limitations

- Sleep mode is disabled by the device when in DRY or FAN_ONLY mode
- `verticalSwing` and `sleepMode` don't push live via Server-Sent Events on this device — the climate entity reflects a confirmed successful command locally until the next push/poll
