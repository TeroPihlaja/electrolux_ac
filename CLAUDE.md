## Pre-commit hook

Always run the test suite before creating a commit. The repo includes a pre-commit hook in `.githooks/`:

```bash
git config core.hooksPath .githooks
```

Once configured, `git commit` will automatically run the tests and abort on failure.

## Running tests

```bash
.venv/bin/pytest tests/ -v
```

If `.venv` doesn't exist:
```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements_test.txt
.venv/bin/pip install "git+https://github.com/TeroPihlaja/py-electrolux-ocp.git@v0.1.4-teropihlaja1"
```

## Key files

- `custom_components/electrolux_ac/hub.py` — Hub (API connection) and Appliance (state + callbacks) classes
- `custom_components/electrolux_ac/climate.py` — ClimateEntity: modes, fan, swing, temperature, sleep preset
- `custom_components/electrolux_ac/sensor.py` — TemperatureSensor + GenericSensor (filter, runtime, RSSI, compressor)
- `custom_components/electrolux_ac/__init__.py` — async_setup_entry / async_unload_entry

## Device

Electrolux COMFORT600 portable AC (model `AZUL`, deviceType `PORTABLE_AIR_CONDITIONER`).
API: Electrolux OneApp OCP via `pyelectroluxocp`, pinned to a patched fork ([TeroPihlaja/py-electrolux-ocp](https://github.com/TeroPihlaja/py-electrolux-ocp)) since upstream is archived — see `manifest.json`.
Live state arrives via WebSocket; initial state polled on setup.

Home Assistant's dependency check for a `name @ git+url` requirement only looks
at the package name, not the URL — so bumping the fork's tag in `manifest.json`
alone will NOT trigger a reinstall if any version of `pyelectroluxocp` is
already present. After updating the fork, force it on the server with:
```bash
docker exec homeassistant python3 -m pip install --force-reinstall --no-deps "pyelectroluxocp @ git+https://github.com/TeroPihlaja/py-electrolux-ocp.git@<tag>"
docker restart homeassistant
```

## Releasing

When creating a release:
1. Add a new section to `CHANGELOG.md` with the version and today's date
2. Bump `"version"` in `custom_components/electrolux_ac/manifest.json` to match
3. Commit both files together, then tag and push: `git tag vX.Y.Z && git push github vX.Y.Z`
4. Create a GitHub release: `gh release create vX.Y.Z --title "vX.Y.Z" --notes "..."`

## Debug logging

To enable verbose logs, add to `config/configuration.yaml` on the server:

```yaml
logger:
  default: warning
  logs:
    custom_components.electrolux_ac: debug
```

Remove when done — debug output is very verbose.
