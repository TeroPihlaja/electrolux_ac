# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

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
