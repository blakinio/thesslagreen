"""Register selection/grouping helpers used by scanner core."""

from __future__ import annotations

from typing import Any

from ..modbus_helpers import group_reads as _group_reads
from ..scanner_register_maps import (
    COIL_REGISTERS,
    DISCRETE_INPUT_REGISTERS,
    HOLDING_REGISTERS,
    INPUT_REGISTERS,
)


def build_names_by_address(mapping: dict[str, int]) -> dict[int, set[str]]:
    """Create address->name aliases map from name->address mapping."""
    by_address: dict[int, set[str]] = {}
    for name, addr in mapping.items():
        by_address.setdefault(addr, set()).add(name)
    return by_address


def group_registers_for_batch_read(
    scanner: Any,
    addresses: list[int],
    *,
    max_gap: int = 1,
    max_batch: int | None = None,
    boundaries: frozenset[int] | None = None,
) -> list[tuple[int, int]]:
    """Group addresses for efficient reads, isolating known-missing addresses."""
    if not addresses:
        return []

    # ``max_gap`` parameter is currently unused
    _ = max_gap

    if max_batch is None:
        max_batch = scanner.effective_batch

    if scanner.safe_scan:
        return [(addr, 1) for addr in sorted(set(addresses))]

    groups = _group_reads(addresses, max_block_size=max_batch, boundaries=boundaries)
    if not scanner._known_missing_addresses:
        return groups

    result: list[tuple[int, int]] = []
    for start, length in groups:
        current = start
        for addr in range(start, start + length):
            if addr in scanner._known_missing_addresses:
                if addr > current:
                    result.append((current, addr - current))
                result.append((addr, 1))
                current = addr + 1
        if current < start + length:
            result.append((current, start + length - current))
    return result


def select_scan_registers(
    scanner: Any,
) -> tuple[dict[int, str], dict[int, str], dict[int, str], dict[int, str], int, int, int, int]:
    """Select which registers to scan and compute address ranges."""
    input_map = getattr(scanner, "_input_register_map", INPUT_REGISTERS)
    holding_map = getattr(scanner, "_holding_register_map", HOLDING_REGISTERS)
    coil_map = getattr(scanner, "_coil_register_map", COIL_REGISTERS)
    discrete_map = getattr(scanner, "_discrete_input_register_map", DISCRETE_INPUT_REGISTERS)

    input_max = max(scanner._registers.get(4, {}).keys(), default=-1)
    holding_max = max(scanner._registers.get(3, {}).keys(), default=-1)
    coil_max = max(scanner._registers.get(1, {}).keys(), default=-1)
    discrete_max = max(scanner._registers.get(2, {}).keys(), default=-1)
    if scanner.full_register_scan:
        input_registers = scanner._registers.get(4, {}) or {
            addr: name for name, addr in input_map.items()
        }
        holding_registers = scanner._registers.get(3, {}) or {
            addr: name for name, addr in holding_map.items()
        }
        coil_registers = scanner._registers.get(1, {}) or {
            addr: name for name, addr in coil_map.items()
        }
        discrete_registers = scanner._registers.get(2, {}) or {
            addr: name for name, addr in discrete_map.items()
        }
    else:
        global_input = {addr: name for name, addr in input_map.items()}
        global_holding = {addr: name for name, addr in holding_map.items()}
        global_coil = {addr: name for name, addr in coil_map.items()}
        global_discrete = {addr: name for name, addr in discrete_map.items()}

        loaded_input = scanner._registers.get(4, {})
        loaded_holding = scanner._registers.get(3, {})
        loaded_coil = scanner._registers.get(1, {})
        loaded_discrete = scanner._registers.get(2, {})

        input_registers = (
            loaded_input
            if loaded_input and (not global_input or len(loaded_input) <= len(global_input))
            else global_input
        )
        holding_registers = (
            loaded_holding
            if loaded_holding and (not global_holding or len(loaded_holding) <= len(global_holding))
            else global_holding
        )
        coil_registers = (
            loaded_coil
            if loaded_coil and (not global_coil or len(loaded_coil) <= len(global_coil))
            else global_coil
        )
        discrete_registers = (
            loaded_discrete
            if loaded_discrete
            and (not global_discrete or len(loaded_discrete) <= len(global_discrete))
            else global_discrete
        )

    return (
        input_registers,
        holding_registers,
        coil_registers,
        discrete_registers,
        input_max,
        holding_max,
        coil_max,
        discrete_max,
    )
