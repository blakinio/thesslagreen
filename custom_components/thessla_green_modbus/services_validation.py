"""Reusable validation and normalization helpers for services."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from .const import DOMAIN


def validate_bypass_temperature_range(data: dict[str, Any]) -> dict[str, Any]:
    """Validate bypass temperature range independently from voluptuous internals."""
    temperature = data.get("min_outdoor_temperature")
    if temperature is not None and not (-20.0 <= float(temperature) <= 40.0):
        invalid_exc = getattr(vol, "Invalid", ValueError)
        raise invalid_exc(f"min_outdoor_temperature ({temperature}) must be in range -20.0..40.0")
    return data


def validate_gwc_temperature_range(data: dict[str, Any]) -> dict[str, Any]:
    """Reject configurations where min_air_temperature >= max_air_temperature."""
    tmin = data.get("min_air_temperature")
    tmax = data.get("max_air_temperature")
    if tmin is not None and tmax is not None and tmin >= tmax:
        invalid_exc = getattr(vol, "Invalid", ValueError)
        raise invalid_exc(
            f"min_air_temperature ({tmin}) must be strictly less than max_air_temperature ({tmax})"
        )
    return data


def normalize_option(value: str) -> str:
    """Convert translation keys to internal option values."""
    if value and value.startswith(f"{DOMAIN}."):
        value = value.split(".", 1)[1]
    prefixes = [
        "special_mode_",
        "day_",
        "period_",
        "bypass_mode_",
        "gwc_mode_",
        "filter_type_",
        "reset_type_",
        "modbus_port_",
        "modbus_baud_rate_",
        "modbus_parity_",
        "modbus_stop_bits_",
    ]
    for prefix in prefixes:
        if value.startswith(prefix):
            return value[len(prefix) :]
    return value
