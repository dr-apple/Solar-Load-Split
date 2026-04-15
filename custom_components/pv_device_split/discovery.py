"""Discovery helpers for Solar Load Split."""

from __future__ import annotations

from dataclasses import dataclass

from homeassistant import config_entries
from homeassistant.const import (
    ATTR_DEVICE_CLASS,
    ATTR_FRIENDLY_NAME,
    ATTR_UNIT_OF_MEASUREMENT,
    CONF_NAME,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.event import async_call_later

from .const import (
    CONF_DEVICE_POWER,
    CONF_ENABLE_DISCOVERY,
    CONF_GRID_POWER,
    CONF_INVERT_GRID,
    DEFAULT_NAME,
    DOMAIN,
)

POWER_UNITS = {"W", "kW"}
GRID_HINTS = (
    "grid",
    "netz",
    "meter",
    "smart_meter",
    "utility",
    "stromzaehler",
    "stromzähler",
    "einspeis",
    "bezug",
)


@dataclass(frozen=True)
class PowerCandidate:
    """A candidate power sensor."""

    entity_id: str
    name: str
    is_grid: bool


@callback
def async_schedule_power_discovery(hass: HomeAssistant) -> None:
    """Schedule a scan for useful power sensors."""
    hass.async_create_task(_async_discover_power_pair(hass))


@callback
def async_schedule_power_discovery_retries(hass: HomeAssistant) -> None:
    """Schedule several scans while Home Assistant finishes restoring states."""
    for delay in (5, 30, 120):
        async_call_later(
            hass,
            delay,
            lambda now: async_schedule_power_discovery(hass),
        )


async def _async_discover_power_pair(hass: HomeAssistant) -> None:
    """Start discovery flows for likely device/grid pairs."""
    grid_entries = _grid_source_entries(hass)
    if not grid_entries:
        return

    candidates = _power_candidates(hass)
    device_candidates = [candidate for candidate in candidates if not candidate.is_grid]

    for grid_entry in grid_entries:
        grid_power = grid_entry.data[CONF_GRID_POWER]
        for device_candidate in device_candidates:
            if device_candidate.entity_id == grid_power:
                continue

            if _is_configured(hass, device_candidate.entity_id, grid_power):
                continue

            unique_id = _pair_unique_id(device_candidate.entity_id, grid_power)
            if _discovery_flow_in_progress(hass, unique_id):
                continue

            await hass.config_entries.flow.async_init(
                DOMAIN,
                context={
                    "source": config_entries.SOURCE_DISCOVERY,
                    "unique_id": unique_id,
                },
                data={
                    CONF_NAME: _suggest_name(device_candidate),
                    CONF_DEVICE_POWER: device_candidate.entity_id,
                    CONF_GRID_POWER: grid_power,
                    CONF_INVERT_GRID: grid_entry.data.get(CONF_INVERT_GRID, False),
                },
            )


@callback
def _power_candidates(hass: HomeAssistant) -> list[PowerCandidate]:
    """Return sensor entities that look like power sensors."""
    candidates: list[PowerCandidate] = []
    entity_registry = er.async_get(hass)

    for state in hass.states.async_all("sensor"):
        entity_entry = entity_registry.async_get(state.entity_id)
        if entity_entry is not None and entity_entry.platform == DOMAIN:
            continue

        unit = state.attributes.get(ATTR_UNIT_OF_MEASUREMENT)
        device_class = state.attributes.get(ATTR_DEVICE_CLASS)

        if device_class != "power" and unit not in POWER_UNITS:
            continue

        name = state.attributes.get(ATTR_FRIENDLY_NAME, state.entity_id)
        text = f"{state.entity_id} {name}".casefold()
        candidates.append(
            PowerCandidate(
                entity_id=state.entity_id,
                name=name,
                is_grid=any(hint in text for hint in GRID_HINTS),
            )
        )

    return candidates


@callback
def _grid_source_entries(hass: HomeAssistant) -> list[config_entries.ConfigEntry]:
    """Return entries that can provide a grid sensor for discovery."""
    seen: set[str] = set()
    entries: list[config_entries.ConfigEntry] = []

    for entry in hass.config_entries.async_entries(DOMAIN):
        if not entry.data.get(CONF_ENABLE_DISCOVERY, True):
            continue

        grid_power = entry.data.get(CONF_GRID_POWER)
        if grid_power is None or grid_power in seen:
            continue

        seen.add(grid_power)
        entries.append(entry)

    return entries


@callback
def _discovery_flow_in_progress(hass: HomeAssistant, unique_id: str) -> bool:
    """Return whether a discovery flow for the pair is already in progress."""
    for flow in hass.config_entries.flow.async_progress_by_handler(DOMAIN):
        context = flow.get("context", {})
        if (
            context.get("source") == config_entries.SOURCE_DISCOVERY
            and context.get("unique_id") == unique_id
        ):
            return True
    return False


@callback
def _is_configured(hass: HomeAssistant, device_power: str, grid_power: str) -> bool:
    """Return whether the pair already has a config entry."""
    for entry in hass.config_entries.async_entries(DOMAIN):
        if (
            entry.data.get(CONF_DEVICE_POWER) == device_power
            and entry.data.get(CONF_GRID_POWER) == grid_power
        ):
            return True
    return False


@callback
def _suggest_name(candidate: PowerCandidate) -> str:
    """Suggest a config entry name from a power sensor."""
    if candidate.name and candidate.name != candidate.entity_id:
        return candidate.name
    return DEFAULT_NAME


@callback
def _pair_unique_id(device_power: str, grid_power: str) -> str:
    """Return the unique ID for a device/grid pair."""
    return f"{device_power}_{grid_power}"
