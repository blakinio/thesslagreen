"""Reusable validation and normalization helpers for services."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from .const import DOMAIN

FILTER_TYPE_MAP = {"presostat": 1, "flat_filters": 2, "cleanpad": 3, "cleanpad_pure": 4}
BAUD_MAP = {
    "4800": 0,
    "9600": 1,
    "14400": 2,
    "19200": 3,
    "28800": 4,
    "38400": 5,
    "57600": 6,
    "76800": 7,
    "115200": 8,
}
PARITY_MAP = {"none": 0, "even": 1, "odd": 2}
STOP_MAP = {"1": 0, "2": 1}


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


def normalize_modbus_options(normalize: Any, data: dict[str, Any]) -> tuple[str, str | None, str | None, str | None]:
    """Normalize set_modbus_parameters payload options."""
    port = normalize(data["port"])
    baud_rate = data.get("baud_rate")
    parity = data.get("parity")
    stop_bits = data.get("stop_bits")
    return (
        port,
        normalize(baud_rate) if baud_rate else None,
        normalize(parity) if parity else None,
        normalize(stop_bits) if stop_bits else None,
    )
