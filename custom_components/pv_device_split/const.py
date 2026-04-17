"""Constants for the Solar Load Split integration."""

from __future__ import annotations

DOMAIN = "pv_device_split"

CONF_DEVICE_POWER = "device_power"
CONF_GRID_POWER = "grid_power"
CONF_INVERT_GRID = "invert_grid"
CONF_ENABLE_DISCOVERY = "enable_discovery"
CONF_GRID_BUFFER_SECONDS = "grid_buffer_seconds"

DEFAULT_NAME = "Solar Load Split"
DEFAULT_GRID_BUFFER_SECONDS = 30

PLATFORMS = ["sensor"]
