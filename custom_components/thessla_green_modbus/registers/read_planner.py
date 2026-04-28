"""Read-planning helpers for register block grouping."""

from __future__ import annotations

from collections.abc import Callable, Iterable

from ..modbus_helpers import group_reads
from .definition import ReadPlan
from .register_def import RegisterDef


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
