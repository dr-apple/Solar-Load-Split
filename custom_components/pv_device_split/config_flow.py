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

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
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

        return self.async_show_form(
            step_id="user",
            data_schema=_schema(),
            errors=errors,
        )


@callback
def _schema() -> vol.Schema:
    """Return the config flow schema."""
    return vol.Schema(
        {
            vol.Optional(CONF_NAME, default=DEFAULT_NAME): selector.TextSelector(),
            vol.Required(CONF_DEVICE_POWER): selector.EntitySelector(
                selector.EntitySelectorConfig(domain="sensor")
            ),
            vol.Required(CONF_GRID_POWER): selector.EntitySelector(
                selector.EntitySelectorConfig(domain="sensor")
            ),
            vol.Optional(CONF_INVERT_GRID, default=False): selector.BooleanSelector(),
        }
    )
