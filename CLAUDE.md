git@gitlab.com:TeroPihlaja/electrolux_ac.git

SSH Connection:
crazyguy@home.crazyguy.info

Folder: /home/crazyguy/homeassistant/config/custom_components/electrolux_ac

## Deploy workflow

1. Make changes and commit locally in `/Users/teropihlaja/dev/electrolux_ac/`
2. Push: `git push origin main`
3. Pull on server: `ssh crazyguy@home.crazyguy.info "cd /home/crazyguy/homeassistant/config/custom_components/electrolux_ac && git pull origin main"`
4. Restart HA: `ssh crazyguy@home.crazyguy.info "cd /home/crazyguy/homeassistant && docker compose restart homeassistant"`

Always commit first, then push separately.

## Running tests

```bash
.venv/bin/pytest tests/ -v
```

If `.venv` doesn't exist:
```bash
/opt/homebrew/bin/python3 -m venv .venv
.venv/bin/pip install -r requirements_test.txt
.venv/bin/pip install pyelectroluxocp
```

## Key files

- `hub.py` — Hub (API connection) and Appliance (state + callbacks) classes
- `climate.py` — ClimateEntity: modes, fan, swing, temperature, sleep preset
- `sensor.py` — TemperatureSensor + GenericSensor (filter, runtime, RSSI, compressor)
- `__init__.py` — async_setup_entry / async_unload_entry

## Device

Electrolux COMFORT600 portable AC (model `AZUL`, deviceType `PORTABLE_AIR_CONDITIONER`).
API: Electrolux OneApp OCP via `pyelectroluxocp==0.1.3`.
Live state arrives via WebSocket; initial state polled on setup.

## Debug logging

To enable verbose logs, add to `config/configuration.yaml` on the server:

```yaml
logger:
  default: warning
  logs:
    custom_components.electrolux_ac: debug
```

Remove when done — debug output is very verbose.
