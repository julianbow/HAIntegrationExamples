"""Unified init for Tempest Test integration supporting both local and cloud modes."""

from __future__ import annotations

import asyncio

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_API_TOKEN, EVENT_HOMEASSISTANT_STOP, Platform
from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.device_registry import DeviceEntry
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.start import async_at_started

from .const import DOMAIN, LOGGER, format_dispatch_call

# Try to import the cloud coordinator.
try:
    from .coordinator import WeatherFlowCloudDataUpdateCoordinator
except ImportError:
    WeatherFlowCloudDataUpdateCoordinator = None

# Local imports for UDP-based discovery.
from pyweatherflowudp.client import EVENT_DEVICE_DISCOVERED, WeatherFlowListener
from pyweatherflowudp.device import EVENT_LOAD_COMPLETE, WeatherFlowDevice
from pyweatherflowudp.errors import ListenerError

# For local mode we forward only to sensor.
LOCAL_PLATFORMS: list[Platform] = [Platform.SENSOR]
# For cloud mode we want to forward to both sensor and weather.
CLOUD_PLATFORMS: list[Platform] = [Platform.SENSOR, Platform.WEATHER]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """
    Set up the Tempest Test integration from a config entry.

    Determines if the integration should run in cloud mode (if CONF_API_TOKEN exists)
    or in local mode (no API token) and then forwards the entry to the appropriate platforms.
    """
    if CONF_API_TOKEN in entry.data:
        # Cloud mode.
        if WeatherFlowCloudDataUpdateCoordinator is None:
            LOGGER.error("Cloud coordinator not available.")
            return False
        LOGGER.debug("Setting up Tempest Test in cloud mode.")
        data_coordinator = WeatherFlowCloudDataUpdateCoordinator(hass, entry)
        await data_coordinator.async_config_entry_first_refresh()
        hass.data.setdefault(DOMAIN, {})[entry.entry_id] = data_coordinator
        # Forward the entry to both sensor and weather platforms.
        await hass.config_entries.async_forward_entry_setups(entry, CLOUD_PLATFORMS)
        return True

    # Local mode.
    LOGGER.debug("Setting up Tempest Test in local mode.")
    client = WeatherFlowListener()

    @callback
    def _async_device_discovered(device: WeatherFlowDevice) -> None:
        LOGGER.debug("Local mode: Found device: %s", device)

        @callback
        def _async_add_device_if_started(device: WeatherFlowDevice) -> None:
            async_at_started(
                hass,
                callback(
                    lambda _: async_dispatcher_send(
                        hass, format_dispatch_call(entry), device
                    )
                ),
            )

        entry.async_on_unload(
            device.on(
                EVENT_LOAD_COMPLETE, lambda _: _async_add_device_if_started(device)
            )
        )

    entry.async_on_unload(client.on(EVENT_DEVICE_DISCOVERED, _async_device_discovered))

    try:
        await client.start_listening()
    except ListenerError as ex:
        raise ConfigEntryNotReady from ex

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = client
    # Forward the entry to the sensor platform for local mode.
    await hass.config_entries.async_forward_entry_setups(entry, LOCAL_PLATFORMS)

    async def _async_handle_ha_shutdown(event: Event) -> None:
        """Handle Home Assistant shutdown."""
        await client.stop_listening()

    entry.async_on_unload(
        hass.bus.async_listen(EVENT_HOMEASSISTANT_STOP, _async_handle_ha_shutdown)
    )
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """
    Unload a config entry.

    Unloads the platforms and cleans up integration data based on whether the integration
    is running in cloud mode or local mode.
    """
    if CONF_API_TOKEN in entry.data:
        if unload_ok := await hass.config_entries.async_unload_platforms(
            entry, CLOUD_PLATFORMS
        ):
            hass.data[DOMAIN].pop(entry.entry_id, None)
        return unload_ok
    else:
        if unload_ok := await hass.config_entries.async_unload_platforms(
            entry, LOCAL_PLATFORMS
        ):
            client: WeatherFlowListener = hass.data[DOMAIN].pop(entry.entry_id, None)
            if client:
                await client.stop_listening()
        return unload_ok


async def async_remove_config_entry_device(
    hass: HomeAssistant, config_entry: ConfigEntry, device_entry: DeviceEntry
) -> bool:
    """
    Remove a config entry from a device.

    For local mode, verifies that no devices managed by the integration match the given device entry.
    For cloud mode, adjust as needed.
    """
    if CONF_API_TOKEN in config_entry.data:
        return True
    else:
        client: WeatherFlowListener = hass.data[DOMAIN][config_entry.entry_id]
        return not any(
            identifier
            for identifier in device_entry.identifiers
            if identifier[0] == DOMAIN
            for device in client.devices
            if device.serial_number == identifier[1]
        )
