"""Helper functions for loading register definitions and grouping reads."""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Dict, Iterable, List, Tuple

_REGISTERS_FILE = Path(__file__).parent / "registers" / "thessla_green_registers_full.json"


@lru_cache
def _load_register_definitions() -> Dict[str, Dict]:
    """Load register definitions indexed by name."""
    with _REGISTERS_FILE.open("r", encoding="utf-8") as f:
        data = json.load(f)
    return {entry["name"]: entry for entry in data}


def get_registers_by_function(function: str) -> Dict[str, int]:
    """Return mapping of register names to addresses for a given function."""
    regs = {}
    for name, info in _load_register_definitions().items():
        if info.get("function") == function:
            regs[name] = int(info.get("address_dec"))
    return regs


def get_register_definition(name: str) -> Dict:
    """Return full definition for a register name."""
    return _load_register_definitions().get(name, {})


def group_reads(addresses: Iterable[int], max_gap: int = 10, max_batch: int = 16) -> List[Tuple[int, int]]:
    """Group register addresses for efficient batch reads."""
    sorted_addrs = sorted(set(addresses))
    if not sorted_addrs:
        return []

    groups: List[Tuple[int, int]] = []
    start = prev = sorted_addrs[0]
    for addr in sorted_addrs[1:]:
        if addr - prev > max_gap or (addr - start + 1) > max_batch:
            groups.append((start, prev - start + 1))
            start = addr
        prev = addr
    groups.append((start, prev - start + 1))
    return groups
