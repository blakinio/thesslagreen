"""Capability inference rules for device scanner.

Maps capability attributes to keywords that indicate their presence when
found in register names.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

CAPABILITY_PATTERNS: Mapping[str, Sequence[str]] = {
    "heating_system": ("heating", "heater"),
    "cooling_system": ("cooling", "cooler"),
    "bypass_system": ("bypass",),
    "gwc_system": ("gwc",),
    # Constant flow capable devices expose registers related to airflow and
    # flow rates. These keywords cover typical naming variations used by the
    # firmware for that feature.
    "constant_flow": ("constant_flow", "cf_", "air_flow", "flow_rate"),
    # Weekly schedule functionality is indicated by registers referencing
    # schedules, airing or related settings.
    "weekly_schedule": ("schedule", "weekly", "airing", "setting"),
}

_TEMPERATURE_CAPABILITIES: Mapping[str, str] = {
    "outside_temperature": "sensor_outside_temperature",
    "supply_temperature": "sensor_supply_temperature",
    "exhaust_temperature": "sensor_exhaust_temperature",
    "fpx_temperature": "sensor_fpx_temperature",
    "duct_supply_temperature": "sensor_duct_supply_temperature",
    "gwc_temperature": "sensor_gwc_temperature",
    "ambient_temperature": "sensor_ambient_temperature",
    "heating_temperature": "sensor_heating_temperature",
}


def capability_block_reason(register_name: str, capabilities: Any) -> str | None:
    """Return a reason string when a register should be skipped."""

    temp_cap = _TEMPERATURE_CAPABILITIES.get(register_name)
    if temp_cap is not None and not getattr(capabilities, temp_cap, False):
        return f"{temp_cap} not supported"

    for cap_name, patterns in CAPABILITY_PATTERNS.items():
        if not getattr(capabilities, cap_name, False) and any(
            pattern in register_name for pattern in patterns
        ):
            return f"{cap_name} not supported"

    return None


def firmware_block_reason(register_name: str, firmware: Any) -> str | None:
    """Reject readable reserved words that older Home firmware cannot control.

    Home 06.2021.01 p.12: airingSwitchCoef requires 4.85; openWindowCoef
    requires 3.72 / 4.72. Home 3.11 reads zero and echoes writes without
    applying them, so a successful probe cannot establish these capabilities.
    Unknown firmware keeps discovery behavior; do not guess its version.
    """
    if register_name not in ("airing_switch_coef", "open_window_coef"):
        return None
    if not isinstance(firmware, str):
        return None
    parts = firmware.strip().lstrip("vV").split(".")
    if len(parts) < 2 or not all(part.isdigit() for part in parts[:2]):
        return None
    major, minor = map(int, parts[:2])
    if register_name == "airing_switch_coef" and (major == 3 or (major == 4 and minor < 85)):
        return "requires firmware 4.85 or later on the 4.x controller"
    if register_name == "open_window_coef" and major in (3, 4) and minor < 72:
        return "requires firmware 3.72 / 4.72 or later"
    return None


__all__ = ["CAPABILITY_PATTERNS", "capability_block_reason", "firmware_block_reason"]
