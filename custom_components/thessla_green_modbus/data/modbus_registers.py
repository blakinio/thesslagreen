"""Helpers for accessing Modbus register metadata from bundled specification."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict

from ..registers import get_all_registers, get_registers_hash

from ..utils import _to_snake_case

__all__ = [
    "get_register_info",
    "get_register_infos",
    "scale_from_raw",
    "scale_to_raw",
    "apply_resolution",
    "get_enum_mapping",
    "map_enum_value",
]

_REGISTER_CACHE: Dict[str, Dict[str, Any]] | None = None
_REGISTER_HASH: str | None = None
_CSV_WARNING_LOGGED = False

_LOGGER = logging.getLogger(__name__)


def _warn_csv_usage(path: Path | None = None) -> None:
    """Log that CSV register files are no longer supported."""
    global _CSV_WARNING_LOGGED
    if _CSV_WARNING_LOGGED:
        return
    if path:
        _LOGGER.warning(
            "Ignoring external register definition file %s; register metadata is now fully provided by JSON",
            path,
        )
    else:
        _LOGGER.info(
            "Register metadata fully migrated to JSON; CSV files are no longer supported",
        )
    _CSV_WARNING_LOGGED = True


def _load_registers() -> Dict[str, Dict[str, Any]]:
    """Load register metadata from bundled JSON data."""
    global _REGISTER_CACHE, _REGISTER_HASH
    current_hash = get_registers_hash()
    if _REGISTER_CACHE is not None and _REGISTER_HASH == current_hash:
        return _REGISTER_CACHE
    registers: Dict[str, Dict[str, Any]] = {}
    for reg in get_all_registers():
        if not reg.name:
            continue
        scale = reg.multiplier or 1
        step = reg.resolution or scale
        registers[reg.name] = {
            "function_code": reg.function,
            "address_dec": reg.address,
            "access": reg.access,
            "description": reg.description,
            "min": reg.min,
            "max": reg.max,
            "default": reg.default,
            "scale": scale,
            "step": step,
            "unit": reg.unit,
            "information": reg.information,
        }
    _REGISTER_CACHE = registers
    _REGISTER_HASH = current_hash
    return registers


def get_register_info(register_name: str) -> Dict[str, Any] | None:
    """Return metadata for a given register name.

    The ``register_name`` should be provided in snake_case form. The returned
    dictionary includes fields like ``min``, ``max``, ``step`` and ``scale``.
    Returns ``None`` if the register is not found.
    """
    registers = _load_registers()
    return registers.get(register_name)


def get_register_infos(register_name: str) -> list[Dict[str, Any]]:
    """Return metadata for all registers matching a name."""

    results: list[Dict[str, Any]] = []
    for reg in get_all_registers():
        if reg.name != register_name:
            continue
        scale = reg.multiplier or 1
        step = reg.resolution or scale
        results.append(
            {
                "function_code": reg.function,
                "address_dec": reg.address,
                "access": reg.access,
                "description": reg.description,
                "min": reg.min,
                "max": reg.max,
                "default": reg.default,
                "scale": scale,
                "step": step,
                "unit": reg.unit,
                "information": reg.information,
            }
        )
    return results


def scale_from_raw(register_name: str, value: float | int) -> float | int:
    """Scale a raw register value using its configured multiplier."""

    info = get_register_info(register_name)
    if not info:
        return value
    multiplier = info.get("scale", 1) or 1
    return value * multiplier


def scale_to_raw(register_name: str, value: float | int) -> int | float:
    """Convert a user value back to raw register form using the multiplier."""

    info = get_register_info(register_name)
    if not info:
        return value
    multiplier = info.get("scale", 1) or 1
    return int(round(float(value) / multiplier))


def apply_resolution(register_name: str, value: float | int) -> float | int:
    """Round ``value`` to the register's resolution if specified."""

    info = get_register_info(register_name)
    if not info:
        return value
    resolution = info.get("step") or info.get("scale") or 1
    return round(float(value) / resolution) * resolution


def _parse_enum(info: str | None) -> dict[str, int] | None:
    """Parse ``"0 - off; 1 - on"`` style strings into a mapping."""

    if not info or "-" not in info:
        return None
    mapping: dict[str, int] = {}
    for part in info.split(";"):
        part = part.strip()
        if not part:
            continue
        try:
            num_str, label = part.split("-", 1)
            mapping[_to_snake_case(label.strip())] = int(num_str.strip())
        except ValueError:
            continue
    return mapping or None


def get_enum_mapping(register_name: str) -> dict[str, int] | None:
    """Return enumeration mapping for ``register_name`` if available."""

    info = get_register_info(register_name)
    if not info:
        return None
    return _parse_enum(info.get("unit")) or _parse_enum(info.get("information"))


def map_enum_value(register_name: str, value: int | str) -> int | str | None:
    """Map between numeric enum value and its textual representation."""

    mapping = get_enum_mapping(register_name)
    if not mapping:
        return value
    if isinstance(value, str):
        return mapping.get(_to_snake_case(value))
    for label, number in mapping.items():
        if number == value:
            return label
    return None
