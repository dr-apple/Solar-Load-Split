"""Constants for the Solar Load Split integration."""

from __future__ import annotations

DOMAIN = "pv_device_split"

CONF_DEVICE_POWER = "device_power"
CONF_GRID_POWER = "grid_power"
CONF_INVERT_GRID = "invert_grid"
CONF_ENABLE_DISCOVERY = "enable_discovery"

DEFAULT_NAME = "Solar Load Split"

PLATFORMS = ["sensor"]
