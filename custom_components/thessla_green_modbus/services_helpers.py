"""Shared helpers for service handlers."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, cast

import voluptuous as vol
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers.service import async_extract_entity_ids

from .const import DOMAIN
from .modbus_exceptions import ConnectionException, ModbusException


def extract_entity_ids(hass: HomeAssistant, call: ServiceCall) -> set[str]:
    """Return entity IDs from a service call."""
    if not call.data.get("entity_id"):
        return set()
    return cast(set[str], async_extract_entity_ids(hass, call))


def iter_target_coordinators(
    hass: HomeAssistant,
    call: ServiceCall,
    get_coordinator_from_entity_id: Callable[[HomeAssistant, str], Any],
) -> list[tuple[str, Any]]:
    """Resolve entity IDs to coordinator instances, skipping missing ones."""
    targets: list[tuple[str, Any]] = []
    for entity_id in extract_entity_ids(hass, call):
        coordinator = get_coordinator_from_entity_id(hass, entity_id)
        if coordinator is None:
            continue
        targets.append((entity_id, coordinator))
    return targets


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
            f"min_air_temperature ({tmin}) must be strictly less than " f"max_air_temperature ({tmax})"
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


def clamp_airflow_rate(coordinator: Any, airflow_rate: int) -> int:
    """Clamp airflow_rate to the coordinator's reported min/max percentages."""
    data = getattr(coordinator, "data", {}) or {}
    min_pct = data.get("min_percentage")
    max_pct = data.get("max_percentage")
    try:
        min_val = int(min_pct) if min_pct is not None else 0
    except (TypeError, ValueError):
        min_val = 0
    try:
        max_val = int(max_pct) if max_pct is not None else 150
    except (TypeError, ValueError):
        max_val = 150
    min_val = max(0, min_val)
    max_val = min(150, max_val)
    if max_val < min_val:
        max_val = min_val
    return max(min_val, min(max_val, int(airflow_rate)))


async def write_register(
    coordinator: Any,
    register: str,
    value: Any,
    entity_id: str,
    action: str,
    logger: Any,
) -> bool:
    """Write to a register with error handling."""
    try:
        return bool(await coordinator.async_write_register(register, value, refresh=False))
    except (ModbusException, ConnectionException) as err:
        logger.error("Failed to %s for %s: %s", action, entity_id, err)
        return False
