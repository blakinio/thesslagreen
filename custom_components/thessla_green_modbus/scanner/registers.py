"""Register-oriented scanner helpers."""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING

from ..const import HOLDING_BATCH_BOUNDARIES, KNOWN_MISSING_REGISTERS
from ..scanner_helpers import UART_OPTIONAL_REGS
from ..scanner_register_maps import MULTI_REGISTER_SIZES

if TYPE_CHECKING:
    from .core import ThesslaGreenDeviceScanner

_LOGGER = logging.getLogger(__name__)


async def scan_register_batch(
    scanner: ThesslaGreenDeviceScanner,
    reg_type: str,
    addr_to_names: dict[int, set[str]],
    addresses: list[int],
    read_fn: Callable[..., Awaitable[list[int] | None]],
    *,
    boundaries: frozenset[int] | None = None,
) -> None:
    """Read a batch of registers of one FC type, with per-address fallback."""
    for start, count in scanner._group_registers_for_batch_read(addresses, boundaries=boundaries):
        try:
            data = await read_fn(start, count)
        except TypeError:
            data = None

        if data is None:
            scanner.failed_addresses["modbus_exceptions"][reg_type].update(range(start, start + count))
            _LOGGER.debug(
                "%s batch read %d-%d failed; probing individually",
                reg_type,
                start,
                start + count - 1,
            )
            for addr in range(start, start + count):
                reg_names = addr_to_names.get(addr)
                if not reg_names:
                    continue
                try:
                    probe = await read_fn(addr, 1, skip_cache=True)
                except TypeError:
                    probe = None
                if not probe:
                    _LOGGER.warning("Failed to read %s register %d", reg_type, addr)
                    continue
                value = probe[0]
                if any(scanner._is_valid_register_value(n, value) for n in reg_names):
                    scanner.available_registers[reg_type].update(reg_names)
                else:
                    scanner.failed_addresses["invalid_values"][reg_type].add(addr)
                    scanner._log_invalid_value(sorted(reg_names)[0], value)
            continue

        for offset, value in enumerate(data):
            addr = start + offset
            if reg_names := addr_to_names.get(addr):
                if any(scanner._is_valid_register_value(n, value) for n in reg_names):
                    scanner.available_registers[reg_type].update(reg_names)
                else:
                    scanner.failed_addresses["invalid_values"][reg_type].add(addr)
                    scanner._log_invalid_value(sorted(reg_names)[0], value)


async def scan_named_input(scanner: ThesslaGreenDeviceScanner, input_registers: dict[int, str]) -> None:
    """Scan FC04 input registers in batches."""
    addr_to_names: dict[int, set[str]] = {}
    addresses: list[int] = []
    for addr, name in input_registers.items():
        if name in KNOWN_MISSING_REGISTERS.get("input_registers", set()):
            continue
        addr_to_names.setdefault(addr, set()).add(name)
        addresses.append(addr)

    async def _read(start: int, count: int, *, skip_cache: bool = False) -> list[int] | None:
        try:
            return (
                await scanner._read_input(scanner._client, start, count, skip_cache=skip_cache)
                if scanner._client is not None
                else await scanner._read_input(start, count, skip_cache=skip_cache)
            )
        except TypeError:
            return await scanner._read_input(start, count, skip_cache=skip_cache)

    await scan_register_batch(scanner, "input_registers", addr_to_names, addresses, _read)


async def scan_named_holding(
    scanner: ThesslaGreenDeviceScanner, holding_registers: dict[int, str]
) -> None:
    """Scan FC03 holding registers in batches, handling multi-word registers."""
    holding_info: dict[int, tuple[set[str], int]] = {}
    holding_addresses: list[int] = []
    for addr, name in holding_registers.items():
        if not scanner.scan_uart_settings and addr in UART_OPTIONAL_REGS:
            continue
        if name in KNOWN_MISSING_REGISTERS.get("holding_registers", set()):
            continue
        size = MULTI_REGISTER_SIZES.get(name, 1)
        if addr in holding_info:
            names, _ = holding_info[addr]
            names.add(name)
        else:
            holding_info[addr] = ({name}, size)
        holding_addresses.extend(range(addr, addr + size))

    addr_to_names = {addr: names for addr, (names, _) in holding_info.items()}

    async def _read(start: int, count: int, *, skip_cache: bool = False) -> list[int] | None:
        try:
            return (
                await scanner._read_holding(scanner._client, start, count, skip_cache=skip_cache)
                if scanner._client is not None
                else await scanner._read_holding(start, count, skip_cache=skip_cache)
            )
        except TypeError:
            return await scanner._read_holding(start, count, skip_cache=skip_cache)

    await scan_register_batch(
        scanner,
        "holding_registers",
        addr_to_names,
        holding_addresses,
        _read,
        boundaries=HOLDING_BATCH_BOUNDARIES,
    )

    failed_addrs = scanner.failed_addresses["modbus_exceptions"]["holding_registers"]
    for addr, name in holding_registers.items():
        if (name.startswith(("e_", "s_")) or name in {"alarm", "error"}) and addr not in failed_addrs:
            scanner.available_registers["holding_registers"].add(name)


async def scan_named_coil(scanner: ThesslaGreenDeviceScanner, coil_registers: dict[int, str]) -> None:
    """Scan FC01 coil registers in batches."""
    addr_to_names: dict[int, set[str]] = {}
    addresses: list[int] = []
    for addr, name in coil_registers.items():
        if name in KNOWN_MISSING_REGISTERS.get("coil_registers", set()):
            continue
        addr_to_names.setdefault(addr, set()).add(name)
        addresses.append(addr)

    for start, count in scanner._group_registers_for_batch_read(addresses):
        coil_data = (
            await scanner._read_coil(scanner._client, start, count)
            if scanner._client is not None
            else await scanner._read_coil(start, count)
        )
        if coil_data is None:
            scanner.failed_addresses["modbus_exceptions"]["coil_registers"].update(
                range(start, start + count)
            )
            for addr in range(start, start + count):
                if addr not in addr_to_names:
                    continue
                probe = (
                    await scanner._read_coil(scanner._client, addr, 1)
                    if scanner._client is not None
                    else await scanner._read_coil(None, addr, 1)
                )
                if probe and probe[0] is not None:
                    scanner.available_registers["coil_registers"].update(addr_to_names[addr])
            continue
        for offset, value in enumerate(coil_data):
            addr = start + offset
            if addr in addr_to_names and value is not None:
                scanner.available_registers["coil_registers"].update(addr_to_names[addr])


async def scan_named_discrete(
    scanner: ThesslaGreenDeviceScanner, discrete_registers: dict[int, str]
) -> None:
    """Scan FC02 discrete input registers in batches."""
    addr_to_names: dict[int, set[str]] = {}
    addresses: list[int] = []
    for addr, name in discrete_registers.items():
        if name in KNOWN_MISSING_REGISTERS.get("discrete_inputs", set()):
            continue
        addr_to_names.setdefault(addr, set()).add(name)
        addresses.append(addr)

    for start, count in scanner._group_registers_for_batch_read(addresses):
        discrete_data = (
            await scanner._read_discrete(scanner._client, start, count)
            if scanner._client is not None
            else await scanner._read_discrete(start, count)
        )
        if discrete_data is None:
            scanner.failed_addresses["modbus_exceptions"]["discrete_inputs"].update(
                range(start, start + count)
            )
            for addr in range(start, start + count):
                if addr not in addr_to_names:
                    continue
                probe = (
                    await scanner._read_discrete(scanner._client, addr, 1)
                    if scanner._client is not None
                    else await scanner._read_discrete(None, addr, 1)
                )
                if probe and probe[0] is not None:
                    scanner.available_registers["discrete_inputs"].update(addr_to_names[addr])
            continue
        for offset, value in enumerate(discrete_data):
            addr = start + offset
            if addr in addr_to_names and value is not None:
                scanner.available_registers["discrete_inputs"].update(addr_to_names[addr])


async def run_named_scan(
    scanner: ThesslaGreenDeviceScanner,
    input_registers: dict[int, str],
    holding_registers: dict[int, str],
    coil_registers: dict[int, str],
    discrete_registers: dict[int, str],
) -> None:
    """Scan only named/known registers (normal scan mode)."""
    await scan_named_input(scanner, input_registers)
    await scan_named_holding(scanner, holding_registers)
    await scan_named_coil(scanner, coil_registers)
    await scan_named_discrete(scanner, discrete_registers)


def compute_scan_blocks(
    scanner: ThesslaGreenDeviceScanner,
    input_registers: dict[int, str],
    holding_registers: dict[int, str],
    coil_registers: dict[int, str],
    discrete_registers: dict[int, str],
    input_max: int,
    holding_max: int,
    coil_max: int,
    discrete_max: int,
) -> dict[str, tuple[int | None, int | None]]:
    """Build scan_blocks dict describing the address range that was scanned."""
    _ = scanner
    if scanner.full_register_scan:
        return {
            "input_registers": (0 if input_max >= 0 else None, input_max if input_max >= 0 else None),
            "holding_registers": (
                0 if holding_max >= 0 else None,
                holding_max if holding_max >= 0 else None,
            ),
            "coil_registers": (0 if coil_max >= 0 else None, coil_max if coil_max >= 0 else None),
            "discrete_inputs": (
                0 if discrete_max >= 0 else None,
                discrete_max if discrete_max >= 0 else None,
            ),
        }
    return {
        "input_registers": (
            (min(input_registers.keys()), max(input_registers.keys())) if input_registers else (None, None)
        ),
        "holding_registers": (
            (min(holding_registers.keys()), max(holding_registers.keys()))
            if holding_registers
            else (None, None)
        ),
        "coil_registers": (
            (min(coil_registers.keys()), max(coil_registers.keys())) if coil_registers else (None, None)
        ),
        "discrete_inputs": (
            (min(discrete_registers.keys()), max(discrete_registers.keys()))
            if discrete_registers
            else (None, None)
        ),
    }


def collect_missing_registers(
    scanner: ThesslaGreenDeviceScanner,
    input_registers: dict[int, str],
    holding_registers: dict[int, str],
    coil_registers: dict[int, str],
    discrete_registers: dict[int, str],
) -> dict[str, dict[str, int]]:
    """Return registers that were expected but not found during scan."""
    register_maps = {
        "input_registers": {name: addr for addr, name in input_registers.items()},
        "holding_registers": {name: addr for addr, name in holding_registers.items()},
        "coil_registers": {name: addr for addr, name in coil_registers.items()},
        "discrete_inputs": {name: addr for addr, name in discrete_registers.items()},
    }
    missing_registers: dict[str, dict[str, int]] = {}
    for reg_type, mapping in register_maps.items():
        missing: dict[str, int] = {}
        for name, addr in mapping.items():
            if name in KNOWN_MISSING_REGISTERS.get(reg_type, set()):
                continue
            if name not in scanner.available_registers[reg_type]:
                missing[name] = addr
        if missing:
            missing_registers[reg_type] = missing
    return missing_registers


__all__ = [
    "collect_missing_registers",
    "compute_scan_blocks",
    "run_named_scan",
    "scan_named_coil",
    "scan_named_discrete",
    "scan_named_holding",
    "scan_named_input",
    "scan_register_batch",
]
