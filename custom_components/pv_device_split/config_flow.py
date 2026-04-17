"""Config flow for Solar Load Split."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_NAME
from homeassistant.core import callback
from homeassistant.helpers import selector

from .const import (
    CONF_DEVICE_POWER,
    CONF_ENABLE_DISCOVERY,
    CONF_GRID_BUFFER_SECONDS,
    CONF_GRID_DEADBAND_WATTS,
    CONF_GRID_POWER,
    CONF_INVERT_GRID,
    DEFAULT_GRID_BUFFER_SECONDS,
    DEFAULT_GRID_DEADBAND_WATTS,
    DEFAULT_NAME,
    DOMAIN,
)
from .discovery import _pair_unique_id


class PVDeviceSplitConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Solar Load Split."""

    VERSION = 1
    _discovery_info: dict[str, Any] | None = None

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> config_entries.OptionsFlow:
        """Create the options flow."""
        return PVDeviceSplitOptionsFlow(config_entry)

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            if _grid_source_entries(self.hass):
                return await self._async_create_split_entry(
                    _with_grid_defaults(self.hass, user_input)
                )
            return await self._async_create_hub_entry(user_input)

        if self.hass.config_entries.async_entries(DOMAIN):
            return await self.async_step_manual_device()

        return self.async_show_form(
            step_id="user",
            data_schema=_hub_schema(),
            errors=errors,
        )

    async def async_step_hub(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Create an additional base grid entry."""
        errors: dict[str, str] = {}

        if user_input is not None:
            return await self._async_create_hub_entry(user_input)

        return self.async_show_form(
            step_id="hub",
            data_schema=_hub_schema(),
            errors=errors,
        )

    async def async_step_manual_device(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Manually add a device power sensor."""
        grid_source_entries = _grid_source_entries(self.hass)
        if user_input is not None:
            return await self._async_create_split_entry(
                _with_grid_defaults(self.hass, user_input)
            )

        return self.async_show_form(
            step_id="manual_device",
            data_schema=_manual_device_schema(
                grid_source_entries[0].data if grid_source_entries else {}
            ),
        )

    async def async_step_discovery(
        self, discovery_info: dict[str, Any]
    ) -> config_entries.ConfigFlowResult:
        """Handle a discovered power sensor pair."""
        self._discovery_info = discovery_info
        self.context["title_placeholders"] = {
            "name": discovery_info.get(CONF_NAME, discovery_info[CONF_DEVICE_POWER]),
        }

        await self.async_set_unique_id(
            _pair_unique_id(
                discovery_info[CONF_DEVICE_POWER],
                discovery_info[CONF_GRID_POWER],
            )
        )
        self._abort_if_unique_id_configured()

        return await self.async_step_discovery_confirm()

    async def async_step_discovery_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Confirm or edit discovered sensors."""
        if self._discovery_info is None:
            return self.async_abort(reason="discovery_missing")

        if user_input is not None:
            return await self._async_create_split_entry(
                {
                    **self._discovery_info,
                    **user_input,
                }
            )

        return self.async_show_form(
            step_id="discovery_confirm",
            data_schema=_discovery_schema(self._discovery_info),
            description_placeholders={
                "device_name": self._discovery_info.get(
                    CONF_NAME,
                    self._discovery_info[CONF_DEVICE_POWER],
                ),
                "device_entity": self._discovery_info[CONF_DEVICE_POWER],
            },
        )

    async def _async_create_hub_entry(
        self, user_input: dict[str, Any]
    ) -> config_entries.ConfigFlowResult:
        """Create the base grid config entry."""
        await self.async_set_unique_id(f"grid_{user_input[CONF_GRID_POWER]}")
        self._abort_if_unique_id_configured()

        return self.async_create_entry(
            title=user_input.get(CONF_NAME, DEFAULT_NAME),
            data={
                CONF_NAME: user_input.get(CONF_NAME, DEFAULT_NAME),
                CONF_GRID_POWER: user_input[CONF_GRID_POWER],
                CONF_INVERT_GRID: user_input.get(CONF_INVERT_GRID, False),
                CONF_ENABLE_DISCOVERY: user_input.get(CONF_ENABLE_DISCOVERY, False),
                CONF_GRID_BUFFER_SECONDS: user_input.get(
                    CONF_GRID_BUFFER_SECONDS,
                    DEFAULT_GRID_BUFFER_SECONDS,
                ),
                CONF_GRID_DEADBAND_WATTS: user_input.get(
                    CONF_GRID_DEADBAND_WATTS,
                    DEFAULT_GRID_DEADBAND_WATTS,
                ),
            },
        )

    async def _async_create_split_entry(
        self, user_input: dict[str, Any]
    ) -> config_entries.ConfigFlowResult:
        """Create a device split config entry."""
        await self.async_set_unique_id(
            _pair_unique_id(
                user_input[CONF_DEVICE_POWER],
                user_input[CONF_GRID_POWER],
            )
        )
        self._abort_if_unique_id_configured()

        return self.async_create_entry(
            title=user_input.get(CONF_NAME, DEFAULT_NAME),
            data={
                CONF_NAME: user_input.get(CONF_NAME, DEFAULT_NAME),
                CONF_DEVICE_POWER: user_input[CONF_DEVICE_POWER],
                CONF_GRID_POWER: user_input[CONF_GRID_POWER],
                CONF_INVERT_GRID: user_input.get(CONF_INVERT_GRID, False),
                CONF_GRID_BUFFER_SECONDS: user_input.get(
                    CONF_GRID_BUFFER_SECONDS,
                    DEFAULT_GRID_BUFFER_SECONDS,
                ),
                CONF_GRID_DEADBAND_WATTS: user_input.get(
                    CONF_GRID_DEADBAND_WATTS,
                    DEFAULT_GRID_DEADBAND_WATTS,
                ),
            },
        )


@callback
def _hub_schema(defaults: dict[str, Any] | None = None) -> vol.Schema:
    """Return the base config flow schema."""
    defaults = defaults or {}
    return vol.Schema(
        {
            vol.Optional(
                CONF_NAME,
                default=defaults.get(CONF_NAME, DEFAULT_NAME),
            ): selector.TextSelector(),
            vol.Required(
                CONF_GRID_POWER,
                default=defaults.get(CONF_GRID_POWER, vol.UNDEFINED),
            ): selector.EntitySelector(
                selector.EntitySelectorConfig(domain="sensor")
            ),
            vol.Optional(
                CONF_INVERT_GRID,
                default=defaults.get(CONF_INVERT_GRID, False),
            ): selector.BooleanSelector(),
            vol.Optional(
                CONF_ENABLE_DISCOVERY,
                default=defaults.get(CONF_ENABLE_DISCOVERY, False),
            ): selector.BooleanSelector(),
            vol.Optional(
                CONF_GRID_BUFFER_SECONDS,
                default=defaults.get(
                    CONF_GRID_BUFFER_SECONDS,
                    DEFAULT_GRID_BUFFER_SECONDS,
                ),
            ): selector.NumberSelector(
                selector.NumberSelectorConfig(
                    min=0,
                    max=600,
                    unit_of_measurement="s",
                )
            ),
            vol.Optional(
                CONF_GRID_DEADBAND_WATTS,
                default=defaults.get(
                    CONF_GRID_DEADBAND_WATTS,
                    DEFAULT_GRID_DEADBAND_WATTS,
                ),
            ): selector.NumberSelector(
                selector.NumberSelectorConfig(
                    min=0,
                    max=1000,
                    unit_of_measurement="W",
                )
            ),
        }
    )


@callback
def _discovery_schema(defaults: dict[str, Any]) -> vol.Schema:
    """Return the discovered device confirmation schema."""
    return vol.Schema(
        {
            vol.Optional(
                CONF_NAME,
                default=defaults.get(CONF_NAME, DEFAULT_NAME),
            ): selector.TextSelector(),
            vol.Required(
                CONF_DEVICE_POWER,
                default=defaults.get(CONF_DEVICE_POWER, vol.UNDEFINED),
            ): selector.EntitySelector(
                selector.EntitySelectorConfig(domain="sensor")
            ),
        }
    )


@callback
def _manual_device_schema(defaults: dict[str, Any]) -> vol.Schema:
    """Return the manual device schema."""
    schema: dict = {
        vol.Optional(
            CONF_NAME,
            default=DEFAULT_NAME,
        ): selector.TextSelector(),
        vol.Required(CONF_DEVICE_POWER): selector.EntitySelector(
            selector.EntitySelectorConfig(domain="sensor")
        ),
        vol.Required(
            CONF_GRID_POWER,
            default=defaults.get(CONF_GRID_POWER, vol.UNDEFINED),
        ): selector.EntitySelector(selector.EntitySelectorConfig(domain="sensor")),
    }

    if CONF_INVERT_GRID not in defaults:
        schema[
            vol.Optional(
                CONF_INVERT_GRID,
                default=False,
            )
        ] = selector.BooleanSelector()

    if CONF_GRID_BUFFER_SECONDS not in defaults:
        schema[
            vol.Optional(
                CONF_GRID_BUFFER_SECONDS,
                default=DEFAULT_GRID_BUFFER_SECONDS,
            )
        ] = selector.NumberSelector(
            selector.NumberSelectorConfig(
                min=0,
                max=600,
                unit_of_measurement="s",
            )
        )

    if CONF_GRID_DEADBAND_WATTS not in defaults:
        schema[
            vol.Optional(
                CONF_GRID_DEADBAND_WATTS,
                default=DEFAULT_GRID_DEADBAND_WATTS,
            )
        ] = selector.NumberSelector(
            selector.NumberSelectorConfig(
                min=0,
                max=1000,
                unit_of_measurement="W",
            )
        )

    return vol.Schema(schema)


@callback
def _grid_source_entries(hass) -> list[config_entries.ConfigEntry]:
    """Return entries that can provide a grid sensor for device setup."""
    seen: set[str] = set()
    entries: list[config_entries.ConfigEntry] = []

    for entry in hass.config_entries.async_entries(DOMAIN):
        grid_power = entry.data.get(CONF_GRID_POWER)
        if grid_power is None or grid_power in seen:
            continue

        seen.add(grid_power)
        entries.append(entry)

    return entries


@callback
def _with_grid_defaults(hass, user_input: dict[str, Any]) -> dict[str, Any]:
    """Add inherited grid options to a manual device config."""
    grid_power = user_input[CONF_GRID_POWER]
    for entry in _grid_source_entries(hass):
        if entry.data.get(CONF_GRID_POWER) == grid_power:
            return {
                **entry.data,
                **user_input,
                CONF_INVERT_GRID: entry.data.get(CONF_INVERT_GRID, False),
                CONF_GRID_BUFFER_SECONDS: entry.data.get(
                    CONF_GRID_BUFFER_SECONDS,
                    DEFAULT_GRID_BUFFER_SECONDS,
                ),
                CONF_GRID_DEADBAND_WATTS: entry.data.get(
                    CONF_GRID_DEADBAND_WATTS,
                    DEFAULT_GRID_DEADBAND_WATTS,
                ),
            }

    return {
        **user_input,
        CONF_INVERT_GRID: user_input.get(CONF_INVERT_GRID, False),
        CONF_GRID_BUFFER_SECONDS: user_input.get(
            CONF_GRID_BUFFER_SECONDS,
            DEFAULT_GRID_BUFFER_SECONDS,
        ),
        CONF_GRID_DEADBAND_WATTS: user_input.get(
            CONF_GRID_DEADBAND_WATTS,
            DEFAULT_GRID_DEADBAND_WATTS,
        ),
    }


class PVDeviceSplitOptionsFlow(config_entries.OptionsFlow):
    """Handle options for Solar Load Split."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Initialize options flow."""
        self._config_entry = config_entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Manage entry options."""
        if user_input is not None:
            data = {
                **self._config_entry.data,
                **user_input,
            }
            self.hass.config_entries.async_update_entry(
                self._config_entry,
                title=data.get(CONF_NAME, DEFAULT_NAME),
                data=data,
            )
            self.hass.async_create_task(
                self.hass.config_entries.async_reload(self._config_entry.entry_id)
            )
            return self.async_create_entry(title="", data={})

        return self.async_show_form(
            step_id="init",
            data_schema=_options_schema(self._config_entry.data),
        )


@callback
def _options_schema(defaults: dict[str, Any]) -> vol.Schema:
    """Return options schema for an existing entry."""
    schema: dict = {
        vol.Optional(
            CONF_NAME,
            default=defaults.get(CONF_NAME, DEFAULT_NAME),
        ): selector.TextSelector(),
        vol.Required(
            CONF_GRID_POWER,
            default=defaults.get(CONF_GRID_POWER, vol.UNDEFINED),
        ): selector.EntitySelector(selector.EntitySelectorConfig(domain="sensor")),
        vol.Optional(
            CONF_INVERT_GRID,
            default=defaults.get(CONF_INVERT_GRID, False),
        ): selector.BooleanSelector(),
        vol.Optional(
            CONF_ENABLE_DISCOVERY,
            default=defaults.get(CONF_ENABLE_DISCOVERY, False),
        ): selector.BooleanSelector(),
        vol.Optional(
            CONF_GRID_BUFFER_SECONDS,
            default=defaults.get(
                CONF_GRID_BUFFER_SECONDS,
                DEFAULT_GRID_BUFFER_SECONDS,
            ),
        ): selector.NumberSelector(
            selector.NumberSelectorConfig(
                min=0,
                max=600,
                unit_of_measurement="s",
            )
        ),
        vol.Optional(
            CONF_GRID_DEADBAND_WATTS,
            default=defaults.get(
                CONF_GRID_DEADBAND_WATTS,
                DEFAULT_GRID_DEADBAND_WATTS,
            ),
        ): selector.NumberSelector(
            selector.NumberSelectorConfig(
                min=0,
                max=1000,
                unit_of_measurement="W",
            )
        ),
    }

    if CONF_DEVICE_POWER in defaults:
        schema[
            vol.Required(
                CONF_DEVICE_POWER,
                default=defaults.get(CONF_DEVICE_POWER, vol.UNDEFINED),
            )
        ] = selector.EntitySelector(selector.EntitySelectorConfig(domain="sensor"))

    return vol.Schema(schema)
