"""Config flow for Electrolux AC integration."""
from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol
import aiohttp

from homeassistant import config_entries, exceptions
from homeassistant.core import HomeAssistant

from .const import DOMAIN, CONF_COUNTRY_CODE
from .hub import Hub

_LOGGER = logging.getLogger(__name__)


async def validate_input(hass: HomeAssistant, data: dict) -> dict[str, Any]:
    hub = Hub(hass, data["email"], data["password"], data[CONF_COUNTRY_CODE])
    try:
        result = await hub.test_connection()
        if not result:
            raise CannotConnect
    except aiohttp.client_exceptions.ClientResponseError:
        raise InvalidAuth
    finally:
        await hub.disconnect()

    return {"title": data["email"]}


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Electrolux AC."""

    VERSION = 1

    async def async_step_user(self, user_input=None):
        """Handle the initial step."""
        default_country = (self.hass.config.country or "fi").lower()

        errors = {}
        if user_input is not None:
            try:
                info = await validate_input(self.hass, user_input)
                return self.async_create_entry(title=info["title"], data=user_input)
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"

        schema = vol.Schema({
            vol.Required("email"): str,
            vol.Required("password"): str,
            vol.Required(CONF_COUNTRY_CODE, default=default_country): str,
        })

        return self.async_show_form(
            step_id="user", data_schema=schema, errors=errors
        )


class CannotConnect(exceptions.HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidAuth(exceptions.HomeAssistantError):
    """Error to indicate there is an invalid credentials."""
