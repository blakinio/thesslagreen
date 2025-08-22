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

_REGISTERS_FILE = Path(__file__).parent / "registers" / "thessla_green_registers_full.json"


@lru_cache
def _load_register_definitions() -> Dict[str, Dict]:
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
