"""Helpers for normalizing full-scan register phase results."""

from __future__ import annotations

from typing import Any


def apply_word_register_block(
    scanner: Any,
    *,
    function: int,
    register_group: str,
    start: int,
    count: int,
    data: list[int],
    unknown_registers: dict[str, dict[int, Any]],
) -> None:
    """Apply full-scan results for input/holding registers."""
    available = scanner.available_registers[register_group]
    invalid_addresses = scanner.failed_addresses["invalid_values"][register_group]
    register_map = scanner._registers.get(function, {})

    for offset in range(count):
        addr = start + offset
        reg_name = register_map.get(addr)
        if offset >= len(data):
            if reg_name is None:
                base = data[0] if data else start
                unknown_registers[register_group][addr] = int(base) + offset
            continue

        value = data[offset]
        if reg_name and scanner._is_valid_register_value(reg_name, value):
            names = scanner._alias_names(function, addr)
            if names:
                available.update(names)
            else:
                available.add(reg_name)
            continue

        unknown_registers[register_group][addr] = value
        if reg_name:
            invalid_addresses.add(addr)
            scanner._log_invalid_value(reg_name, value)
