"""Config flow for Tempest Test integration supporting both local and cloud modes with OAuth2 PKCE."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from pyweatherflowudp.client import EVENT_DEVICE_DISCOVERED, WeatherFlowListener
from pyweatherflowudp.errors import ListenerError
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


async def _async_can_discover_devices() -> bool:
    """Attempt local device discovery via UDP broadcast."""
    _LOGGER.info("[DISCOVERY] Starting local device discovery")
    fut: asyncio.Future[None] = asyncio.get_running_loop().create_future()

    @callback
    def _found(event_data: Any) -> None:
        _LOGGER.info("[DISCOVERY] Device found event fired: %s", event_data)
        if not fut.done():
            fut.set_result(None)

    try:
        async with WeatherFlowListener() as client, asyncio.timeout(10):
            client.on(EVENT_DEVICE_DISCOVERED, _found)
            await fut
    except TimeoutError:
        _LOGGER.warning("[DISCOVERY] No device discovered within timeout")
        return False
    except Exception as exc:
        _LOGGER.exception("[DISCOVERY] Error during discovery: %s", exc)
        raise

    _LOGGER.info("[DISCOVERY] Device discovery successful")
    return True


class TempestPkceImplementation(LocalOAuth2ImplementationWithPkce):
    """PKCE implementation that normalizes provider token response for HA."""

    async def async_resolve_external_data(self, external_data: Any) -> dict[str, Any]:
        raw = await super().async_resolve_external_data(external_data)
        return {
            "access_token": raw.get("access_token"),
            "refresh_token": raw.get("access_token"),
            "expires_in": int(raw.get("expires_in", 3600)),
            "token_type": raw.get("token_type", "Bearer"),
        }


class ConfigFlow(AbstractOAuth2FlowHandler, domain=DOMAIN):
    """Handle the configuration flow, allowing one local and one cloud entry."""

    VERSION = 1
    DOMAIN = DOMAIN

    def _data_schema(self) -> vol.Schema:
        return vol.Schema(
            {vol.Required(DATA_SOURCE, default="local"): vol.In(DATA_SOURCE_OPTIONS)}
        )

    async def async_step_user(
        self, user_input: dict[str, str] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Let the user choose between Local or Cloud mode."""
        _LOGGER.info(
            "[STEP_USER] async_step_user called with user_input: %s", user_input
        )

        if user_input is not None:
            mode = user_input[DATA_SOURCE]
            if mode == "cloud":
                # Prevent duplicate cloud entries
                existing = [
                    e
                    for e in self._async_current_entries()
                    if e.data.get(DATA_SOURCE) == "cloud"
                ]
                if existing:
                    return self.async_abort(reason="single_instance_allowed")

                impl = TempestPkceImplementation(
                    self.hass,
                    self.DOMAIN,
                    CLIENT_ID,
                    AUTHORIZE_URL,
                    TOKEN_URL,
                )
                self.flow_impl = impl
                return await self.async_step_auth()

            # Local mode
            existing = [
                e
                for e in self._async_current_entries()
                if e.data.get(DATA_SOURCE) == "local"
            ]
            if existing:
                return self.async_abort(reason="single_instance_allowed")

            errors: dict[str, str] = {}
            try:
                found = await _async_can_discover_devices()
            except Exception:
                errors["base"] = ERROR_MSG_CANNOT_CONNECT
            else:
                if not found:
                    errors["base"] = ERROR_MSG_NO_DEVICE_FOUND

            if errors:
                _LOGGER.warning("[STEP_USER] Local discovery errors: %s", errors)
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
