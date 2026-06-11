# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

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
