"""Helper functions for loading register definitions and grouping reads."""
from __future__ import annotations

import csv
import json
import logging
from functools import lru_cache
from pathlib import Path
from typing import Dict, Iterable, List, Tuple

_LOGGER = logging.getLogger(__name__)

_REGISTERS_FILE = Path(__file__).parent / "registers" / "thessla_green_registers_full.json"


def group_reads(addresses: Iterable[int], max_block_size: int = 64) -> List[Tuple[int, int]]:
    """Group register addresses into contiguous blocks.

    Args:
        addresses: Iterable of register addresses.
        max_block_size: Maximum number of registers per group.

    Returns:
        List of tuples ``(start_address, count)`` representing grouped reads.
    """
    sorted_addresses = sorted(set(addresses))
    if not sorted_addresses:
        return []

    groups: List[Tuple[int, int]] = []
    start = prev = sorted_addresses[0]
    for addr in sorted_addresses[1:]:
        if addr == prev + 1 and (addr - start) < max_block_size:
            prev = addr
            continue
        groups.append((start, prev - start + 1))
        start = prev = addr
    groups.append((start, prev - start + 1))
    return groups

"""Helper utilities for loading register metadata from JSON and grouping reads.

This module exposes small helper functions used by other parts of the
integration. Register definitions are stored in
``custom_components/thessla_green_modbus/registers/thessla_green_registers_full.json``.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Dict, Iterable, List, Tuple

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


@lru_cache
    """Load register definitions indexed by name."""
    if _REGISTERS_FILE.exists():
        with _REGISTERS_FILE.open("r", encoding="utf-8") as f:
            data = json.load(f)
    else:
        data = _load_from_csv(_REGISTERS_FILE.parent)
    """Load register definitions indexed by name from the JSON file."""
    with _REGISTERS_FILE.open("r", encoding="utf-8") as f:
        data = json.load(f)
    return {entry["name"]: entry for entry in data}


def get_registers_by_function(function: str) -> Dict[str, int]:
    """Return mapping of register names to addresses for a given function."""
    regs: Dict[str, int] = {}
    for name, info in _load_register_definitions().items():
        if info.get("function") == function:
            regs[name] = int(info.get("address_dec"))
    return regs


def get_register_definition(name: str) -> Dict:
    """Return full definition for a register by name."""
    return _load_register_definitions().get(name, {})

def group_reads(addresses: Iterable[int], max_block_size: int = 64) -> List[Tuple[int, int]]:
    """Group register addresses into contiguous blocks up to ``max_block_size``.

    Args:
        addresses: Iterable of register addresses.
        max_block_size: Maximum number of registers in a group.

    Returns:
        List of tuples ``(start_address, count)`` representing grouped reads.
    """
    sorted_addresses = sorted(set(addresses))
    if not sorted_addresses:
        return []

    groups: List[Tuple[int, int]] = []
    start = prev = sorted_addresses[0]
    for addr in sorted_addresses[1:]:
        if addr == prev + 1 and (addr - start) < max_block_size:
            prev = addr
            continue
        groups.append((start, prev - start + 1))
        start = prev = addr
    groups.append((start, prev - start + 1))
    return groups