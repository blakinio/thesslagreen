"""Helper utilities for working with register definitions.

This module exposes thin wrappers around the JSON based register loader.  It is
kept for backward compatibility with older helper scripts which expected to
fetch register information via ``get_register_definition``.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Dict, Iterable, List, Tuple

from .registers import (
    Register,
    get_all_registers,
    get_registers_by_function as _get_registers_by_function,
)


@lru_cache(maxsize=1)
def _register_map() -> Dict[str, Register]:
    """Return register definitions indexed by name."""

    return {reg.name: reg for reg in get_all_registers()}


def get_register_definition(name: str) -> Register:
    """Return the :class:`Register` definition for ``name``."""

    return _register_map()[name]


def get_registers_by_function(function: str) -> Dict[str, int]:
    """Return mapping of register names to addresses for ``function``."""

    return {r.name: r.address for r in _get_registers_by_function(function)}


def group_reads(addresses: Iterable[int], max_block_size: int = 64) -> List[Tuple[int, int]]:
    """Group raw addresses into contiguous read blocks."""

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

