"""Tests for scan_register_batch fallback recovery and batch_failures tracking."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from custom_components.thessla_green_modbus.scanner.registers import (
    scan_named_coil,
    scan_named_discrete,
    scan_register_batch,
)


def _make_scanner(available=None) -> MagicMock:
    """Create a minimal scanner mock with required failed_addresses structure."""
    scanner = MagicMock()
    scanner.available_registers = {
        "input_registers": set(),
        "holding_registers": set(),
        "coil_registers": set(),
        "discrete_inputs": set(),
    }
    scanner.failed_addresses = {
        "modbus_exceptions": {
            "input_registers": set(),
            "holding_registers": set(),
            "coil_registers": set(),
            "discrete_inputs": set(),
        },
        "invalid_values": {
            "input_registers": set(),
            "holding_registers": set(),
        },
        "batch_failures": {
            "input_registers": set(),
            "holding_registers": set(),
            "coil_registers": set(),
            "discrete_inputs": set(),
        },
    }
    scanner._is_valid_register_value = MagicMock(return_value=True)
    scanner._log_invalid_value = MagicMock()
    scanner._transport = None
    scanner._client = None

    def group_registers_for_batch_read(addresses, boundaries=None):
        if not addresses:
            return []
        return [(min(addresses), max(addresses) - min(addresses) + 1)]

    scanner._group_registers_for_batch_read = group_registers_for_batch_read
    if available is not None:
        scanner.available_registers.update(available)
    return scanner


@pytest.mark.asyncio
async def test_batch_fail_individual_success_no_modbus_exception():
    """Batch read fails, individual probe succeeds → modbus_exceptions stays empty."""
    scanner = _make_scanner()
    addr_to_names = {10: {"reg_a"}, 11: {"reg_b"}}
    addresses = [10, 11]

    async def read_fn(start, count, *, skip_cache=False):
        if count > 1:
            return None  # batch fails
        return [42]  # individual probe succeeds

    await scan_register_batch(scanner, "holding_registers", addr_to_names, addresses, read_fn)

    assert not scanner.failed_addresses["modbus_exceptions"]["holding_registers"]
    assert scanner.failed_addresses["batch_failures"]["holding_registers"] == {10, 11}
    assert "reg_a" in scanner.available_registers["holding_registers"]
    assert "reg_b" in scanner.available_registers["holding_registers"]


@pytest.mark.asyncio
async def test_batch_fail_individual_fail_adds_to_modbus_exceptions():
    """Batch fails, individual probe also fails → address ends up in modbus_exceptions."""
    scanner = _make_scanner()
    addr_to_names = {10: {"reg_a"}, 11: {"reg_b"}}
    addresses = [10, 11]

    async def read_fn(start, count, *, skip_cache=False):
        return None  # both batch and individual fail

    await scan_register_batch(scanner, "holding_registers", addr_to_names, addresses, read_fn)

    # Both addresses failed batch AND individual probe
    assert scanner.failed_addresses["modbus_exceptions"]["holding_registers"] == {10, 11}
    assert scanner.failed_addresses["batch_failures"]["holding_registers"] == {10, 11}
    assert not scanner.available_registers["holding_registers"]


@pytest.mark.asyncio
async def test_batch_fail_mixed_recovery():
    """Batch fails; addr 10 recovered, addr 11 not → only addr 11 in modbus_exceptions."""
    scanner = _make_scanner()
    addr_to_names = {10: {"reg_a"}, 11: {"reg_b"}}
    addresses = [10, 11]

    async def read_fn(start, count, *, skip_cache=False):
        if count > 1:
            return None  # batch fails
        if start == 10:
            return [99]  # probe for 10 succeeds
        return None  # probe for 11 fails

    await scan_register_batch(scanner, "holding_registers", addr_to_names, addresses, read_fn)

    assert scanner.failed_addresses["modbus_exceptions"]["holding_registers"] == {11}
    assert scanner.failed_addresses["batch_failures"]["holding_registers"] == {10, 11}
    assert "reg_a" in scanner.available_registers["holding_registers"]
    assert "reg_b" not in scanner.available_registers["holding_registers"]


@pytest.mark.asyncio
async def test_batch_fail_unnamed_address_not_in_modbus_exceptions():
    """Unnamed addresses in a failed batch are in batch_failures but NOT modbus_exceptions."""
    scanner = _make_scanner()
    # Only addr 10 has a name; addr 11 is unnamed (e.g., gap in deep scan)
    addr_to_names = {10: {"reg_a"}}
    addresses = [10, 11]

    async def read_fn(start, count, *, skip_cache=False):
        if count > 1:
            return None  # batch fails
        return [42]  # individual probe for addr 10 succeeds

    await scan_register_batch(scanner, "input_registers", addr_to_names, addresses, read_fn)

    # Unnamed addr 11 is in batch_failures but not in modbus_exceptions
    assert 11 not in scanner.failed_addresses["modbus_exceptions"]["input_registers"]
    assert 11 in scanner.failed_addresses["batch_failures"]["input_registers"]
    assert "reg_a" in scanner.available_registers["input_registers"]


@pytest.mark.asyncio
async def test_batch_success_no_batch_failures():
    """Successful batch read → no batch_failures and no modbus_exceptions."""
    scanner = _make_scanner()
    addr_to_names = {10: {"reg_a"}, 11: {"reg_b"}}
    addresses = [10, 11]

    async def read_fn(start, count, *, skip_cache=False):
        return [100, 200]  # batch succeeds

    await scan_register_batch(scanner, "holding_registers", addr_to_names, addresses, read_fn)

    assert not scanner.failed_addresses["modbus_exceptions"]["holding_registers"]
    assert not scanner.failed_addresses["batch_failures"]["holding_registers"]
    assert "reg_a" in scanner.available_registers["holding_registers"]
    assert "reg_b" in scanner.available_registers["holding_registers"]


@pytest.mark.asyncio
async def test_scan_named_coil_batch_fail_individual_success():
    """Coil batch fails, individual probe succeeds → modbus_exceptions empty."""
    scanner = _make_scanner()
    coil_registers = {5: "coil_power", 6: "coil_bypass"}

    call_count = 0

    async def mock_read_coil(client_or_start, start_or_count=None, count=None):
        nonlocal call_count
        call_count += 1
        if start_or_count is not None and count is not None:
            # Called as (client, start, count) — individual probe
            return [True]
        # Called as (start, count) — batch
        return None

    scanner._read_coil = AsyncMock(side_effect=mock_read_coil)
    scanner.scan_uart_settings = False
    scanner._known_missing_registers = {}
    scanner._group_registers_for_batch_read = lambda addrs, **_: (
        [(min(addrs), max(addrs) - min(addrs) + 1)] if addrs else []
    )

    # Patch to avoid HA dependencies
    with patch(
        "custom_components.thessla_green_modbus.scanner.registers.KNOWN_MISSING_REGISTERS",
        {},
    ):
        await scan_named_coil(scanner, coil_registers)

    assert not scanner.failed_addresses["modbus_exceptions"]["coil_registers"]
    assert scanner.failed_addresses["batch_failures"]["coil_registers"]


@pytest.mark.asyncio
async def test_scan_named_discrete_batch_fail_individual_success():
    """Discrete batch fails, individual probe succeeds → modbus_exceptions empty."""
    scanner = _make_scanner()
    discrete_registers = {3: "ds_input_a", 4: "ds_input_b"}

    async def mock_read_discrete(client_or_start, start_or_count=None, count=None):
        if start_or_count is not None and count is not None:
            return [True]
        return None

    scanner._read_discrete = AsyncMock(side_effect=mock_read_discrete)
    scanner._known_missing_registers = {}
    scanner._group_registers_for_batch_read = lambda addrs, **_: (
        [(min(addrs), max(addrs) - min(addrs) + 1)] if addrs else []
    )

    with patch(
        "custom_components.thessla_green_modbus.scanner.registers.KNOWN_MISSING_REGISTERS",
        {},
    ):
        await scan_named_discrete(scanner, discrete_registers)

    assert not scanner.failed_addresses["modbus_exceptions"]["discrete_inputs"]
    assert scanner.failed_addresses["batch_failures"]["discrete_inputs"]
