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
            return await self._async_create_hub_entry(user_input)

        return self.async_show_form(
            step_id="user",
            data_schema=_hub_schema(),
            errors=errors,
        )

    async def async_step_discovery(
        self, discovery_info: dict[str, Any]
    ) -> config_entries.ConfigFlowResult:
        """Handle a discovered power sensor pair."""
        self._discovery_info = discovery_info

        await self.async_set_unique_id(
            f"{discovery_info[CONF_DEVICE_POWER]}_{discovery_info[CONF_GRID_POWER]}"
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
            f"{user_input[CONF_DEVICE_POWER]}_{user_input[CONF_GRID_POWER]}"
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
