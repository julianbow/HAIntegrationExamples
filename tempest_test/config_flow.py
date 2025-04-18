# config_flow.py
"""Config flow for Tempest Test integration using PKCE with wrapped token responses."""

from __future__ import annotations

import asyncio
from asyncio import Future
import logging
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.helpers.config_entry_oauth2_flow import (
    AbstractOAuth2FlowHandler,
    LocalOAuth2ImplementationWithPkce,
)

from .const import (
    AUTHORIZE_URL,
    CLIENT_ID,
    DATA_SOURCE,
    DATA_SOURCE_OPTIONS,
    DOMAIN,
    ERROR_MSG_CANNOT_CONNECT,
    ERROR_MSG_NO_DEVICE_FOUND,
    TOKEN_URL,
)

_LOGGER = logging.getLogger(__name__)


class TempestPkceImplementation(LocalOAuth2ImplementationWithPkce):
    """PKCE implementation that normalizes provider token response for HA."""

    async def async_resolve_external_data(self, external_data: Any) -> dict[str, Any]:
        raw_token = await super().async_resolve_external_data(external_data)
        return {
            "access_token": raw_token.get("access_token"),
            "refresh_token": raw_token.get("access_token"),
            "expires_in": int(raw_token.get("expires_in", 3600)),
            "token_type": raw_token.get("token_type", "Bearer"),
        }


async def _async_can_discover_devices() -> bool:
    """Attempt local device discovery via UDP broadcast."""
    _LOGGER.info("[DISCOVERY] Starting local device discovery")
    fut: Future[None] = asyncio.get_running_loop().create_future()

    @callback
    def _found(event_data):
        _LOGGER.info("[DISCOVERY] Device found event fired: %s", event_data)
        if not fut.done():
            fut.set_result(None)

    try:
        from pyweatherflowudp.client import EVENT_DEVICE_DISCOVERED, WeatherFlowListener
        from pyweatherflowudp.errors import ListenerError

        async with WeatherFlowListener() as client, asyncio.timeout(10):
            client.on(EVENT_DEVICE_DISCOVERED, _found)
            await fut
    except asyncio.TimeoutError:
        _LOGGER.warning("[DISCOVERY] Timeout: No device discovered within 10 seconds")
        return False
    except Exception as exc:
        _LOGGER.exception("[DISCOVERY] Unexpected error during discovery: %s", exc)
        raise

    _LOGGER.info("[DISCOVERY] Device discovery successful")
    return True


class ConfigFlow(AbstractOAuth2FlowHandler, domain=DOMAIN):
    """Handle the configuration flow for Tempest Test integration with PKCE."""

    VERSION = 1
    DOMAIN = DOMAIN

    @property
    def logger(self) -> logging.Logger:
        return _LOGGER

    def _data_schema(self) -> vol.Schema:
        """Schema for selecting Local vs. Cloud mode."""
        return vol.Schema(
            {vol.Required(DATA_SOURCE, default="local"): vol.In(DATA_SOURCE_OPTIONS)}
        )

    async def async_step_user(
        self, user_input: dict[str, str] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Let the user choose between Local or Cloud (OAuth2) mode."""
        _LOGGER.info(
            "[STEP_USER] async_step_user called with user_input: %s", user_input
        )

        if user_input is not None:
            if user_input[DATA_SOURCE] == "cloud":
                _LOGGER.info("[STEP_USER] Starting OAuth2 PKCE flow for cloud mode")
                impl = TempestPkceImplementation(
                    self.hass,
                    self.DOMAIN,
                    CLIENT_ID,
                    AUTHORIZE_URL,
                    TOKEN_URL,
                )
                self.flow_impl = impl
                return await self.async_step_auth()

            # Local mode path
            errors: dict[str, str] = {}
            if self._async_current_entries():
                return self.async_abort(reason="single_instance_allowed")
            try:
                found = await _async_can_discover_devices()
            except Exception:
                errors["base"] = ERROR_MSG_CANNOT_CONNECT
            else:
                if not found:
                    errors["base"] = ERROR_MSG_NO_DEVICE_FOUND
            if errors:
                return self.async_show_form(
                    step_id="user", data_schema=self._data_schema(), errors=errors
                )
            return self.async_create_entry(
                title="Tempest Station (Local)", data=user_input
            )

        return self.async_show_form(
            step_id="user", data_schema=self._data_schema(), errors={}
        )

    async def async_oauth_create_entry(
        self, data: dict[str, Any]
    ) -> config_entries.ConfigEntry:
        """Create the config entry after OAuth2 completes."""
        _LOGGER.info("[OAUTH_CREATE_ENTRY] Token exchange complete, data: %s", data)
        return self.async_create_entry(title="Tempest Station (Cloud)", data=data)
