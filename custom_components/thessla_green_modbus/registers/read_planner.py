"""Read-planning helpers for register block grouping."""

from __future__ import annotations

from collections.abc import Callable, Iterable

from .. import const
from .definition import ReadPlan
from .register_def import RegisterDef


def group_reads(
    addresses: Iterable[int],
    max_block_size: int | None = None,
    boundaries: frozenset[int] | None = None,
) -> list[tuple[int, int]]:
    """Group raw register addresses into contiguous read blocks.

    The addresses are sorted and sequential ranges are merged up to
    ``max_block_size`` entries.  The returned list contains ``(start, length)``
    tuples suitable for bulk Modbus read operations.

    ``boundaries`` is an optional set of addresses at which a new batch must
    start regardless of contiguity.  Use this to prevent batches from spanning
    register regions that a device firmware cannot handle in a single request
    (e.g. AirPack4 FW 3.11 rejects FC03 reads that cross addr 15→16).
    """

    if max_block_size is None:
        max_block_size = const.MAX_REGS_PER_REQUEST
    max_block_size = min(max_block_size, const.MAX_REGS_PER_REQUEST)
    sorted_addresses = sorted(set(addresses))
    if not sorted_addresses:
        return []

    groups: list[tuple[int, int]] = []
    start = prev = sorted_addresses[0]
    for addr in sorted_addresses[1:]:
        force_split = boundaries is not None and addr in boundaries
        if not force_split and addr == prev + 1 and (addr - start + 1) <= max_block_size:
            prev = addr
            continue
        groups.append((start, prev - start + 1))
        start = prev = addr
    groups.append((start, prev - start + 1))
    return groups


def chunk_register_range(
    start: int,
    count: int,
    max_block_size: int | None = None,
) -> list[tuple[int, int]]:
    """Split a contiguous register range into safe-sized chunks."""

    if count <= 0:
        return []

    if max_block_size is None:
        max_block_size = const.MAX_REGS_PER_REQUEST
    max_block_size = min(max_block_size, const.MAX_REGS_PER_REQUEST)
    if max_block_size < 1:
        max_block_size = 1

    chunks: list[tuple[int, int]] = []
    remaining = count
    current = start
    while remaining > 0:
        chunk_len = min(remaining, max_block_size)
        chunks.append((current, chunk_len))
        current += chunk_len
        remaining -= chunk_len
    return chunks


def chunk_register_values(
    start: int,
    values: list[int],
    max_block_size: int | None = None,
) -> list[tuple[int, list[int]]]:
    """Split register values into safe-sized chunks with updated addresses."""

    if not values:
        return []

    if max_block_size is None:
        max_block_size = const.MAX_REGS_PER_REQUEST
    max_block_size = min(max_block_size, const.MAX_REGS_PER_REQUEST)
    if max_block_size < 1:
        max_block_size = 1

    chunks: list[tuple[int, list[int]]] = []
    for offset in range(0, len(values), max_block_size):
        chunk = values[offset : offset + max_block_size]
        chunks.append((start + offset, chunk))
    return chunks


def plan_group_reads(
    load_registers_cb: Callable[[], list[RegisterDef]],
    *,
    max_block_size: int | None = None,
) -> list[ReadPlan]:
    """Group registers into contiguous read plans."""
    if max_block_size is None:
        from ..const import MAX_BATCH_REGISTERS

        max_block_size = MAX_BATCH_REGISTERS

    regs_by_fn: dict[int | str, list[int]] = {}
    for reg in load_registers_cb():
        addr_range = range(reg.address, reg.address + reg.length)
        regs_by_fn.setdefault(reg.function, []).extend(addr_range)

    plans: list[ReadPlan] = []
    for fn, addresses in regs_by_fn.items():
        for start, length in group_reads(addresses, max_block_size=max_block_size):
            plans.append(ReadPlan(fn, start, length))
    return plans


def group_registers(
    addresses: Iterable[int],
    *,
    max_block_size: int | None = None,
) -> list[tuple[int, int]]:
    """Return grouped register ranges for provided addresses."""
    return group_reads(addresses, max_block_size=max_block_size)
