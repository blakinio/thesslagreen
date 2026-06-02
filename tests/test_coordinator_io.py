from __future__ import annotations

import logging
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from custom_components.thessla_green_modbus.coordinator import ThesslaGreenModbusCoordinator
from custom_components.thessla_green_modbus.core.retry import _PermanentModbusError
from pymodbus.exceptions import ConnectionException, ModbusIOException


@pytest.fixture
def coordinator() -> ThesslaGreenModbusCoordinator:
    coord = ThesslaGreenModbusCoordinator.from_params(
        hass=MagicMock(),
        host="localhost",
        port=502,
        slave_id=1,
        name="test",
        scan_interval=30,
        timeout=5,
        retry=1,
    )
    dc = coord.device_client
    dc.available_registers = {
        "holding_registers": {"mode", "air_flow_rate_manual"},
        "input_registers": set(),
        "coil_registers": set(),
        "discrete_inputs": set(),
    }
    dc._register_groups = {"holding_registers": [(100, 2)]}
    dc._failed_registers = set()
    dc.effective_batch = 10
    mapping = {100: "mode", 101: "air_flow_rate_manual"}
    dc._find_register_name = lambda rt, addr: mapping.get(addr)
    dc._process_register_value = lambda _name, value: value
    dc._clear_register_failure = MagicMock()
    dc._mark_registers_failed = MagicMock()
    return coord


@pytest.mark.asyncio
async def test_holding_happy_path_batch_full(coordinator: ThesslaGreenModbusCoordinator) -> None:
    dc = coordinator.device_client
    dc._transport = SimpleNamespace(
        is_connected=lambda: True,
        read_holding_registers=AsyncMock(),
    )
    dc.client = None
    dc._read_with_retry = AsyncMock(return_value=SimpleNamespace(registers=[11, 22]))

    data = await dc._read_holding_registers_optimized()

    assert data == {"mode": 11, "air_flow_rate_manual": 22}
    dc._mark_registers_failed.assert_not_called()


@pytest.mark.asyncio
async def test_holding_partial_read_falls_back_for_tail(
    coordinator: ThesslaGreenModbusCoordinator,
) -> None:
    """Partial batch response: tail registers are retried individually, not marked failed."""
    dc = coordinator.device_client
    dc._transport = SimpleNamespace(
        is_connected=lambda: True,
        read_holding_registers=AsyncMock(),
    )
    dc.client = None

    # Batch returns only 1 of 2 registers; individual read returns 99 for the tail.
    async def _fake_read(_read_method, address, count, **_kwargs):
        if count > 1:
            return SimpleNamespace(registers=[11])
        return SimpleNamespace(registers=[99])

    dc._read_with_retry = AsyncMock(side_effect=_fake_read)

    data = await dc._read_holding_registers_optimized()

    assert data == {"mode": 11, "air_flow_rate_manual": 99}
    dc._mark_registers_failed.assert_not_called()


@pytest.mark.asyncio
async def test_holding_empty_read_falls_back_to_individual(
    coordinator: ThesslaGreenModbusCoordinator,
) -> None:
    dc = coordinator.device_client
    dc._transport = SimpleNamespace(
        is_connected=lambda: True,
        read_holding_registers=AsyncMock(),
    )
    dc.client = None
    dc._read_with_retry = AsyncMock(return_value=SimpleNamespace(registers=[]))
    dc._read_holding_individually = AsyncMock()

    await dc._read_holding_registers_optimized()

    dc._read_holding_individually.assert_awaited_once()


@pytest.mark.asyncio
async def test_holding_modbus_io_exception_falls_back_to_individual(
    coordinator: ThesslaGreenModbusCoordinator,
) -> None:
    dc = coordinator.device_client
    dc._transport = SimpleNamespace(
        is_connected=lambda: True,
        read_holding_registers=AsyncMock(),
    )
    dc.client = None
    dc._read_with_retry = AsyncMock(side_effect=ModbusIOException("broken frame"))
    dc._read_holding_individually = AsyncMock()

    await dc._read_holding_registers_optimized()

    dc._read_holding_individually.assert_awaited_once()


@pytest.mark.asyncio
async def test_holding_permanent_error_marks_failed_without_fallback(
    coordinator: ThesslaGreenModbusCoordinator,
) -> None:
    dc = coordinator.device_client
    dc._transport = SimpleNamespace(
        is_connected=lambda: True,
        read_holding_registers=AsyncMock(),
    )
    dc.client = None
    dc._read_with_retry = AsyncMock(side_effect=_PermanentModbusError("illegal"))
    dc._read_holding_individually = AsyncMock()

    await dc._read_holding_registers_optimized()

    dc._mark_registers_failed.assert_called_once_with(["mode", "air_flow_rate_manual"])
    dc._read_holding_individually.assert_not_called()


@pytest.mark.asyncio
async def test_holding_uses_transport_method_when_available(
    coordinator: ThesslaGreenModbusCoordinator,
) -> None:
    dc = coordinator.device_client
    transport_read = AsyncMock()
    dc._transport = SimpleNamespace(
        is_connected=lambda: True, read_holding_registers=transport_read
    )
    dc.client = None
    seen = {}

    async def _fake_read_with_retry(read_method, *_args, **_kwargs):
        seen["method"] = read_method
        return SimpleNamespace(registers=[1, 2])

    dc._read_with_retry = _fake_read_with_retry

    await dc._read_holding_registers_optimized()

    assert seen["method"] is transport_read


@pytest.mark.asyncio
async def test_holding_falls_back_to_client_read_method(
    coordinator: ThesslaGreenModbusCoordinator,
) -> None:
    dc = coordinator.device_client
    dc._transport = None
    client_read = AsyncMock(return_value=SimpleNamespace(registers=[7, 8]))
    dc.client = SimpleNamespace(connected=True, read_holding_registers=client_read)
    dc._call_modbus = AsyncMock(return_value=SimpleNamespace(registers=[7, 8]))

    async def _fake_read_with_retry(read_method, address, count, **_kwargs):
        return await read_method(dc.slave_id, address, count=count, attempt=1)

    dc._read_with_retry = _fake_read_with_retry

    data = await dc._read_holding_registers_optimized()

    assert data == {"mode": 7, "air_flow_rate_manual": 8}
    dc._call_modbus.assert_awaited_once_with(
        client_read,
        100,
        count=2,
        attempt=1,
    )


@pytest.mark.asyncio
async def test_holding_connection_exception_propagates_not_swallowed(
    coordinator: ThesslaGreenModbusCoordinator,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """ConnectionException from a batch read propagates to abort the update cycle.

    When the Modbus transport is globally disconnected, re-raising rather than
    swallowing prevents WARNING spam across every register chunk.  The single
    ERROR is emitted by the coordinator update-cycle error handler instead.
    """
    dc = coordinator.device_client
    dc._transport = SimpleNamespace(
        is_connected=lambda: True,
        read_holding_registers=AsyncMock(),
    )
    dc.client = None
    dc._read_with_retry = AsyncMock(
        side_effect=ConnectionException("Modbus client is not connected")
    )
    dc._read_holding_individually = AsyncMock()

    with caplog.at_level(logging.WARNING), pytest.raises(ConnectionException):
        await dc._read_holding_registers_optimized()

    dc._read_holding_individually.assert_not_called()
    warning_texts = [r for r in caplog.records if r.levelno >= logging.WARNING]
    assert len(warning_texts) == 0, (
        f"Expected no WARNING logs for connection error, got: {[r.message for r in warning_texts]}"
    )


@pytest.mark.asyncio
async def test_input_connection_exception_propagates_not_swallowed(
    coordinator: ThesslaGreenModbusCoordinator,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """ConnectionException in input register batch propagates to abort update cycle."""
    dc = coordinator.device_client
    dc._transport = SimpleNamespace(
        is_connected=lambda: True,
        read_input_registers=AsyncMock(),
    )
    dc.client = None
    dc.available_registers = {
        **dc.available_registers,
        "input_registers": {"outside_temperature"},
    }
    dc._register_groups = {"input_registers": [(0, 1)]}
    dc._find_register_name = lambda rt, addr: "outside_temperature" if addr == 0 else None
    dc._read_with_retry = AsyncMock(
        side_effect=ConnectionException("Modbus client is not connected")
    )

    with caplog.at_level(logging.WARNING), pytest.raises(ConnectionException):
        await dc._read_input_registers_optimized()

    warning_texts = [r for r in caplog.records if r.levelno >= logging.WARNING]
    assert len(warning_texts) == 0, (
        f"Expected no WARNING logs for connection error, got: {[r.message for r in warning_texts]}"
    )
