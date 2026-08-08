"""Tests for the Solar Load Split config and options flows."""

from unittest.mock import Mock, patch

from homeassistant.const import CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.pv_device_split.const import (
    CONF_DEVICE_POWER,
    CONF_GRID_BUFFER_SECONDS,
    CONF_GRID_DEADBAND_WATTS,
    CONF_GRID_POWER,
    CONF_INVERT_GRID,
    DOMAIN,
)
from custom_components.pv_device_split.discovery import (
    async_schedule_power_discovery_retries,
)


def _data(device: str, grid: str = "sensor.grid_power") -> dict:
    return {
        CONF_NAME: "Washer",
        CONF_DEVICE_POWER: device,
        CONF_GRID_POWER: grid,
        CONF_INVERT_GRID: False,
        CONF_GRID_BUFFER_SECONDS: 0,
        CONF_GRID_DEADBAND_WATTS: 0,
    }


async def test_options_updates_unique_id(
    hass: HomeAssistant,
    enable_custom_integrations: None,
) -> None:
    """Changing source entities keeps the entry unique ID in sync."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Washer",
        unique_id="sensor.old_power_sensor.grid_power",
        data=_data("sensor.old_power"),
    )
    entry.add_to_hass(hass)

    with patch.object(hass.config_entries, "async_schedule_reload") as schedule_reload:
        result = await hass.config_entries.options.async_init(entry.entry_id)
        result = await hass.config_entries.options.async_configure(
            result["flow_id"],
            user_input=_data("sensor.new_power"),
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert entry.unique_id == "sensor.new_power_sensor.grid_power"
    assert entry.data[CONF_DEVICE_POWER] == "sensor.new_power"
    schedule_reload.assert_called_once_with(entry.entry_id)


async def test_options_rejects_duplicate_pair(
    hass: HomeAssistant,
    enable_custom_integrations: None,
) -> None:
    """Options cannot change an entry to a pair owned by another entry."""
    existing = MockConfigEntry(
        domain=DOMAIN,
        unique_id="sensor.existing_sensor.grid_power",
        data=_data("sensor.existing"),
    )
    existing.add_to_hass(hass)
    edited = MockConfigEntry(
        domain=DOMAIN,
        unique_id="sensor.old_sensor.grid_power",
        data=_data("sensor.old"),
    )
    edited.add_to_hass(hass)

    result = await hass.config_entries.options.async_init(edited.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input=_data("sensor.existing"),
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "already_configured"}
    assert edited.unique_id == "sensor.old_sensor.grid_power"


def test_discovery_retries_use_callback_jobs(hass: HomeAssistant) -> None:
    """Delayed discovery callbacks stay on Home Assistant's event loop."""
    scheduled: list[object] = []

    with patch(
        "custom_components.pv_device_split.discovery.async_call_later",
        side_effect=lambda _hass, _delay, action: scheduled.append(action),
    ):
        async_schedule_power_discovery_retries(hass)

    assert len(scheduled) == 3
    assert all(getattr(action, "_hass_callback", False) for action in scheduled)

    with patch(
        "custom_components.pv_device_split.discovery.async_schedule_power_discovery"
    ) as discover:
        scheduled[0](Mock())
    discover.assert_called_once_with(hass)
