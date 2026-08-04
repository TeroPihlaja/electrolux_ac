# Migrate to the Official Electrolux Developer SDK

## Goal

Replace `pyelectroluxocp` (archived upstream, patched via a private fork) with `electrolux-group-developer-sdk`, the officially maintained Python client for Electrolux's Developer Portal API. Removes the dependency on an unmaintained reverse-engineered library and its associated operational risk (see the refresh-token-lockout incident of 2026-07-28 through 2026-08-04), in exchange for a one-time manual credential setup.

This is a breaking change to how the integration authenticates. Acceptable because there is currently one user (the maintainer), who will re-enter credentials once after upgrading.

## Why

- `pyelectroluxocp`'s upstream repo is archived; its own README points users to this official SDK.
- The official SDK is actively maintained by Electrolux's Developer Portal team, has a built-in rate limiter, and exposes a clear `BadCredentialsException` distinct from transient connectivity failures — the exact signal the old library was missing when its refresh token was silently revoked and it retried forever.
- Confirmed via `AZUL` (this device's project name) being explicitly mapped to the SDK's `ACAppliance` class — first-party support for this exact model.

## Scope boundary

`hub.py` and `config_flow.py` are rewritten. `climate.py` and `sensor.py` are **not** expected to need a rewrite: the SDK's `ApplianceDetails.capabilities` and `ApplianceState.properties` are raw `dict[str, Any]`, matching the shape the old API already returned (same underlying Electrolux data model, different transport). `Appliance` continues to expose `._states` (dict) and `.capabilities` (dict) exactly as it does today.

One narrow exception: the SDK's own test fixtures use uppercase enum values (`"mode": "OFF"`, `"temperatureRepresentation": "CELSIUS"`) where the old API used lowercase (`"mode": "cool"`, confirmed from live logs). Both `climate.py` and `sensor.py` do exact-lowercase string comparisons against `_states` values (e.g. `_states.get('temperatureRepresentation') == 'fahrenheit'`). To be correct regardless of which casing the real API actually returns, every such comparison in both files is made case-insensitive (`.lower()` the retrieved value before comparing). This is the one change to those two files.

## Authentication model change

| | Old (`pyelectroluxocp`) | New (`electrolux-group-developer-sdk`) |
|---|---|---|
| Config entry fields | `email`, `password`, `country_code` | `api_key`, `access_token`, `refresh_token` |
| Credential source | Same login as the Electrolux mobile app | Manually generated once via [developer.electrolux.one](https://developer.electrolux.one/) (existing Electrolux account login, then create an API key and generate a token pair in the portal UI) |
| API host | `api.eu.ocp.electrolux.one` (consumer OCP) | `api.developer.electrolux.one` (developer portal) |

`country_code` is dropped — the developer API has a single fixed host, no per-region identity-provider lookup.

## `hub.py` design

**Client construction**

```python
token_manager = TokenManager(
    access_token=entry.data["access_token"],
    refresh_token=entry.data["refresh_token"],
    api_key=entry.data["api_key"],
    on_token_update=self._persist_tokens,
)
self._client = ApplianceClient(token_manager=token_manager)
```

**Token persistence** — `on_token_update(access_token, refresh_token, api_key)` fires on every token rotation (including once at construction). `Hub._persist_tokens` calls `hass.config_entries.async_update_entry(entry, data={**entry.data, "access_token": access_token, "refresh_token": refresh_token})` so rotated tokens survive a restart. Getting this right is the direct lesson from the 2026-07-28 incident.

**Push updates** — `ApplianceClient.start_event_stream(do_on_livestream_opening_list=[self._full_refresh])` runs as a background task (`asyncio.ensure_future`, same pattern as today's `watch_for_appliance_state_updates`). Register a per-appliance listener via `add_listener(appliance_id, callback)`; the callback applies the SDK's `apply_sse_update(state, event)` helper and feeds the resulting `.properties["reported"]` dict into the existing `_states` update + `publish_updates()` path. `_full_refresh` (passed via `do_on_livestream_opening_list`) re-fetches full appliance state on every (re)connection, matching today's "refetch on reconnect" behavior.

`start_event_stream`'s internal reconnect loop catches every exception (including a permanently dead refresh token) and retries after a fixed 10s sleep — it never surfaces auth failure. Reauth detection is therefore **not** wired through this path.

**Periodic safety-net poll** — a `DataUpdateCoordinator` runs every 10 minutes (matching today's `refresh_connection_state` cadence) and does two things in order:

1. Calls `ApplianceClient.test_connection()` first. Unlike the SSE path, this explicitly distinguishes `BadCredentialsException` (dead/invalid tokens) from `FailedConnectionException` (transient connectivity). On `BadCredentialsException`, the coordinator raises `ConfigEntryAuthFailed`, Home Assistant's standard mechanism for triggering a reauth prompt.
2. On success, fetches full appliance data (details + state) and merges it into `_states` / `publish_updates()` — the actual "catch anything the SSE stream missed" safety net, not just a connectivity check.

This coordinator is the only part of this integration using `DataUpdateCoordinator` — introduced specifically because it's the idiomatic way to surface `ConfigEntryAuthFailed` outside of initial setup.

**Commands** — `Appliance.execute_command` becomes `self.hub._client.send_command(appliance_id, {command: value})`.

## `config_flow.py` design

- Form fields: `api_key`, `access_token`, `refresh_token` (all required strings), with a description/link pointing to the developer portal for generating them.
- Validation: construct `ApplianceClient`/`TokenManager` with the submitted values and call `test_connection()`. `BadCredentialsException` maps to the existing `invalid_auth` error key (already used for the old flow's auth failures).
- Add `async_step_reauth` / `async_step_reauth_confirm`: when the coordinator raises `ConfigEntryAuthFailed`, the user is prompted to paste a freshly generated token pair (same three fields), and the config entry is updated in place rather than requiring delete-and-re-add.

## Testing

- `tests/test_hub.py`: mock `ApplianceClient` and `TokenManager` instead of `OneAppApi`. Cover: token persistence on rotation, SSE event → `_states` update, coordinator raising `ConfigEntryAuthFailed` on `BadCredentialsException` from `test_connection()`.
- `tests/test_config_flow.py`: mock `test_connection()` success/`BadCredentialsException` paths for both initial setup and reauth.
- `requirements_test.txt` / local `.venv` gain `electrolux-group-developer-sdk` (PyPI, confirmed installable, latest 0.6.1) in place of the `pyelectroluxocp` fork.

## Rollout

- Build on a feature branch; `main` is what the live HA server tracks, so nothing merges until it's verified end-to-end against the real AC.
- `manifest.json`: swap `requirements` to `electrolux-group-developer-sdk` (pinned version), drop the `pyelectroluxocp` git+https fork reference entirely, bump to a new major version (breaking config format), `iot_class` stays `cloud_push`.
- No migration shim for the old `email`/`password` config entry — as sole user, delete and re-add the integration once after upgrading, entering the newly generated `api_key`/`access_token`/`refresh_token`.
- The `pyelectroluxocp` fork and its in-flight PEP 541 name-claim request become optional/decoupled from this integration — no longer required for `electrolux_ac` to work, though the maintainer may still pursue it separately to help other `pyelectroluxocp` users.
- The pending HACS default-catalog submission (PR #8376) is unaffected by this migration's timing; it can continue independently since it targets the already-released `v1.0.3`.
