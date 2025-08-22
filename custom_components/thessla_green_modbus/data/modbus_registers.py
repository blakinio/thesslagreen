"""Helpers for accessing Modbus register metadata from CSV."""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Any, Dict

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


def _parse_number(value: str | None) -> float | None:
    """Convert a CSV field to a float if possible."""
    if value is None:
        return None
    value = value.strip()
    if not value:
        return None
    try:
        # Try integer first to avoid floating point artifacts
        return int(value)
    except ValueError:
        try:
            return float(value)
        except ValueError:
            return None


def _load_registers() -> Dict[str, Dict[str, Any]]:
    """Load register metadata from the bundled CSV file."""
    global _REGISTER_CACHE
    if _REGISTER_CACHE is not None:
        return _REGISTER_CACHE

    csv_path = Path(__file__).with_name("modbus_registers.csv")
    registers: Dict[str, Dict[str, Any]] = {}
    with csv_path.open(encoding="utf-8", newline="") as csvfile:
        reader = csv.DictReader(
            row for row in csvfile if row.strip() and not row.lstrip().startswith("#")
        )
        for row in reader:
            name = _to_snake_case(row["Register_Name"])
            scale = _parse_number(row.get("Multiplier")) or 1
            registers[name] = {
                "function_code": row.get("Function_Code"),
                "address_hex": row.get("Address_HEX"),
                "address_dec": _parse_number(row.get("Address_DEC")),
                "access": row.get("Access"),
                "description": row.get("Description"),
                "min": _parse_number(row.get("Min")),
                "max": _parse_number(row.get("Max")),
                "default": _parse_number(row.get("Default_Value")),
                "scale": scale,
                "step": scale,
                "unit": row.get("Unit"),
                "information": row.get("Information"),
                "software_version": row.get("Software_Version"),
                "notes": row.get("Notes"),
            }
    _REGISTER_CACHE = registers
    return registers


def get_register_info(register_name: str) -> Dict[str, Any] | None:
    """Return metadata for a given register name.

    The ``register_name`` should be provided in snake_case form. The returned
    dictionary includes fields like ``min``, ``max``, ``step`` and ``scale``.
    Returns ``None`` if the register is not found in the CSV.
    """
    registers = _load_registers()
    return registers.get(register_name)


def get_register_infos(register_name: str) -> list[Dict[str, Any]]:
    """Return metadata for all registers matching a name.

    Some registers such as ``date_time`` span multiple consecutive Modbus
    addresses but share the same name in the CSV specification.  This helper
    returns metadata for each matching row preserving their order so callers
    can create individual mappings (e.g. ``date_time_1`` ... ``date_time_4``).
    """

    csv_path = Path(__file__).with_name("modbus_registers.csv")
    results: list[Dict[str, Any]] = []
    with csv_path.open(encoding="utf-8", newline="") as csvfile:
        reader = csv.DictReader(
            row for row in csvfile if row.strip() and not row.lstrip().startswith("#")
        )
        for row in reader:
            name = _to_snake_case(row["Register_Name"])
            if name != register_name:
                continue
            scale = _parse_number(row.get("Multiplier")) or 1
            results.append(
                {
                    "function_code": row.get("Function_Code"),
                    "address_hex": row.get("Address_HEX"),
                    "address_dec": _parse_number(row.get("Address_DEC")),
                    "access": row.get("Access"),
                    "description": row.get("Description"),
                    "min": _parse_number(row.get("Min")),
                    "max": _parse_number(row.get("Max")),
                    "default": _parse_number(row.get("Default_Value")),
                    "scale": scale,
                    "step": scale,
                    "unit": row.get("Unit"),
                    "information": row.get("Information"),
                    "software_version": row.get("Software_Version"),
                    "notes": row.get("Notes"),
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
