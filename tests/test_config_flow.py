import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from custom_components.electrolux_ac.config_flow import ConfigFlow, InvalidAuth


@pytest.mark.asyncio
async def test_config_flow_maps_invalid_auth_to_invalid_auth_error_key():
    flow = ConfigFlow()
    flow.hass = MagicMock()
    flow.hass.config.country = "fi"
    flow.context = {}

    with patch(
        "custom_components.electrolux_ac.config_flow.validate_input",
        side_effect=InvalidAuth,
    ):
        result = await flow.async_step_user(
            {"email": "x@x.com", "password": "wrong", "country_code": "fi"}
        )

    assert result["errors"]["base"] == "invalid_auth"
