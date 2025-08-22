"""Helpers for accessing register definitions used by the integration."""

from __future__ import annotations

"""Helpers for loading register definitions and grouping reads."""

from __future__ import annotations

import csv
import json
import logging
from functools import lru_cache
from typing import Dict, Iterable, List, Tuple

from .registers.loader import Register, get_all_registers


@lru_cache(maxsize=1)
def _register_map() -> Dict[str, Register]:
    """Load register definitions indexed by name."""

    return {reg.name: reg for reg in get_all_registers()}


def get_register_definition(name: str) -> Register:
    """Return the :class:`Register` definition for ``name``."""

    return _register_map()[name]

def _load_from_csv(directory: Path) -> List[Dict]:
    """Load register definitions from CSV files in a directory."""

    _LOGGER.warning(
        "Register CSV files are deprecated and will be removed in a future release. "
        "Please migrate to JSON."
    )
    rows: List[Dict] = []
    for csv_file in directory.glob("*.csv"):
        with csv_file.open(encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                try:
                    row["address_dec"] = int(row["address_dec"])
                except (KeyError, ValueError):
                    continue
                for field in ("multiplier", "resolution"):
                    if row.get(field) not in (None, ""):
                        try:
                            row[field] = float(row[field])
                        except ValueError:
                            row[field] = None
                if "enum" in row and row["enum"]:
                    try:
                        row["enum"] = json.loads(row["enum"])
                    except json.JSONDecodeError:
                        row["enum"] = None
                rows.append(row)
    return rows


@lru_cache(maxsize=1)
def _load_register_definitions() -> Dict[str, Dict]:
    """Load register definitions indexed by name."""

    if _REGISTERS_FILE.exists():
        with _REGISTERS_FILE.open("r", encoding="utf-8") as f:
            data = json.load(f)
        entries = data.get("registers", data)
    else:  # pragma: no cover - defensive fallback
        entries = _load_from_csv(_REGISTERS_FILE.parent)
    return {entry["name"]: entry for entry in entries}


def get_registers_by_function(function: str) -> Dict[str, int]:
    """Return mapping of register names to addresses for a function code."""

    return {reg.name: reg.address for reg in _register_map().values() if reg.function == function}


def get_register_definition(name: str) -> Dict:
    """Return full definition for a register by ``name``."""

    return _load_register_definitions().get(name, {})


def group_reads(addresses: Iterable[int], max_block_size: int = 64) -> List[Tuple[int, int]]:
    """Group register addresses into contiguous blocks."""

    sorted_addresses = sorted(set(addresses))
    if not sorted_addresses:
        return []

    groups: List[Tuple[int, int]] = []
    start = prev = sorted_addresses[0]
    for addr in sorted_addresses[1:]:
        if addr == prev + 1 and (addr - start + 1) <= max_block_size:
            prev = addr
            continue
        groups.append((start, prev - start + 1))
        start = prev = addr
    groups.append((start, prev - start + 1))
    return groups


__all__ = ["Register", "get_register_definition", "get_registers_by_function", "group_reads"]
__all__ = [
    "get_register_definition",
    "get_registers_by_function",
    "group_reads",
]

