# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

## [1.2.0] - 2026-08-04

### Added
- Reauthentication now sets and validates a unique ID per Electrolux account, rejecting credentials for a different account instead of silently repointing an existing entry (and its entities) at it.

### Fixed
- `min_temp`/`max_temp` always read the Celsius capability regardless of the device's configured unit, giving Fahrenheit devices a wrong slider range.
- `appliance_info` could revert to `None` on a transient refresh gap (SSE reconnect / 10-minute safety-net poll), crashing `device_info` on the next read.
- Unload could race a live entity's service call against an already-disconnected hub; platforms now unload before the hub disconnects, and `execute_command`/`full_refresh` no longer raise `AttributeError` if the client is already gone.
- Appliances with valid state but transiently-missing capability details were skipped from setup permanently instead of just missing optional capability data.
- The safety-net coordinator now classifies non-auth connectivity failures as `UpdateFailed` instead of letting them propagate unclassified.
- Config flow descriptions no longer embed raw URLs (fixes Hassfest translation validation).

## [1.1.0] - 2026-08-04

### Changed
- **Breaking:** migrated from `pyelectroluxocp` (archived upstream) to the officially maintained `electrolux-group-developer-sdk`. Authentication now uses an API key + access/refresh token pair generated at https://developer.electrolux.one/ instead of your Electrolux app email/password. Existing installs must remove and re-add the integration with the new credentials.
- Push updates now arrive via Server-Sent Events instead of WebSocket (same real-time behavior, different transport).
- Added a periodic (10 min) safety-net check that distinguishes invalid credentials from transient connectivity issues and triggers Home Assistant's reauth flow when credentials are revoked — the underlying reliability gap behind the 2026-07-28 outage.

### Fixed
- Commands (swing mode, fan speed, HVAC mode, sleep preset) now send uppercase values matching the appliance's capability schema (e.g. `verticalSwing: "ON"`/`"OFF"`). The new API strictly validates against the schema and rejects lowercase values with a 406; the old API silently accepted them.
- `verticalSwing` and `sleepMode` don't push live via Server-Sent Events on this device — the climate entity now reflects a confirmed successful command locally instead of waiting for the next poll (up to 10 minutes). A later push or poll still overwrites this if it ever disagrees with the device.

## [1.0.3] - 2026-08-04

### Added
- `LICENSE` file (MIT) at repository root, required for HACS default catalog submission

### Fixed
- Integration could become permanently stuck offline after the Electrolux cloud account's refresh token was revoked: the underlying `pyelectroluxocp` client retried the same dead refresh token forever instead of falling back to a fresh login, and retried at a fixed 5-second interval with no backoff, which kept re-triggering Electrolux's API rate limiting indefinitely. Since `pyelectroluxocp` is archived upstream, `manifest.json` now pins a patched fork ([TeroPihlaja/py-electrolux-ocp](https://github.com/TeroPihlaja/py-electrolux-ocp)) instead of the dead PyPI release.

## [1.0.2] - 2026-06-11

### Fixed
- Crash on startup when API response is missing `applianceData` key (`discover_appliances`)
- Silent `IndexError` when `get_appliances_info` returns an empty list, which left `appliance_info` as `None` and caused a downstream crash
- `async_turn_on` and `async_turn_off` no longer directly mutate internal device state — state is now authoritative from the WebSocket only
- `async_set_temperature` no longer raises `KeyError` when called without a temperature value (e.g. range-only thermostat calls)
- Temperature unit now defaults to Celsius when `temperatureRepresentation` is absent from device state (previously defaulted to Fahrenheit)
- Authentication failure in config flow now shows "Invalid credentials" instead of "Unable to connect"

### Changed
- Connection state polling interval reduced from 30 minutes to 10 minutes for faster offline detection
- `wait_for_state` now returns immediately if state is already populated, avoiding a redundant 5-second delay on second platform setup

### Refactored
- Removed redundant `asyncio.ensure_future` wrapper in `execute_command` (replaced with plain `await`)
- Deduplicated seconds-to-hours converter lambda in sensor setup

## [1.0.1] - 2026-06-10

### Added
- Brand assets (`brand/icon.png`, `brand/icon@2x.png`) for HACS validation
- HACS and Hassfest validation CI workflows

### Removed
- GitLab CI configuration files

## [1.0.0] - 2026-06-10

Initial release.

### Added
- Climate entity with On/Off, Cool, Dry, and Fan Only modes
- Fan speed control (Auto, Low, Medium, High)
- Vertical swing control
- Target temperature (°C/°F)
- Sleep mode preset
- Ambient temperature sensor
- Filter state sensor (`good` / `clean` = needs cleaning)
- Filter runtime sensor (hours)
- Total compressor runtime sensor (hours)
- Compressor state sensor
- WiFi signal strength sensor (dBm)
- HEPA filter lifetime sensor
- Alerts sensor with warning log on active alerts
- Online status detection with 30-minute polling fallback
- Configurable country code in config flow
- Support for Electrolux OneApp OCP API via `pyelectroluxocp`
