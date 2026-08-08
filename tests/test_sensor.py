"""Tests for Solar Load Split sensors."""

from homeassistant.const import (
    ATTR_UNIT_OF_MEASUREMENT,
    CONF_NAME,
    UnitOfEnergy,
    UnitOfPower,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.pv_device_split.const import (
    CONF_DEVICE_POWER,
    CONF_GRID_BUFFER_SECONDS,
    CONF_GRID_DEADBAND_WATTS,
    CONF_GRID_POWER,
    CONF_INVERT_GRID,
    DOMAIN,
)
from custom_components.pv_device_split.sensor import (
    _state_as_energy_kwh,
    _state_as_power_watts,
)


def _entry(name: str = "Washer") -> MockConfigEntry:
    return MockConfigEntry(
        domain=DOMAIN,
        title=name,
        unique_id="sensor.washer_power_sensor.grid_power",
        data={
            CONF_NAME: name,
            CONF_DEVICE_POWER: "sensor.washer_power",
            CONF_GRID_POWER: "sensor.grid_power",
            CONF_INVERT_GRID: False,
            CONF_GRID_BUFFER_SECONDS: 0,
            CONF_GRID_DEADBAND_WATTS: 0,
        },
    )


def test_power_unit_conversion_and_validation(hass: HomeAssistant) -> None:
    """Power states are converted only from supported finite units."""
    hass.states.async_set("sensor.watts", "125", {ATTR_UNIT_OF_MEASUREMENT: UnitOfPower.WATT})
    hass.states.async_set(
        "sensor.kilowatts", "1.25", {ATTR_UNIT_OF_MEASUREMENT: UnitOfPower.KILO_WATT}
    )
    hass.states.async_set("sensor.volts", "230", {ATTR_UNIT_OF_MEASUREMENT: "V"})
    hass.states.async_set("sensor.nan", "nan", {ATTR_UNIT_OF_MEASUREMENT: "W"})

    assert _state_as_power_watts(hass, "sensor.watts") == 125
    assert _state_as_power_watts(hass, "sensor.kilowatts") == 1250
    assert _state_as_power_watts(hass, "sensor.volts") is None
    assert _state_as_power_watts(hass, "sensor.nan") is None


def test_energy_unit_conversion_and_validation(hass: HomeAssistant) -> None:
    """Energy states are converted only from supported finite units."""
    hass.states.async_set("sensor.wh", "1250", {ATTR_UNIT_OF_MEASUREMENT: UnitOfEnergy.WATT_HOUR})
    hass.states.async_set(
        "sensor.kwh", "1.25", {ATTR_UNIT_OF_MEASUREMENT: UnitOfEnergy.KILO_WATT_HOUR}
    )
    hass.states.async_set("sensor.inf", "inf", {ATTR_UNIT_OF_MEASUREMENT: "kWh"})

    assert _state_as_energy_kwh(hass, "sensor.wh") == 1.25
    assert _state_as_energy_kwh(hass, "sensor.kwh") == 1.25
    assert _state_as_energy_kwh(hass, "sensor.inf") is None


async def test_setup_creates_sensors_and_single_entry_device(
    hass: HomeAssistant,
    enable_custom_integrations: None,
) -> None:
    """A split entry loads twelve sensors attached to its own device."""
    entry = _entry()
    entry.add_to_hass(hass)
    hass.states.async_set(
        "sensor.washer_power", "1000", {ATTR_UNIT_OF_MEASUREMENT: UnitOfPower.WATT}
    )
    hass.states.async_set("sensor.grid_power", "400", {ATTR_UNIT_OF_MEASUREMENT: UnitOfPower.WATT})

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    entity_entries = er.async_entries_for_config_entry(er.async_get(hass), entry.entry_id)
    assert len(entity_entries) == 12
    assert hass.states.get("sensor.washer_pv_power").state == "0.6"
    assert hass.states.get("sensor.washer_grid_power").state == "0.4"

    devices = dr.async_entries_for_config_entry(dr.async_get(hass), entry.entry_id)
    assert len(devices) == 1
    assert devices[0].config_entry_id == entry.entry_id

    assert await hass.config_entries.async_unload(entry.entry_id)


async def test_preserves_custom_registry_name(
    hass: HomeAssistant,
    enable_custom_integrations: None,
) -> None:
    """Loading the integration does not overwrite a user-defined name."""
    entry = _entry()
    entry.add_to_hass(hass)
    registry = er.async_get(hass)
    entity = registry.async_get_or_create(
        "sensor",
        DOMAIN,
        f"{entry.entry_id}_pv_power",
        suggested_object_id="washer_pv_power",
    )
    registry.async_update_entity(entity.entity_id, name="My custom solar")
    hass.states.async_set(
        "sensor.washer_power", "1000", {ATTR_UNIT_OF_MEASUREMENT: UnitOfPower.WATT}
    )
    hass.states.async_set("sensor.grid_power", "400", {ATTR_UNIT_OF_MEASUREMENT: UnitOfPower.WATT})

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert registry.async_get(entity.entity_id).name == "My custom solar"


async def test_clears_only_legacy_generated_registry_name(
    hass: HomeAssistant,
    enable_custom_integrations: None,
) -> None:
    """An old generated full name is migrated to entity translations."""
    entry = _entry()
    entry.add_to_hass(hass)
    registry = er.async_get(hass)
    entity = registry.async_get_or_create(
        "sensor",
        DOMAIN,
        f"{entry.entry_id}_pv_power",
        suggested_object_id="washer_pv_power",
    )
    registry.async_update_entity(entity.entity_id, name="Washer PV Power")
    hass.states.async_set(
        "sensor.washer_power", "1000", {ATTR_UNIT_OF_MEASUREMENT: UnitOfPower.WATT}
    )
    hass.states.async_set("sensor.grid_power", "400", {ATTR_UNIT_OF_MEASUREMENT: UnitOfPower.WATT})

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert registry.async_get(entity.entity_id).name is None
