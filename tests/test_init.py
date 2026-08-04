from unittest.mock import MagicMock, AsyncMock, patch
import pytest
from homeassistant.exceptions import ConfigEntryAuthFailed
from electrolux_group_developer_sdk.client.bad_credentials_exception import BadCredentialsException
from custom_components.electrolux_ac import async_setup_entry


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
