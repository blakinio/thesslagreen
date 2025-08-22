"""Utility helpers for reading register definitions."""
from __future__ import annotations

from typing import Iterable, List, Tuple


def group_reads(addresses: Iterable[int], max_block_size: int = 64) -> List[Tuple[int, int]]:
    """Group register addresses into contiguous blocks.

    Args:
        addresses: Iterable of register addresses.
        max_block_size: Maximum number of registers per group.

    Returns:
        List of tuples ``(start_address, count)`` representing grouped reads.
    """
    # Remove duplicates and sort addresses
    sorted_addresses = sorted(set(addresses))
    if not sorted_addresses:
        return []

    groups: List[Tuple[int, int]] = []
    start = prev = sorted_addresses[0]
    for addr in sorted_addresses[1:]:
        # Continue current group if address is consecutive and block size limit not exceeded
        if addr == prev + 1 and (addr - start) < max_block_size:
            prev = addr
            continue

        # Otherwise, finalize current group and start a new one
        groups.append((start, prev - start + 1))
        start = prev = addr

    # Append the final group
    groups.append((start, prev - start + 1))
    return groups
