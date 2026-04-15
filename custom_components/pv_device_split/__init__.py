"""Solar Load Split custom integration."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EVENT_HOMEASSISTANT_STARTED
from homeassistant.core import HomeAssistant

from .const import CONF_DEVICE_POWER, DOMAIN, PLATFORMS
from .discovery import (
    async_schedule_power_discovery,
    async_schedule_power_discovery_retries,
)


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Set up Solar Load Split."""
    hass.bus.async_listen_once(
        EVENT_HOMEASSISTANT_STARTED,
        lambda event: async_schedule_power_discovery_retries(hass),
    )
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Solar Load Split from a config entry."""
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = entry.data

    async_schedule_power_discovery(hass)
    async_schedule_power_discovery_retries(hass)

    if CONF_DEVICE_POWER not in entry.data:
        return True

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if CONF_DEVICE_POWER not in entry.data:
        hass.data[DOMAIN].pop(entry.entry_id, None)
        return True

    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id, None)

    return unload_ok
