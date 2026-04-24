"""Helpers for register lookup/grouping/decoding used by coordinator."""

from __future__ import annotations

import logging
from typing import Any

from .const import SENSOR_UNAVAILABLE, SENSOR_UNAVAILABLE_REGISTERS
from .register_defs_cache import get_register_definitions

_LOGGER = logging.getLogger(__name__.rsplit(".", maxsplit=1)[0])


def find_register_name(
    reverse_maps: dict[str, dict[int, str]], register_type: str, address: int
) -> str | None:
    """Find register name by address using pre-built reverse maps."""
    return reverse_maps.get(register_type, {}).get(address)


def process_register_value(register_name: str, value: int) -> Any:
    """Decode a raw register value using its definition."""
    if register_name in {"dac_supply", "dac_exhaust", "dac_heater", "dac_cooler"} and not (
        0 <= value <= 4095
    ):
        _LOGGER.warning("Register %s out of range for DAC: %s", register_name, value)
        return None
    try:
        definition = get_register_definitions()[register_name]
    except KeyError:
        _LOGGER.error("Unknown register name: %s", register_name)
        return False

    if value == SENSOR_UNAVAILABLE:
        if definition.is_temperature():
            _LOGGER.debug(
                "Processed %s: raw=%s value=None (temperature sentinel)",
                register_name,
                value,
            )
            return None
        if register_name in SENSOR_UNAVAILABLE_REGISTERS:
            _LOGGER.debug(
                "Processed %s: raw=%s value=SENSOR_UNAVAILABLE",
                register_name,
                value,
            )
            return SENSOR_UNAVAILABLE

    raw_value = value
    if definition.is_temperature() and isinstance(raw_value, int) and raw_value > 32767:
        raw_value -= 65536

    decoded = definition.decode(raw_value)

    if decoded == SENSOR_UNAVAILABLE:
        _LOGGER.debug(
            "Processed %s: raw=%s value=SENSOR_UNAVAILABLE (post-decode)",
            register_name,
            value,
        )
        return SENSOR_UNAVAILABLE

    if register_name in {"supply_flow_rate", "exhaust_flow_rate"} and isinstance(decoded, int):
        if decoded > 32767:
            decoded -= 65536

    if definition.enum is not None and isinstance(decoded, str) and isinstance(value, int):
        decoded = value

    _LOGGER.debug("Processed %s: raw=%s value=%s", register_name, value, decoded)
    return decoded


def create_consecutive_groups(registers: dict[str, int]) -> list[tuple[int, int, dict[str, int]]]:
    """Return grouped address ranges with key maps."""
    ordered = sorted(registers.items(), key=lambda item: item[1])
    if not ordered:
        return []
    groups: list[tuple[int, int, dict[str, int]]] = []
    start = ordered[0][1]
    prev = start
    key_map: dict[str, int] = {ordered[0][0]: ordered[0][1]}
    for key, addr in ordered[1:]:
        if addr == prev + 1:
            key_map[key] = addr
        else:
            groups.append((start, prev - start + 1, dict(key_map)))
            start = addr
            key_map = {key: addr}
        prev = addr
    groups.append((start, prev - start + 1, dict(key_map)))
    return groups
