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
    CONF_GRID_POWER,
    CONF_INVERT_GRID,
    DEFAULT_NAME,
    DOMAIN,
)
from .discovery import _pair_unique_id


class PVDeviceSplitConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Solar Load Split."""

    VERSION = 1
    _discovery_info: dict[str, Any] | None = None

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            if _grid_entries(self.hass):
                return await self._async_create_split_entry(
                    _with_grid_defaults(self.hass, user_input)
                )
            return await self._async_create_hub_entry(user_input)

        if _grid_entries(self.hass):
            return await self.async_step_manual_device()

        return self.async_show_form(
            step_id="user",
            data_schema=_hub_schema(),
            errors=errors,
        )

    async def async_step_manual_device(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Manually add a device power sensor."""
        grid_entries = _grid_entries(self.hass)
        if not grid_entries:
            return await self.async_step_user(user_input)

        if user_input is not None:
            return await self._async_create_split_entry(
                _with_grid_defaults(self.hass, user_input)
            )

        return self.async_show_form(
            step_id="manual_device",
            data_schema=_manual_device_schema(grid_entries[0].data),
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
    return vol.Schema(
        {
            vol.Optional(
                CONF_NAME,
                default=defaults.get(CONF_NAME, DEFAULT_NAME),
            ): selector.TextSelector(),
            vol.Required(CONF_DEVICE_POWER): selector.EntitySelector(
                selector.EntitySelectorConfig(domain="sensor")
            ),
            vol.Required(
                CONF_GRID_POWER,
                default=defaults.get(CONF_GRID_POWER, vol.UNDEFINED),
            ): selector.EntitySelector(
                selector.EntitySelectorConfig(domain="sensor")
            ),
        }
    )


@callback
def _grid_entries(hass) -> list[config_entries.ConfigEntry]:
    """Return configured base grid entries."""
    return [
        entry
        for entry in hass.config_entries.async_entries(DOMAIN)
        if CONF_GRID_POWER in entry.data and CONF_DEVICE_POWER not in entry.data
    ]


@callback
def _with_grid_defaults(hass, user_input: dict[str, Any]) -> dict[str, Any]:
    """Add inherited grid options to a manual device config."""
    grid_power = user_input[CONF_GRID_POWER]
    for entry in _grid_entries(hass):
        if entry.data.get(CONF_GRID_POWER) == grid_power:
            return {
                **entry.data,
                **user_input,
                CONF_INVERT_GRID: entry.data.get(CONF_INVERT_GRID, False),
            }

    return {
        **user_input,
        CONF_INVERT_GRID: user_input.get(CONF_INVERT_GRID, False),
    }
