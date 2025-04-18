from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities
) -> None:
    if "api_token" in entry.data:
        # Cloud mode: delegate to sensor_cloud.py
        from . import sensor_cloud

        await sensor_cloud.async_setup_entry(hass, entry, async_add_entities)
    else:
        # Local mode: delegate to sensor_local.py
        from . import sensor_local

        await sensor_local.async_setup_entry(hass, entry, async_add_entities)
