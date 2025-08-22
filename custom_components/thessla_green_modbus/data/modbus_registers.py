"""Helpers for accessing Modbus register metadata from bundled specification."""

from __future__ import annotations

import csv
import json
import logging
from pathlib import Path
from typing import Any, Dict

from ..utils import _to_snake_case

__all__ = ["get_register_info", "get_register_infos"]

_REGISTER_CACHE: Dict[str, Dict[str, Any]] | None = None
_JSON_CACHE: list[Dict[str, Any]] | None = None
_CSV_WARNING_LOGGED = False

_LOGGER = logging.getLogger(__name__)


def _parse_number(value: Any) -> float | None:
    """Convert a value to a float if possible."""
    if value is None:
        return None
    value = str(value).strip()
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


def _warn_csv_usage() -> None:
    """Log a warning if the deprecated CSV is used."""
    global _CSV_WARNING_LOGGED
    if not _CSV_WARNING_LOGGED:
        _LOGGER.warning("Loading register metadata from deprecated CSV file")
        _CSV_WARNING_LOGGED = True


def _load_json_registers() -> list[Dict[str, Any]] | None:
    """Load registers from the bundled JSON specification."""
    global _JSON_CACHE
    if _JSON_CACHE is not None:
        return _JSON_CACHE
    json_path = (
        Path(__file__).resolve().parent.parent
        / "registers"
        / "thessla_green_registers_full.json"
    )
    if not json_path.exists():
        return None
    with json_path.open(encoding="utf-8") as f:
        data = json.load(f)
    _JSON_CACHE = data.get("registers", [])
    return _JSON_CACHE


def _load_registers() -> Dict[str, Dict[str, Any]]:
    """Load register metadata from the bundled JSON or CSV file."""
    global _REGISTER_CACHE
    if _REGISTER_CACHE is not None:
        return _REGISTER_CACHE

    json_regs = _load_json_registers()
    if json_regs is not None:
        registers: Dict[str, Dict[str, Any]] = {}
        for reg in json_regs:
            name = _to_snake_case(reg.get("name", ""))
            scale = (
                _parse_number(reg.get("multiplier"))
                or _parse_number(reg.get("scale"))
                or 1
            )
            registers[name] = {
                "function_code": reg.get("function"),
                "address_hex": reg.get("address_hex"),
                "address_dec": _parse_number(reg.get("address_dec")),
                "access": reg.get("access"),
                "description": reg.get("description"),
                "min": _parse_number(reg.get("min")),
                "max": _parse_number(reg.get("max")),
                "default": _parse_number(reg.get("default")),
                "scale": scale,
                "step": scale,
                "unit": reg.get("unit"),
                "information": reg.get("information"),
                "software_version": reg.get("software_version"),
                "notes": reg.get("notes"),
            }
        _REGISTER_CACHE = registers
        return registers

    _warn_csv_usage()
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
    Returns ``None`` if the register is not found.
    """
    registers = _load_registers()
    return registers.get(register_name)


def get_register_infos(register_name: str) -> list[Dict[str, Any]]:
    """Return metadata for all registers matching a name."""

    json_regs = _load_json_registers()
    results: list[Dict[str, Any]] = []
    if json_regs is not None:
        for reg in json_regs:
            name = _to_snake_case(reg.get("name", ""))
            if name != register_name:
                continue
            scale = (
                _parse_number(reg.get("multiplier"))
                or _parse_number(reg.get("scale"))
                or 1
            )
            results.append(
                {
                    "function_code": reg.get("function"),
                    "address_hex": reg.get("address_hex"),
                    "address_dec": _parse_number(reg.get("address_dec")),
                    "access": reg.get("access"),
                    "description": reg.get("description"),
                    "min": _parse_number(reg.get("min")),
                    "max": _parse_number(reg.get("max")),
                    "default": _parse_number(reg.get("default")),
                    "scale": scale,
                    "step": scale,
                    "unit": reg.get("unit"),
                    "information": reg.get("information"),
                    "software_version": reg.get("software_version"),
                    "notes": reg.get("notes"),
                }
            )
        return results

    _warn_csv_usage()
    csv_path = Path(__file__).with_name("modbus_registers.csv")
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
