"""Config flow for Electrolux AC integration."""
from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant import config_entries, exceptions
from homeassistant.core import HomeAssistant

from electrolux_group_developer_sdk.auth.token_manager import TokenManager
from electrolux_group_developer_sdk.client.appliance_client import ApplianceClient
from electrolux_group_developer_sdk.client.bad_credentials_exception import BadCredentialsException

from .const import DOMAIN, CONF_API_KEY, CONF_ACCESS_TOKEN, CONF_REFRESH_TOKEN

_LOGGER = logging.getLogger(__name__)

DEVELOPER_PORTAL_URL = "https://developer.electrolux.one/"

_SCHEMA = vol.Schema({
    vol.Required(CONF_API_KEY): str,
    vol.Required(CONF_ACCESS_TOKEN): str,
    vol.Required(CONF_REFRESH_TOKEN): str,
})


async def validate_input(hass: HomeAssistant, data: dict) -> dict[str, Any]:
    token_manager = TokenManager(
        access_token=data[CONF_ACCESS_TOKEN],
        refresh_token=data[CONF_REFRESH_TOKEN],
        api_key=data[CONF_API_KEY],
    )
    client = ApplianceClient(token_manager=token_manager)
    try:
        await client.test_connection()
        email = await client.get_user_email()
    except BadCredentialsException as ex:
        raise InvalidAuth from ex
    except Exception as ex:
        raise CannotConnect from ex

    return {"title": email.email}


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Electrolux AC."""

    VERSION = 2

    async def async_step_user(self, user_input=None):
        """Handle the initial step."""
        errors = {}
        if user_input is not None:
            try:
                info = await validate_input(self.hass, user_input)
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                await self.async_set_unique_id(info["title"])
                self._abort_if_unique_id_configured()
                return self.async_create_entry(title=info["title"], data=user_input)

        return self.async_show_form(
            step_id="user",
            data_schema=_SCHEMA,
            errors=errors,
            description_placeholders={"portal_url": DEVELOPER_PORTAL_URL},
        )

    async def async_step_reauth(self, entry_data: dict[str, Any]):
        """Handle reauthorization triggered by ConfigEntryAuthFailed."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(self, user_input=None):
        """Ask the user for a fresh api_key/access_token/refresh_token."""
        errors = {}
        if user_input is not None:
            try:
                info = await validate_input(self.hass, user_input)
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                reauth_entry = self._get_reauth_entry()
                if reauth_entry.unique_id is not None and info["title"] != reauth_entry.unique_id:
                    errors["base"] = "reauth_account_mismatch"
                else:
                    return self.async_update_reload_and_abort(
                        reauth_entry, data_updates=user_input
                    )

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=_SCHEMA,
            errors=errors,
            description_placeholders={"portal_url": DEVELOPER_PORTAL_URL},
        )


class CannotConnect(exceptions.HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidAuth(exceptions.HomeAssistantError):
    """Error to indicate there is an invalid credentials."""
