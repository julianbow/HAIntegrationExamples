"""Entry point for Tempest Test sensors."""

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities,
) -> None:
    """Set up sensors for Tempest Test, selecting cloud vs. local mode."""

    # Determine if we're in cloud or local mode based on presence of access token
    if "token" in entry.data:
        from . import sensor_cloud

        await sensor_cloud.async_setup_entry(hass, entry, async_add_entities)
    else:
        from . import sensor_local

        await sensor_local.async_setup_entry(hass, entry, async_add_entities)
