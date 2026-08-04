from unittest.mock import MagicMock, AsyncMock, patch
import pytest
from homeassistant.exceptions import ConfigEntryAuthFailed
from electrolux_group_developer_sdk.client.bad_credentials_exception import BadCredentialsException
from custom_components.electrolux_ac import async_setup_entry, async_unload_entry, DOMAIN


@pytest.mark.asyncio
async def test_setup_entry_raises_auth_failed_when_credentials_revoked():
    """Reproduces the Critical bug: discover_appliances() alone can't distinguish
    a dead refresh token from a transient failure, so test_connection() must run
    first and its BadCredentialsException must propagate as ConfigEntryAuthFailed."""
    hass = MagicMock()
    hass.data = {}
    entry = MagicMock()
    entry.entry_id = "test_entry_id"

    with patch("custom_components.electrolux_ac.hub.Hub") as mock_hub_cls:
        mock_hub = mock_hub_cls.return_value
        mock_hub.test_connection = AsyncMock(side_effect=BadCredentialsException("dead token"))
        mock_hub.disconnect = AsyncMock()

        with pytest.raises(ConfigEntryAuthFailed):
            await async_setup_entry(hass, entry)

    mock_hub.disconnect.assert_called_once()


@pytest.mark.asyncio
async def test_unload_entry_unloads_platforms_before_disconnecting_hub():
    """Entities must be removed before the hub disconnects, so a still-live entity can't
    trigger execute_command() against an already-nulled client during unload."""
    call_order = []

    hass = MagicMock()
    entry = MagicMock()
    entry.entry_id = "test_entry_id"

    hub = MagicMock()
    hub.coordinator.async_shutdown = AsyncMock(side_effect=lambda: call_order.append("coordinator_shutdown"))
    hub.disconnect = AsyncMock(side_effect=lambda: call_order.append("hub_disconnect"))
    hass.data = {DOMAIN: {"test_entry_id": hub}}

    async def unload_platforms(_entry, _platforms):
        call_order.append("unload_platforms")
        return True

    hass.config_entries.async_unload_platforms = AsyncMock(side_effect=unload_platforms)

    result = await async_unload_entry(hass, entry)

    assert result is True
    assert call_order == ["unload_platforms", "coordinator_shutdown", "hub_disconnect"]
    assert "test_entry_id" not in hass.data[DOMAIN]
