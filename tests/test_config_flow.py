import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from electrolux_group_developer_sdk.client.bad_credentials_exception import BadCredentialsException
from custom_components.electrolux_ac.config_flow import ConfigFlow, InvalidAuth, CannotConnect, validate_input


def _flow():
    flow = ConfigFlow()
    flow.hass = MagicMock()
    flow.context = {}
    return flow


@pytest.mark.asyncio
async def test_config_flow_maps_invalid_auth_to_invalid_auth_error_key():
    flow = _flow()
    with patch(
        "custom_components.electrolux_ac.config_flow.validate_input",
        side_effect=InvalidAuth,
    ):
        result = await flow.async_step_user(
            {"api_key": "k", "access_token": "a", "refresh_token": "r"}
        )
    assert result["errors"]["base"] == "invalid_auth"


@pytest.mark.asyncio
async def test_config_flow_maps_cannot_connect_to_cannot_connect_error_key():
    flow = _flow()
    with patch(
        "custom_components.electrolux_ac.config_flow.validate_input",
        side_effect=CannotConnect,
    ):
        result = await flow.async_step_user(
            {"api_key": "k", "access_token": "a", "refresh_token": "r"}
        )
    assert result["errors"]["base"] == "cannot_connect"


@pytest.mark.asyncio
async def test_validate_input_raises_invalid_auth_on_bad_credentials():
    with patch("custom_components.electrolux_ac.config_flow.ApplianceClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.test_connection = AsyncMock(side_effect=BadCredentialsException("bad"))
        mock_client_cls.return_value = mock_client
        with pytest.raises(InvalidAuth):
            await validate_input(MagicMock(), {"api_key": "k", "access_token": "a", "refresh_token": "r"})


@pytest.mark.asyncio
async def test_validate_input_returns_email_as_title():
    with patch("custom_components.electrolux_ac.config_flow.ApplianceClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.test_connection = AsyncMock()
        mock_email = MagicMock()
        mock_email.email = "user@example.com"
        mock_client.get_user_email = AsyncMock(return_value=mock_email)
        mock_client_cls.return_value = mock_client
        result = await validate_input(MagicMock(), {"api_key": "k", "access_token": "a", "refresh_token": "r"})
    assert result["title"] == "user@example.com"


@pytest.mark.asyncio
async def test_reauth_confirm_updates_entry_on_success():
    flow = _flow()
    reauth_entry = MagicMock()
    reauth_entry.unique_id = "user@example.com"
    flow._get_reauth_entry = MagicMock(return_value=reauth_entry)
    flow.async_update_reload_and_abort = MagicMock(return_value={"type": "abort", "reason": "reauth_successful"})
    with patch(
        "custom_components.electrolux_ac.config_flow.validate_input",
        return_value={"title": "user@example.com"},
    ):
        result = await flow.async_step_reauth_confirm(
            {"api_key": "new_k", "access_token": "new_a", "refresh_token": "new_r"}
        )
    flow.async_update_reload_and_abort.assert_called_once_with(
        reauth_entry,
        data_updates={"api_key": "new_k", "access_token": "new_a", "refresh_token": "new_r"},
    )
    assert result["reason"] == "reauth_successful"


@pytest.mark.asyncio
async def test_reauth_confirm_shows_error_on_invalid_auth():
    flow = _flow()
    with patch(
        "custom_components.electrolux_ac.config_flow.validate_input",
        side_effect=InvalidAuth,
    ):
        result = await flow.async_step_reauth_confirm(
            {"api_key": "k", "access_token": "a", "refresh_token": "r"}
        )
    assert result["errors"]["base"] == "invalid_auth"


@pytest.mark.asyncio
async def test_reauth_confirm_rejects_credentials_for_a_different_account():
    """Entering a different Electrolux account's valid credentials during reauth must
    not silently repoint the entry (and all its entities) at that other account."""
    flow = _flow()
    reauth_entry = MagicMock()
    reauth_entry.unique_id = "original@example.com"
    flow._get_reauth_entry = MagicMock(return_value=reauth_entry)
    flow.async_update_reload_and_abort = MagicMock()
    with patch(
        "custom_components.electrolux_ac.config_flow.validate_input",
        return_value={"title": "someone_else@example.com"},
    ):
        result = await flow.async_step_reauth_confirm(
            {"api_key": "new_k", "access_token": "new_a", "refresh_token": "new_r"}
        )
    assert result["errors"]["base"] == "reauth_account_mismatch"
    flow.async_update_reload_and_abort.assert_not_called()


@pytest.mark.asyncio
async def test_reauth_confirm_allows_same_account_when_entry_has_no_unique_id():
    """Entries created before unique_id support existed have unique_id=None; reauth for
    those must not be blocked since there's nothing to compare against."""
    flow = _flow()
    reauth_entry = MagicMock()
    reauth_entry.unique_id = None
    flow._get_reauth_entry = MagicMock(return_value=reauth_entry)
    flow.async_update_reload_and_abort = MagicMock(return_value={"type": "abort", "reason": "reauth_successful"})
    with patch(
        "custom_components.electrolux_ac.config_flow.validate_input",
        return_value={"title": "user@example.com"},
    ):
        result = await flow.async_step_reauth_confirm(
            {"api_key": "new_k", "access_token": "new_a", "refresh_token": "new_r"}
        )
    flow.async_update_reload_and_abort.assert_called_once()
    assert result["reason"] == "reauth_successful"


@pytest.mark.asyncio
async def test_user_step_sets_unique_id_and_aborts_if_already_configured():
    flow = _flow()
    flow.async_set_unique_id = AsyncMock()
    flow._abort_if_unique_id_configured = MagicMock()
    with patch(
        "custom_components.electrolux_ac.config_flow.validate_input",
        return_value={"title": "user@example.com"},
    ):
        result = await flow.async_step_user(
            {"api_key": "k", "access_token": "a", "refresh_token": "r"}
        )
    flow.async_set_unique_id.assert_called_once_with("user@example.com")
    flow._abort_if_unique_id_configured.assert_called_once()
    assert result["title"] == "user@example.com"
