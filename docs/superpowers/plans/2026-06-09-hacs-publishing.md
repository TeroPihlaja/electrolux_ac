# HACS Publishing Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the Electrolux AC integration publishable to HACS by restructuring the repo, migrating to GitHub, fixing log levels, adding feature detection, and updating server deployment.

**Architecture:** The repo moves to the HACS-required structure (`custom_components/electrolux_ac/` subdirectory). Server deployment shifts from a git checkout inside `config/custom_components/` to a volume mount in `compose.yml`, consistent with how other custom integrations are already deployed on the server. Tests stay at repo root with `pythonpath = .` replacing the namespace shim.

**Tech Stack:** Python 3.14, Home Assistant, HACS, GitHub, Docker Compose

---

## Files

**Moved into `custom_components/electrolux_ac/` (via `git mv`):**
- `__init__.py`, `climate.py`, `hub.py`, `sensor.py`, `config_flow.py`, `const.py`, `manifest.json`, `strings.json`, `translations/`

**Modified at repo root:**
- `conftest.py` — remove namespace shim (no longer needed with real package structure)
- `setup.cfg` — add `pythonpath = .`
- `CLAUDE.md` — update repo URL, deployment instructions
- `README.md` — update installation instructions

**New at repo root:**
- `hacs.json`

**Modified inside `custom_components/electrolux_ac/`:**
- `hub.py` — fix log levels, add feature detection
- `sensor.py` — fix log level, remove TODO comment
- `manifest.json` — fill in `documentation` and `issue_tracker`

**Modified on server:**
- `/home/crazyguy/homeassistant/compose.yml` — add volume mount for component

---

## Task 1: Restructure repo — move component files to `custom_components/electrolux_ac/`

**Files:**
- Create: `custom_components/electrolux_ac/` (directory)
- Move: all component Python files and assets

- [ ] **Step 1: Create the package directory and move files**

```bash
cd /Users/teropihlaja/dev/electrolux_ac
mkdir -p custom_components/electrolux_ac
git mv __init__.py custom_components/electrolux_ac/
git mv climate.py custom_components/electrolux_ac/
git mv hub.py custom_components/electrolux_ac/
git mv sensor.py custom_components/electrolux_ac/
git mv config_flow.py custom_components/electrolux_ac/
git mv const.py custom_components/electrolux_ac/
git mv manifest.json custom_components/electrolux_ac/
git mv strings.json custom_components/electrolux_ac/
git mv translations custom_components/electrolux_ac/
```

- [ ] **Step 2: Update `conftest.py` — remove namespace shim**

`custom_components/` now exists as a real directory in the repo, so pytest can find `custom_components.electrolux_ac` via `pythonpath = .`. Replace the entire contents of `conftest.py` with:

```python
pytest_plugins = "pytest_homeassistant_custom_component"
```

- [ ] **Step 3: Update `setup.cfg` — add pythonpath**

```ini
[tool:pytest]
testpaths = tests
asyncio_mode = auto
pythonpath = .
```

- [ ] **Step 4: Run tests to verify they still pass**

```bash
cd /Users/teropihlaja/dev/electrolux_ac
.venv/bin/pytest tests/ -v
```

Expected: 12 passed.

- [ ] **Step 5: Commit**

```bash
git -C /Users/teropihlaja/dev/electrolux_ac add -A
git -C /Users/teropihlaja/dev/electrolux_ac commit -m "refactor: move component into custom_components/electrolux_ac/ for HACS"
```

---

## Task 2: Fix log levels

**Files:**
- Modify: `custom_components/electrolux_ac/hub.py`
- Modify: `custom_components/electrolux_ac/sensor.py`

Log level issues:
- `hub.py` Creating hub: `info` → `debug` (logs user's email address)
- `hub.py` connect/disconnect: `info` → `debug` (routine lifecycle)
- `hub.py` Waiting for state: `warning` → `debug` (normal startup polling)
- `hub.py` appliance state updated: `info` → `debug` (fires on every push)
- `hub.py` appliance info: `warn` → `debug` (`warn` is also deprecated)
- `hub.py` appliance capabilities: `info` → `debug`
- `sensor.py` Creating temperature sensor: `warning` → `debug`

- [ ] **Step 1: Fix log levels in `hub.py`**

Make these targeted replacements in `custom_components/electrolux_ac/hub.py`:

```python
# Line ~18: Hub __init__
_LOGGER.debug("Creating Electrolux hub with email %s", email)

# Line ~36: connect()
_LOGGER.debug("Connecting to Electrolux hub")

# Line ~42: disconnect()
_LOGGER.debug("Disconnecting from Electrolux hub")

# Line ~101: wait_for_state loop
_LOGGER.debug("Waiting for initial state: %d/%d", i + 1, STATE_MAX)

# Line ~116: state_update_callback
_LOGGER.debug("appliance state updated: %s", json.dumps(data))

# Line ~126: update_appliance_info (also fix deprecated .warn → .debug)
_LOGGER.debug("appliance info: %s", json.dumps(info))

# Line ~130: update_appliance_info capabilities
_LOGGER.debug("appliance capabilities: %s", json.dumps(capab))
```

- [ ] **Step 2: Fix log level in `sensor.py`**

In `custom_components/electrolux_ac/sensor.py`, change the temperature sensor creation log:

```python
# was: _LOGGER.warning(...)
_LOGGER.debug("Creating temperature sensor with presentation: %s",
              self._appliance._states.get('temperatureRepresentation'))
```

- [ ] **Step 3: Run tests**

```bash
.venv/bin/pytest tests/ -v
```

Expected: 12 passed.

- [ ] **Step 4: Commit**

```bash
git -C /Users/teropihlaja/dev/electrolux_ac add custom_components/
git -C /Users/teropihlaja/dev/electrolux_ac commit -m "fix: set correct log levels — move routine messages to debug"
```

---

## Task 3: Feature detection

**Files:**
- Modify: `custom_components/electrolux_ac/hub.py`

After fetching capabilities, compare them against the known set and log any unrecognised keys with a link to the issue tracker. This helps users report unsupported features.

- [ ] **Step 1: Add `KNOWN_CAPABILITIES` constant and detection logic to `hub.py`**

Add this constant near the top of `hub.py`, after the imports:

```python
# Capabilities we handle or knowingly ignore. Anything else is logged as unsupported.
_KNOWN_CAPABILITIES = {
    # Controlled by the climate entity
    "executeCommand", "targetTemperatureC", "fanSpeedSetting",
    "mode", "verticalSwing", "sleepMode",
    # Read-only / exposed as sensors
    "applianceState", "fanSpeedState", "networkInterface", "ambientTemperatureC",
    # Known but not yet implemented
    "alerts", "uiLockMode", "startTime", "stopTime",
}

_ISSUE_TRACKER = "https://github.com/TeroPihlaja/electrolux_ac/issues"
```

Then in `update_appliance_info`, after `self.capabilities = capab`, add:

```python
      unknown = sorted(set(capab.keys()) - _KNOWN_CAPABILITIES)
      for key in unknown:
          _LOGGER.warning(
              "Unsupported capability '%s' found on appliance %s. "
              "Please open an issue at %s so it can be added.",
              key, self._id, _ISSUE_TRACKER,
          )
```

- [ ] **Step 2: Remove the TODO comment from `sensor.py`**

Remove the `# TODO: Add more sensors` block (lines 29–48 of `custom_components/electrolux_ac/sensor.py`). The tracked features are now handled via capability detection.

- [ ] **Step 3: Run tests**

```bash
.venv/bin/pytest tests/ -v
```

Expected: 12 passed.

- [ ] **Step 4: Commit**

```bash
git -C /Users/teropihlaja/dev/electrolux_ac add custom_components/
git -C /Users/teropihlaja/dev/electrolux_ac commit -m "feat: log unsupported capabilities with issue tracker link"
```

---

## Task 4: Add integration icon

**Files:**
- Create: `custom_components/electrolux_ac/icon.png`
- Create: `custom_components/electrolux_ac/icon@2x.png`

The official Electrolux brand already exists in `home-assistant/brands`. Download and use those assets directly — HACS picks up `icon.png` from the component directory automatically.

- [ ] **Step 1: Download the Electrolux brand icons**

```bash
cd /Users/teropihlaja/dev/electrolux_ac/custom_components/electrolux_ac
curl -sL https://raw.githubusercontent.com/home-assistant/brands/master/core_integrations/electrolux/icon.png -o icon.png
curl -sL https://raw.githubusercontent.com/home-assistant/brands/master/core_integrations/electrolux/icon%402x.png -o "icon@2x.png"
```

- [ ] **Step 2: Commit**

```bash
git -C /Users/teropihlaja/dev/electrolux_ac add custom_components/electrolux_ac/icon.png "custom_components/electrolux_ac/icon@2x.png"
git -C /Users/teropihlaja/dev/electrolux_ac commit -m "feat: add Electrolux brand icon"
```

> **Follow-up (after GitHub repo is live):** Submit a PR to `home-assistant/brands` adding `custom_integrations/electrolux_ac/` so the icon appears in the official HA brands index.

---

## Task 5: Create GitHub repo and push

- [ ] **Step 1: Create public GitHub repo**

```bash
gh repo create TeroPihlaja/electrolux_ac --public --description "Home Assistant custom integration for Electrolux portable air conditioners" --source /Users/teropihlaja/dev/electrolux_ac --remote github --push
```

- [ ] **Step 2: Verify the push succeeded**

```bash
gh repo view TeroPihlaja/electrolux_ac --web
```

Expected: GitHub repo page opens showing the restructured code.

---

## Task 6: `hacs.json` and `manifest.json`

**Files:**
- Create: `hacs.json`
- Modify: `custom_components/electrolux_ac/manifest.json`

- [ ] **Step 1: Create `hacs.json` at repo root**

```json
{
  "name": "Electrolux AC",
  "render_readme": true
}
```

- [ ] **Step 2: Update `manifest.json`**

Replace the `documentation` and `issue_tracker` values:

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
  "requirements": ["pyelectroluxocp==0.1.3"],
  "version": "1.0.0"
}
```

Note: `iot_class` changed from `cloud_polling` to `cloud_push` — the integration receives live state via WebSocket, not by polling. Also version changed from `v0.1.0` to `1.0.0` (HACS expects semver without `v` prefix). Also updated `name` to remove "control" for cleaner display.

- [ ] **Step 3: Run tests**

```bash
.venv/bin/pytest tests/ -v
```

Expected: 12 passed.

- [ ] **Step 4: Commit and push to GitHub**

```bash
git -C /Users/teropihlaja/dev/electrolux_ac add hacs.json custom_components/electrolux_ac/manifest.json
git -C /Users/teropihlaja/dev/electrolux_ac commit -m "feat: add hacs.json and fill in manifest.json for HACS publishing"
git -C /Users/teropihlaja/dev/electrolux_ac push github main
```

---

## Task 7: Update server deployment

**Context:** Currently the repo is cloned directly into `config/custom_components/electrolux_ac/`. After the restructure the repo has a `custom_components/electrolux_ac/` subdirectory, so we follow the same pattern as `pyicloud_src`: clone the repo to `/home/crazyguy/homeassistant/electrolux_ac/` and mount the component into the container via `compose.yml`.

- [ ] **Step 1: Clone the GitHub repo to the server**

```bash
ssh crazyguy@home.crazyguy.info "cd /home/crazyguy/homeassistant && git clone git@github.com:TeroPihlaja/electrolux_ac.git"
```

Expected: repo cloned to `/home/crazyguy/homeassistant/electrolux_ac/`.

- [ ] **Step 2: Remove the old git checkout from config**

```bash
ssh crazyguy@home.crazyguy.info "rm -rf /home/crazyguy/homeassistant/config/custom_components/electrolux_ac"
```

- [ ] **Step 3: Add volume mount to `compose.yml`**

In `/home/crazyguy/homeassistant/compose.yml`, add this line under the `homeassistant` service `volumes:` section (after the `/config` line):

```yaml
      - /home/crazyguy/homeassistant/electrolux_ac/custom_components/electrolux_ac:/config/custom_components/electrolux_ac
```

- [ ] **Step 4: Restart HA and verify startup**

```bash
ssh crazyguy@home.crazyguy.info "cd /home/crazyguy/homeassistant && docker compose restart homeassistant && sleep 70 && docker compose logs --since=2m homeassistant 2>&1 | grep -i electrolux"
```

Expected: component loads cleanly, sensors and climate entity appear.

- [ ] **Step 5: Update deploy instructions in CLAUDE.md**

Replace the deploy workflow section in `CLAUDE.md`:

```markdown
## Deploy workflow

1. Make changes and commit locally in `/Users/teropihlaja/dev/electrolux_ac/`
2. Push: `git push github main`
3. Pull on server: `ssh crazyguy@home.crazyguy.info "cd /home/crazyguy/homeassistant/electrolux_ac && git pull"`
4. Restart HA: `ssh crazyguy@home.crazyguy.info "cd /home/crazyguy/homeassistant && docker compose restart homeassistant"`

Always commit first, then push separately.
```

Also update the repo URL at the top:
```
git@github.com:TeroPihlaja/electrolux_ac.git
```

- [ ] **Step 6: Update README.md installation instructions**

Replace the "Via Git" section:

```markdown
### Via Git (recommended for updates)

```bash
cd /home/crazyguy/homeassistant
git clone git@github.com:TeroPihlaja/electrolux_ac.git
```

Then add to `compose.yml` under the homeassistant `volumes:`:
```yaml
- /home/crazyguy/homeassistant/electrolux_ac/custom_components/electrolux_ac:/config/custom_components/electrolux_ac
```

To update:
```bash
cd /home/crazyguy/homeassistant/electrolux_ac && git pull
```
Then restart Home Assistant.
```

- [ ] **Step 7: Commit and push**

```bash
git -C /Users/teropihlaja/dev/electrolux_ac add CLAUDE.md README.md
git -C /Users/teropihlaja/dev/electrolux_ac commit -m "docs: update deployment instructions for GitHub + volume mount workflow"
git -C /Users/teropihlaja/dev/electrolux_ac push github main
```

---

## Task 8: Create first GitHub release

HACS needs at least one release to show version history.

- [ ] **Step 1: Create release v1.0.0**

```bash
gh release create 1.0.0 \
  --repo TeroPihlaja/electrolux_ac \
  --title "v1.0.0 — Initial release" \
  --notes "Initial HACS-compatible release.

**Supported device:** Electrolux COMFORT600 portable AC (PORTABLE_AIR_CONDITIONER)

**Features:**
- Climate entity: on/off, cool/dry/fan-only modes, fan speed, swing, target temperature, sleep mode preset
- Sensors: temperature, filter state, filter runtime, total runtime, compressor state, WiFi RSSI, HEPA filter lifetime"
```

- [ ] **Step 2: Verify release appears on GitHub**

```bash
gh release view 1.0.0 --repo TeroPihlaja/electrolux_ac
```

Expected: release details shown with tag `1.0.0`.

- [ ] **Step 3: Also push to GitLab for backup**

```bash
git -C /Users/teropihlaja/dev/electrolux_ac push origin main
```
