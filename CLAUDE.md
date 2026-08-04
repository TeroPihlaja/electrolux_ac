## Pre-commit hook

Always run the test suite before creating a commit. The repo includes a pre-commit hook in `.githooks/`:

```bash
git config core.hooksPath .githooks
```

Once configured, `git commit` will automatically run the tests, then Hassfest validation, and abort on failure.

## Running tests

```bash
.venv/bin/pytest tests/ -v
```

If `.venv` doesn't exist:
```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements_test.txt
.venv/bin/pip install electrolux-group-developer-sdk==0.6.1
```

## Local CI checks

The `Validate` GitHub Actions workflow (`.github/workflows/validate.yml`) runs Hassfest and HACS
validation via Docker images. Both can be reproduced locally (needs Docker — e.g. `brew install
--cask orbstack`):

```bash
scripts/run_hassfest.sh          # same check as CI; also runs automatically pre-commit
scripts/run_hacs_validation.sh   # checks the *pushed* state on GitHub (releases, topics) — run after pushing/tagging, needs `gh auth login`
```

If Docker isn't installed/running, both scripts print a message and exit 0 (skip) rather than blocking the commit.

## Key files

- `custom_components/electrolux_ac/hub.py` — Hub (API connection) and Appliance (state + callbacks) classes
- `custom_components/electrolux_ac/climate.py` — ClimateEntity: modes, fan, swing, temperature, sleep preset
- `custom_components/electrolux_ac/sensor.py` — TemperatureSensor + GenericSensor (filter, runtime, RSSI, compressor)
- `custom_components/electrolux_ac/__init__.py` — async_setup_entry / async_unload_entry

## Device

Electrolux COMFORT600 portable AC (model `AZUL`, deviceType `PORTABLE_AIR_CONDITIONER`).
API: [Electrolux Developer Portal API](https://developer.electrolux.one/) via `electrolux-group-developer-sdk` (official, PyPI). Requires an API key + access/refresh token pair generated manually via the developer portal (log in with your Electrolux account, create an API key, generate tokens) — see `config_flow.py`.
Live state arrives via Server-Sent Events (SSE); a 10-minute safety-net poll (`coordinator.py`) additionally verifies credentials and re-fetches full state.

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
