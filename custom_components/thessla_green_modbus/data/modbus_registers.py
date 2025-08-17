"""Helpers for accessing Modbus register metadata from CSV."""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Any, Dict

from ..utils import _to_snake_case

__all__ = ["get_register_info"]

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
