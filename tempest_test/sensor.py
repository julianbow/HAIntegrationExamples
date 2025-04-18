"""
sensor.py
Dispatch to local or cloud sensors for Tempest Test integration, with logging.
"""

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

# If your const.py defines CONF_ACCESS_TOKEN, import it; otherwise adapt to your key
# Detect cloud mode by presence of `token` in entry.data

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities,
) -> None:
    """Set up sensors for Tempest Test, selecting cloud vs. local mode."""
    _LOGGER.info("Tempest Test async_setup_entry called; entry.data=%s", entry.data)

    # Determine if we're in cloud or local mode based on presence of access token
    if "token" in entry.data:
        _LOGGER.info("Tempest Test running in CLOUD mode; loading cloud sensors.")
        from . import sensor_cloud

        await sensor_cloud.async_setup_entry(hass, entry, async_add_entities)
        _LOGGER.info("Tempest Test cloud sensors setup complete.")
    else:
        _LOGGER.info("Tempest Test running in LOCAL mode; loading local sensors.")
        from . import sensor_local

        await sensor_local.async_setup_entry(hass, entry, async_add_entities)
        _LOGGER.info("Tempest Test local sensors setup complete.")
