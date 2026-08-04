from unittest.mock import MagicMock, AsyncMock
import pytest
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import UpdateFailed
from electrolux_group_developer_sdk.client.bad_credentials_exception import BadCredentialsException
from custom_components.electrolux_ac.coordinator import ElectroluxSafetyNetCoordinator


def make_coordinator(hub=None):
    hass = MagicMock()
    entry = MagicMock()
    hub = hub or MagicMock()
    return ElectroluxSafetyNetCoordinator(hass, entry, hub)


@pytest.mark.asyncio
async def test_update_data_raises_config_entry_auth_failed_on_bad_credentials():
    hub = MagicMock()
    hub.test_connection = AsyncMock(side_effect=BadCredentialsException("dead token"))
    coordinator = make_coordinator(hub)
    with pytest.raises(ConfigEntryAuthFailed):
        await coordinator._async_update_data()


@pytest.mark.asyncio
async def test_update_data_calls_full_refresh_after_successful_connection_test():
    hub = MagicMock()
    hub.test_connection = AsyncMock()
    hub.full_refresh = AsyncMock()
    coordinator = make_coordinator(hub)
    await coordinator._async_update_data()
    hub.full_refresh.assert_called_once()


@pytest.mark.asyncio
async def test_update_data_does_not_call_full_refresh_on_bad_credentials():
    hub = MagicMock()
    hub.test_connection = AsyncMock(side_effect=BadCredentialsException("dead token"))
    hub.full_refresh = AsyncMock()
    coordinator = make_coordinator(hub)
    with pytest.raises(ConfigEntryAuthFailed):
        await coordinator._async_update_data()
    hub.full_refresh.assert_not_called()


@pytest.mark.asyncio
async def test_update_data_raises_update_failed_on_non_auth_connection_error():
    hub = MagicMock()
    hub.test_connection = AsyncMock(side_effect=RuntimeError("network blip"))
    coordinator = make_coordinator(hub)
    with pytest.raises(UpdateFailed):
        await coordinator._async_update_data()


@pytest.mark.asyncio
async def test_update_data_raises_update_failed_when_full_refresh_fails():
    """A non-auth failure from full_refresh() must be classified as UpdateFailed (so the
    coordinator handles it as an expected, retryable failure) rather than propagate as
    an unclassified exception."""
    hub = MagicMock()
    hub.test_connection = AsyncMock()
    hub.full_refresh = AsyncMock(side_effect=RuntimeError("network blip"))
    coordinator = make_coordinator(hub)
    with pytest.raises(UpdateFailed):
        await coordinator._async_update_data()
