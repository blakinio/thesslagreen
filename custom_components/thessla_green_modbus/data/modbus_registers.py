"""Helpers for accessing Modbus register metadata from JSON."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict

from ..utils import _to_snake_case

__all__ = ["get_register_info", "get_register_infos"]

_REGISTER_CACHE: Dict[str, Dict[str, Any]] | None = None

_SPECIAL_BASE = {
    "date_time_rrmm": "date_time",
    "date_time_ddtt": "date_time",
    "date_time_ggmm": "date_time",
    "date_time_sscc": "date_time",
    "lock_date_rrmm": "lock_date",
    "lock_date_ddtt": "lock_date",
    "lock_date_ggmm": "lock_date",
    "lock_date_rr": "lock_date",
    "lock_date_mm": "lock_date",
    "lock_date_dd": "lock_date",
}


def _load_registers() -> Dict[str, Dict[str, Any]]:
    """Load register metadata from the bundled JSON file."""
    global _REGISTER_CACHE
    if _REGISTER_CACHE is not None:
        return _REGISTER_CACHE

    json_path = Path(__file__).with_name("modbus_registers.json")
    registers: Dict[str, Dict[str, Any]] = {}
    with json_path.open(encoding="utf-8") as jsonfile:
        data = json.load(jsonfile)
    for row in data.get("registers", []):
        name = _to_snake_case(row.get("name", ""))
        name = _SPECIAL_BASE.get(name, name)
        scale = row.get("scale") or 1
        registers[name] = {
            "function_code": row.get("function"),
            "address_hex": row.get("address_hex"),
            "address_dec": row.get("address_dec"),
            "access": row.get("access"),
            "description": row.get("description"),
            "min": row.get("min"),
            "max": row.get("max"),
            "default": row.get("default"),
            "scale": scale,
            "step": row.get("step", scale),
            "unit": row.get("unit"),
            "information": row.get("information"),
            "software_version": row.get("software_version"),
            "notes": row.get("notes"),
            "enum": row.get("enum"),
        }
    _REGISTER_CACHE = registers
    return registers


def get_register_info(register_name: str) -> Dict[str, Any] | None:
    """Return metadata for a given register name.

    The ``register_name`` should be provided in snake_case form. The returned
    dictionary includes fields like ``min``, ``max``, ``step`` and ``scale``.
    Returns ``None`` if the register is not found in the JSON file.
    """
    registers = _load_registers()
    return registers.get(register_name)


def get_register_infos(register_name: str) -> list[Dict[str, Any]]:
    """Return metadata for all registers matching a name.

    Some registers such as ``date_time`` span multiple consecutive Modbus
    addresses but share the same name in the JSON specification.  This helper
    returns metadata for each matching row preserving their order so callers
    can create individual mappings (e.g. ``date_time_1`` ... ``date_time_4``).
    """

    json_path = Path(__file__).with_name("modbus_registers.json")
    results: list[Dict[str, Any]] = []
    with json_path.open(encoding="utf-8") as jsonfile:
        data = json.load(jsonfile)
    for row in data.get("registers", []):
        name = _to_snake_case(row.get("name", ""))
        name = _SPECIAL_BASE.get(name, name)
        if name != register_name:
            continue
        scale = row.get("scale") or 1
        results.append(
            {
                "function_code": row.get("function"),
                "address_hex": row.get("address_hex"),
                "address_dec": row.get("address_dec"),
                "access": row.get("access"),
                "description": row.get("description"),
                "min": row.get("min"),
                "max": row.get("max"),
                "default": row.get("default"),
                "scale": scale,
                "step": row.get("step", scale),
                "unit": row.get("unit"),
                "information": row.get("information"),
                "software_version": row.get("software_version"),
                "notes": row.get("notes"),
                "enum": row.get("enum"),
            }
        )
    return results
