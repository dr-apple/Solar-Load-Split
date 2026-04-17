"""Sensors for Solar Load Split."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from dataclasses import replace
from datetime import datetime
from datetime import timedelta
from enum import StrEnum
import logging

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    ATTR_UNIT_OF_MEASUREMENT,
    CONF_NAME,
    UnitOfEnergy,
    UnitOfPower,
)
from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import (
    async_track_state_change_event,
    async_track_time_interval,
)
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.util import dt as dt_util

from .const import (
    CONF_DEVICE_POWER,
    CONF_GRID_BUFFER_SECONDS,
    CONF_GRID_DEADBAND_WATTS,
    CONF_GRID_POWER,
    CONF_INVERT_GRID,
    DEFAULT_GRID_BUFFER_SECONDS,
    DEFAULT_GRID_DEADBAND_WATTS,
    DEFAULT_NAME,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)


class SplitSensorKey(StrEnum):
    """Sensor keys."""

    PV_POWER = "pv_power"
    GRID_POWER = "grid_power"
    PV_ENERGY = "pv_energy"
    GRID_ENERGY = "grid_energy"
    PV_ENERGY_DAILY = "pv_energy_daily"
    GRID_ENERGY_DAILY = "grid_energy_daily"
    PV_ENERGY_WEEKLY = "pv_energy_weekly"
    GRID_ENERGY_WEEKLY = "grid_energy_weekly"
    PV_ENERGY_MONTHLY = "pv_energy_monthly"
    GRID_ENERGY_MONTHLY = "grid_energy_monthly"
    PV_ENERGY_YEARLY = "pv_energy_yearly"
    GRID_ENERGY_YEARLY = "grid_energy_yearly"


PERIOD_SENSOR_KEYS: dict[SplitSensorKey, tuple[str, str]] = {
    SplitSensorKey.PV_ENERGY_DAILY: ("pv", "day"),
    SplitSensorKey.GRID_ENERGY_DAILY: ("grid", "day"),
    SplitSensorKey.PV_ENERGY_WEEKLY: ("pv", "week"),
    SplitSensorKey.GRID_ENERGY_WEEKLY: ("grid", "week"),
    SplitSensorKey.PV_ENERGY_MONTHLY: ("pv", "month"),
    SplitSensorKey.GRID_ENERGY_MONTHLY: ("grid", "month"),
    SplitSensorKey.PV_ENERGY_YEARLY: ("pv", "year"),
    SplitSensorKey.GRID_ENERGY_YEARLY: ("grid", "year"),
}

PERIODS = ("day", "week", "month", "year")


SENSOR_DESCRIPTIONS: tuple[SensorEntityDescription, ...] = (
    SensorEntityDescription(
        key=SplitSensorKey.PV_POWER,
        name="PV Power",
        native_unit_of_measurement=UnitOfPower.KILO_WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=2,
    ),
    SensorEntityDescription(
        key=SplitSensorKey.GRID_POWER,
        name="Grid Power",
        native_unit_of_measurement=UnitOfPower.KILO_WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=2,
    ),
    SensorEntityDescription(
        key=SplitSensorKey.PV_ENERGY,
        name="PV Energy",
        icon="mdi:solar-power",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        suggested_display_precision=2,
    ),
    SensorEntityDescription(
        key=SplitSensorKey.GRID_ENERGY,
        name="Grid Energy",
        icon="mdi:transmission-tower",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        suggested_display_precision=2,
    ),
    SensorEntityDescription(
        key=SplitSensorKey.PV_ENERGY_DAILY,
        name="PV Daily Energy",
        icon="mdi:solar-power",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL,
        suggested_display_precision=2,
    ),
    SensorEntityDescription(
        key=SplitSensorKey.GRID_ENERGY_DAILY,
        name="Grid Daily Energy",
        icon="mdi:transmission-tower",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL,
        suggested_display_precision=2,
    ),
    SensorEntityDescription(
        key=SplitSensorKey.PV_ENERGY_WEEKLY,
        name="PV Weekly Energy",
        icon="mdi:solar-power",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL,
        suggested_display_precision=2,
    ),
    SensorEntityDescription(
        key=SplitSensorKey.GRID_ENERGY_WEEKLY,
        name="Grid Weekly Energy",
        icon="mdi:transmission-tower",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL,
        suggested_display_precision=2,
    ),
    SensorEntityDescription(
        key=SplitSensorKey.PV_ENERGY_MONTHLY,
        name="PV Monthly Energy",
        icon="mdi:solar-power",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL,
        suggested_display_precision=2,
    ),
    SensorEntityDescription(
        key=SplitSensorKey.GRID_ENERGY_MONTHLY,
        name="Grid Monthly Energy",
        icon="mdi:transmission-tower",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL,
        suggested_display_precision=2,
    ),
    SensorEntityDescription(
        key=SplitSensorKey.PV_ENERGY_YEARLY,
        name="PV Yearly Energy",
        icon="mdi:solar-power",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL,
        suggested_display_precision=2,
    ),
    SensorEntityDescription(
        key=SplitSensorKey.GRID_ENERGY_YEARLY,
        name="Grid Yearly Energy",
        icon="mdi:transmission-tower",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL,
        suggested_display_precision=2,
    ),
)

SHORT_ENTITY_NAMES = (
    "PV Power",
    "Grid Power",
    "PV Energy",
    "Grid Energy",
    "PV Leistung",
    "Netz Leistung",
    "PV Energie",
    "Netz Energie",
    "PV Daily Energy",
    "Grid Daily Energy",
    "PV Weekly Energy",
    "Grid Weekly Energy",
    "PV Monthly Energy",
    "Grid Monthly Energy",
    "PV Yearly Energy",
    "Grid Yearly Energy",
    "PV Tagesenergie",
    "Netz Tagesenergie",
    "PV Wochenenergie",
    "Netz Wochenenergie",
    "PV Monatsenergie",
    "Netz Monatsenergie",
    "PV Jahresenergie",
    "Netz Jahresenergie",
)


@dataclass
class SplitPower:
    """Calculated split power values."""

    pv_power_kw: float
    grid_power_kw: float


class PVDeviceSplitRuntime:
    """Runtime state shared by all entities for one config entry."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialize the runtime."""
        self.hass = hass
        self.entry = entry
        self.name = entry.data.get(CONF_NAME, DEFAULT_NAME)
        self.device_power_entity = entry.data[CONF_DEVICE_POWER]
        self.grid_power_entity = entry.data[CONF_GRID_POWER]
        self.invert_grid = entry.data.get(CONF_INVERT_GRID, False)
        self.grid_buffer_seconds = max(
            int(entry.data.get(CONF_GRID_BUFFER_SECONDS, DEFAULT_GRID_BUFFER_SECONDS)),
            0,
        )
        self.grid_deadband_watts = max(
            float(
                entry.data.get(
                    CONF_GRID_DEADBAND_WATTS,
                    DEFAULT_GRID_DEADBAND_WATTS,
                )
            ),
            0.0,
        )
        self._stable_grid_is_export: bool | None = None
        self._pending_grid_is_export: bool | None = None
        self._pending_grid_since: datetime | None = None
        self.pv_energy_kwh = 0.0
        self.grid_energy_kwh = 0.0
        self.period_energy_kwh: dict[str, float] = {
            key: 0.0 for key in PERIOD_SENSOR_KEYS
        }
        self.period_markers: dict[str, str] = {}
        self.powers = SplitPower(0.0, 0.0)
        self.last_update: datetime | None = None
        self.available = False
        self._listeners: list[Callable[[], None]] = []
        self._unsub_state: Callable[[], None] | None = None
        self._unsub_time: Callable[[], None] | None = None

    @property
    def device_info(self) -> DeviceInfo:
        """Return device registry information."""
        return DeviceInfo(
            identifiers={(DOMAIN, self.entry.entry_id)},
            name=self.name,
            manufacturer="Solar Load Split",
            model="Virtual split meter",
        )

    def add_listener(self, listener: Callable[[], None]) -> Callable[[], None]:
        """Register a listener called when calculated values change."""
        self._listeners.append(listener)

        def remove_listener() -> None:
            self._listeners.remove(listener)

        return remove_listener

    async def async_start(self) -> None:
        """Start tracking source entity state changes."""
        self._update(dt_util.utcnow())
        self._unsub_state = async_track_state_change_event(
            self.hass,
            [self.device_power_entity, self.grid_power_entity],
            self._async_source_state_changed,
        )
        self._unsub_time = async_track_time_interval(
            self.hass,
            self._async_time_interval,
            timedelta(minutes=1),
        )

    def stop(self) -> None:
        """Stop tracking source entity state changes."""
        if self._unsub_state is not None:
            self._unsub_state()
            self._unsub_state = None
        if self._unsub_time is not None:
            self._unsub_time()
            self._unsub_time = None

    @callback
    def _async_source_state_changed(self, event: Event) -> None:
        """Handle source entity state changes."""
        self._update(dt_util.utcnow())
        self._notify_listeners()

    @callback
    def _async_time_interval(self, now: datetime) -> None:
        """Update energy totals while source power remains steady."""
        self._update(now)
        self._notify_listeners()

    @callback
    def _notify_listeners(self) -> None:
        """Notify entities that calculated values changed."""
        for listener in self._listeners:
            listener()

    @callback
    def _update(self, now: datetime) -> None:
        """Update power and energy values."""
        device_power_w = _state_as_power_watts(self.hass, self.device_power_entity)
        grid_power_w = _state_as_power_watts(self.hass, self.grid_power_entity)

        if device_power_w is None or grid_power_w is None:
            self.available = False
            self.last_update = now
            self.powers = SplitPower(0.0, 0.0)
            return

        self.available = True
        device_power_w = max(device_power_w, 0.0)
        if self.invert_grid:
            grid_power_w *= -1
        grid_power_w = self._apply_grid_deadband(grid_power_w)
        grid_power_w = self._buffered_grid_power(now, grid_power_w)

        if self.last_update is not None:
            self._reset_periods_if_needed(now)
            elapsed_hours = max((now - self.last_update).total_seconds(), 0.0) / 3600
            self.pv_energy_kwh += self.powers.pv_power_kw * elapsed_hours
            self.grid_energy_kwh += self.powers.grid_power_kw * elapsed_hours
            self._add_period_energy("pv", self.powers.pv_power_kw, elapsed_hours)
            self._add_period_energy("grid", self.powers.grid_power_kw, elapsed_hours)
        else:
            self._reset_periods_if_needed(now)

        self.last_update = now
        self.powers = self._calculate(device_power_w, grid_power_w)

    @callback
    def _apply_grid_deadband(self, grid_power_w: float) -> float:
        """Treat small grid import/export values as neutral inverter noise."""
        if self.grid_deadband_watts <= 0:
            return grid_power_w

        if abs(grid_power_w) <= self.grid_deadband_watts:
            return 0.0

        return grid_power_w

    @callback
    def _buffered_grid_power(self, now: datetime, grid_power_w: float) -> float:
        """Return a sign-debounced grid power value."""
        if self.grid_buffer_seconds <= 0:
            self._stable_grid_is_export = grid_power_w < 0
            self._pending_grid_is_export = None
            self._pending_grid_since = None
            return grid_power_w

        if grid_power_w == 0:
            self._pending_grid_is_export = None
            self._pending_grid_since = None
            return grid_power_w

        grid_is_export = grid_power_w < 0
        if self._stable_grid_is_export is None:
            self._stable_grid_is_export = grid_is_export
            return grid_power_w

        if grid_is_export == self._stable_grid_is_export:
            self._pending_grid_is_export = None
            self._pending_grid_since = None
            return grid_power_w

        if self._pending_grid_is_export != grid_is_export:
            self._pending_grid_is_export = grid_is_export
            self._pending_grid_since = now
            return _force_grid_sign(grid_power_w, self._stable_grid_is_export)

        if (
            self._pending_grid_since is not None
            and (now - self._pending_grid_since).total_seconds()
            >= self.grid_buffer_seconds
        ):
            self._stable_grid_is_export = grid_is_export
            self._pending_grid_is_export = None
            self._pending_grid_since = None
            return grid_power_w

        return _force_grid_sign(grid_power_w, self._stable_grid_is_export)

    @staticmethod
    def _calculate(device_power_w: float, grid_power_w: float) -> SplitPower:
        """Calculate PV and grid power in kW."""
        if grid_power_w == 0:
            return SplitPower(pv_power_kw=0.0, grid_power_kw=0.0)

        if grid_power_w < 0:
            pv_used_w = min(device_power_w, abs(grid_power_w))
        else:
            pv_used_w = 0.0

        grid_used_w = max(device_power_w - pv_used_w, 0.0)
        return SplitPower(
            pv_power_kw=round(pv_used_w / 1000, 2),
            grid_power_kw=round(grid_used_w / 1000, 2),
        )

    @callback
    def restore_period_energy(
        self,
        key: SplitSensorKey,
        value: float,
        last_updated: datetime | None,
    ) -> None:
        """Restore a period energy value if it belongs to the current period."""
        if key not in PERIOD_SENSOR_KEYS:
            return

        _, period = PERIOD_SENSOR_KEYS[key]
        now = dt_util.utcnow()
        self.period_markers[period] = _period_marker(now, period)

        if last_updated is None:
            return

        if _period_marker(last_updated, period) == self.period_markers[period]:
            self.period_energy_kwh[key] = value

    @callback
    def _reset_periods_if_needed(self, now: datetime) -> None:
        """Reset period counters when the local period changes."""
        for period in PERIODS:
            marker = _period_marker(now, period)
            if self.period_markers.get(period) == marker:
                continue

            self.period_markers[period] = marker
            for key, (_, key_period) in PERIOD_SENSOR_KEYS.items():
                if key_period == period:
                    self.period_energy_kwh[key] = 0.0

    @callback
    def _add_period_energy(
        self,
        source: str,
        power_kw: float,
        elapsed_hours: float,
    ) -> None:
        """Add energy to the matching period counters."""
        for key, (key_source, _) in PERIOD_SENSOR_KEYS.items():
            if key_source == source:
                self.period_energy_kwh[key] += power_kw * elapsed_hours


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Solar Load Split sensors from a config entry."""
    runtime = PVDeviceSplitRuntime(hass, entry)

    entities: list[PVDeviceSplitSensor] = [
        PVDeviceSplitSensor(runtime, description) for description in SENSOR_DESCRIPTIONS
    ]

    async_add_entities(entities)
    await runtime.async_start()
    entry.async_on_unload(runtime.stop)


class PVDeviceSplitSensor(SensorEntity, RestoreEntity):
    """Solar Load Split sensor."""

    _attr_has_entity_name = False

    def __init__(
        self,
        runtime: PVDeviceSplitRuntime,
        description: SensorEntityDescription,
    ) -> None:
        """Initialize the sensor."""
        self.runtime = runtime
        self.entity_description = replace(
            description,
            name=_localized_entity_name(
                runtime.hass.config.language,
                runtime.name,
                description.key,
            ),
        )
        self._attr_name = self.entity_description.name
        self._full_name = self.entity_description.name
        self._attr_unique_id = f"{runtime.entry.entry_id}_{description.key}"
        self._attr_device_info = runtime.device_info
        self._attr_native_value: float | None = None
        if description.device_class == SensorDeviceClass.ENERGY:
            self._attr_last_reset = None
        self._remove_listener: Callable[[], None] | None = None

    @property
    def available(self) -> bool:
        """Return whether the entity is available."""
        return self.runtime.available

    async def async_added_to_hass(self) -> None:
        """Restore energy totals and subscribe to runtime updates."""
        await super().async_added_to_hass()
        self._async_update_registry_name()

        if self.entity_description.key in (
            SplitSensorKey.PV_ENERGY,
            SplitSensorKey.GRID_ENERGY,
            *PERIOD_SENSOR_KEYS,
        ):
            if (last_state := await self.async_get_last_state()) is not None:
                try:
                    value = float(last_state.state)
                except (TypeError, ValueError):
                    _LOGGER.debug(
                        "Could not restore %s from state %s",
                        self.entity_description.key,
                        last_state.state,
                    )
                else:
                    if self.entity_description.key == SplitSensorKey.PV_ENERGY:
                        self.runtime.pv_energy_kwh = value
                    elif self.entity_description.key == SplitSensorKey.GRID_ENERGY:
                        self.runtime.grid_energy_kwh = value
                    else:
                        self.runtime.restore_period_energy(
                            self.entity_description.key,
                            value,
                            last_state.last_updated,
                        )

        self._update_native_value()
        self._remove_listener = self.runtime.add_listener(self._handle_runtime_update)

    @callback
    def _async_update_registry_name(self) -> None:
        """Update old registry names from previous versions."""
        registry = er.async_get(self.hass)
        entity_entry = registry.async_get(self.entity_id)
        if entity_entry is None:
            return

        if entity_entry.name == self._full_name:
            return

        registry.async_update_entity(self.entity_id, name=self._full_name)

    async def async_will_remove_from_hass(self) -> None:
        """Unsubscribe from runtime updates."""
        if self._remove_listener is not None:
            self._remove_listener()
            self._remove_listener = None

    @callback
    def _handle_runtime_update(self) -> None:
        """Handle an update from the shared runtime."""
        self._update_native_value()
        self.async_write_ha_state()

    @callback
    def _update_native_value(self) -> None:
        """Update the entity native value from the runtime."""
        match self.entity_description.key:
            case SplitSensorKey.PV_POWER:
                self._attr_native_value = self.runtime.powers.pv_power_kw
            case SplitSensorKey.GRID_POWER:
                self._attr_native_value = self.runtime.powers.grid_power_kw
            case SplitSensorKey.PV_ENERGY:
                self._attr_native_value = round(self.runtime.pv_energy_kwh, 2)
            case SplitSensorKey.GRID_ENERGY:
                self._attr_native_value = round(self.runtime.grid_energy_kwh, 2)
            case key if key in PERIOD_SENSOR_KEYS:
                self._attr_native_value = round(
                    self.runtime.period_energy_kwh[key],
                    2,
                )


def _state_as_power_watts(hass: HomeAssistant, entity_id: str) -> float | None:
    """Return an entity power state in watts."""
    state = hass.states.get(entity_id)
    if state is None:
        return None

    try:
        value = float(state.state)
    except (TypeError, ValueError):
        return None

    unit = state.attributes.get(ATTR_UNIT_OF_MEASUREMENT)
    if unit == UnitOfPower.KILO_WATT or str(unit).casefold() == "kw":
        return value * 1000

    return value


def _localized_entity_name(
    language: str | None,
    device_name: str,
    key: str,
) -> str:
    """Return a stable full entity name for the current Home Assistant language."""
    german_names = {
        SplitSensorKey.PV_POWER: "PV Leistung",
        SplitSensorKey.GRID_POWER: "Netz Leistung",
        SplitSensorKey.PV_ENERGY: "PV Energie",
        SplitSensorKey.GRID_ENERGY: "Netz Energie",
        SplitSensorKey.PV_ENERGY_DAILY: "PV Tagesenergie",
        SplitSensorKey.GRID_ENERGY_DAILY: "Netz Tagesenergie",
        SplitSensorKey.PV_ENERGY_WEEKLY: "PV Wochenenergie",
        SplitSensorKey.GRID_ENERGY_WEEKLY: "Netz Wochenenergie",
        SplitSensorKey.PV_ENERGY_MONTHLY: "PV Monatsenergie",
        SplitSensorKey.GRID_ENERGY_MONTHLY: "Netz Monatsenergie",
        SplitSensorKey.PV_ENERGY_YEARLY: "PV Jahresenergie",
        SplitSensorKey.GRID_ENERGY_YEARLY: "Netz Jahresenergie",
    }
    english_names = {
        SplitSensorKey.PV_POWER: "PV Power",
        SplitSensorKey.GRID_POWER: "Grid Power",
        SplitSensorKey.PV_ENERGY: "PV Energy",
        SplitSensorKey.GRID_ENERGY: "Grid Energy",
        SplitSensorKey.PV_ENERGY_DAILY: "PV Daily Energy",
        SplitSensorKey.GRID_ENERGY_DAILY: "Grid Daily Energy",
        SplitSensorKey.PV_ENERGY_WEEKLY: "PV Weekly Energy",
        SplitSensorKey.GRID_ENERGY_WEEKLY: "Grid Weekly Energy",
        SplitSensorKey.PV_ENERGY_MONTHLY: "PV Monthly Energy",
        SplitSensorKey.GRID_ENERGY_MONTHLY: "Grid Monthly Energy",
        SplitSensorKey.PV_ENERGY_YEARLY: "PV Yearly Energy",
        SplitSensorKey.GRID_ENERGY_YEARLY: "Grid Yearly Energy",
    }

    names = german_names if (language or "").startswith("de") else english_names
    return f"{device_name} {names[key]}"


def _period_marker(timestamp: datetime, period: str) -> str:
    """Return a local period marker for a timestamp."""
    local = dt_util.as_local(timestamp)

    if period == "day":
        return local.date().isoformat()
    if period == "week":
        year, week, _ = local.isocalendar()
        return f"{year}-W{week}"
    if period == "month":
        return f"{local.year}-{local.month}"
    if period == "year":
        return str(local.year)

    return local.date().isoformat()


def _force_grid_sign(grid_power_w: float, export: bool) -> float:
    """Force a grid value to the currently stable sign."""
    value = abs(grid_power_w)
    return -value if export else value
