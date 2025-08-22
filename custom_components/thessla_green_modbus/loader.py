"""Helpers for loading register definitions and metadata.

The integration historically read ``modbus_registers.csv`` from multiple
locations.  To simplify maintenance, the parsing logic lives in this module and
other modules import the constants or helper functions from here.  The loader
currently reads the bundled CSV file but logs a warning as this behaviour is
kept only for backwards compatibility – a dedicated registers package may
replace it in the future.
"""

from __future__ import annotations

import csv
import logging
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from .utils import _to_snake_case, BCD_TIME_PREFIXES

__all__ = [
    "COIL_REGISTERS",
    "DISCRETE_INPUT_REGISTERS",
    "INPUT_REGISTERS",
    "HOLDING_REGISTERS",
    "MULTI_REGISTER_SIZES",
    "get_register_info",
    "get_register_infos",
    "load_register_definitions",
]

_LOGGER = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Internal caches
# ---------------------------------------------------------------------------

_REGISTER_MAP: Dict[str, Dict[int, str]] | None = None
_REGISTER_RANGES: Dict[str, Tuple[Optional[int], Optional[int]]] | None = None
_REGISTER_VERSIONS: Dict[str, Tuple[int, ...]] | None = None
_REGISTER_INFO: Dict[str, Dict[str, Any]] | None = None
_REGISTER_INFO_LISTS: Dict[str, List[Dict[str, Any]]] | None = None


def _parse_number(value: str | None) -> float | None:
    """Convert a CSV field to a number when possible."""
    if value is None:
        return None
    value = value.strip()
    if not value:
        return None
    try:
        return int(value)
    except ValueError:
        try:
            return float(value)
        except ValueError:
            return None


def _load_from_csv() -> None:
    """Load register definitions from the bundled CSV file."""
    global COIL_REGISTERS, DISCRETE_INPUT_REGISTERS, INPUT_REGISTERS, HOLDING_REGISTERS
    global MULTI_REGISTER_SIZES, _REGISTER_MAP, _REGISTER_RANGES, _REGISTER_VERSIONS
    global _REGISTER_INFO, _REGISTER_INFO_LISTS

    csv_path = Path(__file__).parent / "data" / "modbus_registers.csv"
    _LOGGER.warning(
        "Loading register definitions from CSV; this compatibility layer "
        "will be removed in a future release",
    )

    coil_rows: List[Tuple[str, int, Optional[int], Optional[int], Optional[Tuple[int, ...]]]] = []
    discrete_rows: List[Tuple[str, int, Optional[int], Optional[int], Optional[Tuple[int, ...]]]] = []
    input_rows: List[Tuple[str, int, Optional[int], Optional[int], Optional[Tuple[int, ...]]]] = []
    holding_rows: List[Tuple[str, int, Optional[int], Optional[int], Optional[Tuple[int, ...]]]] = []

    COIL_REGISTERS = {}
    DISCRETE_INPUT_REGISTERS = {}
    INPUT_REGISTERS = {}
    HOLDING_REGISTERS = {}
    MULTI_REGISTER_SIZES = {}
    _REGISTER_RANGES = {}
    _REGISTER_VERSIONS = {}
    _REGISTER_INFO = {}
    _REGISTER_INFO_LISTS = defaultdict(list)
    info_map: Dict[str, Dict[str, Any]] = {}
    info_lists: Dict[str, List[Dict[str, Any]]] = _REGISTER_INFO_LISTS

    with csv_path.open(encoding="utf-8", newline="") as csvfile:
        reader = csv.DictReader(
            row for row in csvfile if row.strip() and not row.lstrip().startswith("#")
        )
        for row in reader:
            func = row.get("Function_Code")
            if not func:
                continue
            name_raw = row.get("Register_Name")
            if not name_raw:
                continue
            name = _to_snake_case(name_raw)
            try:
                addr = int(row.get("Address_DEC", 0))
            except (TypeError, ValueError):
                continue

            min_raw = row.get("Min")
            max_raw = row.get("Max")
            version_raw = row.get("Software_Version")

            def _parse_range(raw: str | None) -> int | None:
                if raw in (None, ""):
                    return None
                text = str(raw).split("#", 1)[0].strip()
                if not text:
                    return None
                try:
                    if text.lower().startswith(("0x", "+0x", "-0x")):
                        return int(text, 0)
                    return int(float(text))
                except ValueError:
                    _LOGGER.warning("Ignoring non-numeric range value for %s: %s", name, raw)
                    return None

            min_val = _parse_range(min_raw)
            max_val = _parse_range(max_raw)

            if name.startswith(BCD_TIME_PREFIXES):
                min_val = ((min_val // 10) << 12 | (min_val % 10) << 8) if min_val is not None else 0
                max_val = ((max_val // 10) << 12 | (max_val % 10) << 8 | 0x59) if max_val is not None else 0x2359
            elif name.startswith(("setting_summer_", "setting_winter_")):
                min_val = (min_val << 8) if min_val is not None else 0
                max_val = ((max_val << 8) | 0xFF) if max_val is not None else 0xFFFF

            ver_tuple: Optional[Tuple[int, ...]] = None
            if version_raw:
                try:
                    ver_tuple = tuple(int(part) for part in str(version_raw).split("."))
                except ValueError:
                    ver_tuple = None

            row_info = {
                "function_code": func,
                "address_hex": row.get("Address_HEX"),
                "address_dec": addr,
                "access": row.get("Access"),
                "description": row.get("Description"),
                "min": _parse_number(min_raw),
                "max": _parse_number(max_raw),
                "default": _parse_number(row.get("Default_Value")),
                "scale": _parse_number(row.get("Multiplier")) or 1,
                "step": _parse_number(row.get("Multiplier")) or 1,
                "unit": row.get("Unit"),
                "information": row.get("Information"),
                "software_version": version_raw,
                "notes": row.get("Notes"),
            }
            info_lists[name].append(row_info)
            info_map.setdefault(name, row_info)

            target = None
            if func == "01":
                target = coil_rows
            elif func == "02":
                target = discrete_rows
            elif func == "04":
                target = input_rows
            elif func == "03":
                target = holding_rows
            if target is not None:
                target.append((name, addr, min_val, max_val, ver_tuple))

    def _build_map(
        rows: List[Tuple[str, int, Optional[int], Optional[int], Optional[Tuple[int, ...]]]]
    ) -> Tuple[Dict[str, int], Dict[int, str]]:
        rows.sort(key=lambda item: item[1])
        counts: Dict[str, int] = defaultdict(int)
        for name, *_ in rows:
            counts[name] += 1
        name_map: Dict[str, int] = {}
        addr_map: Dict[int, str] = {}
        seen: Dict[str, int] = defaultdict(int)
        for name, addr, min_val, max_val, ver in rows:
            key = name
            if counts[name] > 1:
                seen[name] += 1
                key = f"{name}_{seen[name]}"
                if seen[name] == 1:
                    MULTI_REGISTER_SIZES[key] = counts[name]
            name_map[key] = addr
            addr_map[addr] = key
            if min_val is not None or max_val is not None:
                _REGISTER_RANGES[key] = (min_val, max_val)
            if ver is not None:
                _REGISTER_VERSIONS[key] = ver
        return name_map, addr_map

    COIL_REGISTERS, coil_addr = _build_map(coil_rows)
    DISCRETE_INPUT_REGISTERS, discrete_addr = _build_map(discrete_rows)
    INPUT_REGISTERS, input_addr = _build_map(input_rows)
    HOLDING_REGISTERS, holding_addr = _build_map(holding_rows)

    _REGISTER_MAP = {
        "01": coil_addr,
        "02": discrete_addr,
        "04": input_addr,
        "03": holding_addr,
    }
    _REGISTER_INFO = info_map
    _REGISTER_INFO_LISTS = info_lists


def _ensure_loaded() -> None:
    if _REGISTER_MAP is None:
        _load_from_csv()


def load_register_definitions() -> Tuple[
    Dict[str, Dict[int, str]],
    Dict[str, Tuple[Optional[int], Optional[int]]],
    Dict[str, Tuple[int, ...]],
]:
    """Return register map, ranges and firmware versions for the scanner."""
    _ensure_loaded()
    assert _REGISTER_MAP is not None
    assert _REGISTER_RANGES is not None
    assert _REGISTER_VERSIONS is not None
    return _REGISTER_MAP, _REGISTER_RANGES, _REGISTER_VERSIONS


def get_register_info(register_name: str) -> Dict[str, Any] | None:
    """Return metadata for a register name."""
    _ensure_loaded()
    assert _REGISTER_INFO is not None
    return _REGISTER_INFO.get(register_name)


def get_register_infos(register_name: str) -> List[Dict[str, Any]]:
    """Return metadata for all registers matching a base name."""
    _ensure_loaded()
    assert _REGISTER_INFO_LISTS is not None
    return list(_REGISTER_INFO_LISTS.get(register_name, []))


# Load CSV data on import so the public constants are available
COIL_REGISTERS: Dict[str, int] = {}
DISCRETE_INPUT_REGISTERS: Dict[str, int] = {}
INPUT_REGISTERS: Dict[str, int] = {}
HOLDING_REGISTERS: Dict[str, int] = {}
MULTI_REGISTER_SIZES: Dict[str, int] = {}

_ensure_loaded()

