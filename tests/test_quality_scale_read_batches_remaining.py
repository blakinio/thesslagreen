# mypy: ignore-errors
"""Exercise remaining batch-read fallback, retry, and connection branches."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

import pytest
from custom_components.thessla_green_modbus.core import read_batches
from custom_components.thessla_green_modbus.core.retry import _PermanentModbusError
from pymodbus.exceptions import ConnectionException, ModbusException


def _owner():
    device_client = SimpleNamespace(
        _register_groups={},
        _transport=None,
        client=None,
        effective_batch=4,
        available_registers={"input_registers": {"r1", "r2"}, "holding_registers": {"h1", "h2"}},
        statistics={"total_registers_read": 0},
        slave_id=10,
    )
    owner = SimpleNamespace(
        device_client=device_client,
        _failed_registers=set(),
        _find_register_name=Mock(),
        _process_register_value=Mock(side_effect=lambda _name, value: value),
        _clear_register_failure=Mock(),
        _mark_registers_failed=Mock(),
        _call_modbus=AsyncMock(),
        _read_with_retry=AsyncMock(),
    )
    return owner


@pytest.mark.asyncio
async def test_holding_fallback_uses_default_when_owner_has_no_hook() -> None:
    owner = _owner()
    with patch.object(read_batches, "read_holding_individually", new=AsyncMock()) as fallback:
        await read_batches._read_holding_fallback(owner, "read", 1, ["h1"], {})
    fallback.assert_awaited_once_with(owner, "read", 1, ["h1"], {})


@pytest.mark.asyncio
async def test_individual_input_fallback_marks_none_empty_and_errors() -> None:
    owner = _owner()
    owner._read_with_retry = AsyncMock(
        side_effect=[
            SimpleNamespace(registers=[1]),
            SimpleNamespace(registers=[]),
            _PermanentModbusError("bad"),
            ValueError("bad value"),
        ]
    )
    owner._process_register_value = Mock(return_value=None)
    await read_batches._fallback_individual_input_reads(
        owner, "read", 10, [None, "r1", "r2", "r3", "r4"], {}
    )
    assert owner._mark_registers_failed.call_count == 4


@pytest.mark.asyncio
async def test_input_batch_shortcuts_and_error_classes() -> None:
    owner = _owner()
    owner._failed_registers = {"r1", "r2"}
    await read_batches._read_input_register_batch(
        owner, "read", 10, 2, ["r1", "r2"], {}, owner._failed_registers
    )
    owner._read_with_retry.assert_not_awaited()

    owner._failed_registers = set()
    owner._read_with_retry = AsyncMock(side_effect=_PermanentModbusError("permanent"))
    await read_batches._read_input_register_batch(owner, "read", 10, 2, ["r1", "r2"], {}, set())
    owner._mark_registers_failed.assert_called()

    owner._read_with_retry = AsyncMock(side_effect=ConnectionException("offline"))
    with pytest.raises(ConnectionException):
        await read_batches._read_input_register_batch(owner, "read", 10, 2, ["r1", "r2"], {}, set())

    owner._read_with_retry = AsyncMock(side_effect=ValueError("bad"))
    await read_batches._read_input_register_batch(owner, "read", 10, 2, ["r1", "r2"], {}, set())


@pytest.mark.asyncio
async def test_input_optimized_no_groups_transport_client_and_disconnected_paths() -> None:
    owner = _owner()
    assert await read_batches.read_input_registers_optimized(owner) == {}

    transport = SimpleNamespace(
        is_connected=Mock(return_value=True), read_input_registers=AsyncMock()
    )
    owner.device_client._transport = transport
    owner.device_client._register_groups = {"input_registers": [(10, 1)]}
    owner._find_register_name = Mock(return_value="r1")
    owner._read_with_retry = AsyncMock(return_value=SimpleNamespace(registers=[7]))
    assert await read_batches.read_input_registers_optimized(owner) == {"r1": 7}

    owner.device_client._transport = None
    client = SimpleNamespace(connected=True, read_input_registers=AsyncMock())
    owner.device_client.client = client
    owner._call_modbus = AsyncMock(return_value=SimpleNamespace(registers=[8]))

    async def invoke_read(method, *_args, **_kwargs):
        return await method(10, 10, count=1)

    owner._read_with_retry = AsyncMock(side_effect=invoke_read)
    assert await read_batches.read_input_registers_optimized(owner) == {"r1": 8}

    owner.device_client.client = None
    with pytest.raises(ConnectionException, match="not connected"):
        await read_batches.read_input_registers_optimized(owner)


@pytest.mark.asyncio
async def test_holding_individual_none_empty_permanent_connection_and_general() -> None:
    owner = _owner()
    owner._read_with_retry = AsyncMock(
        side_effect=[
            SimpleNamespace(registers=[1]),
            SimpleNamespace(registers=[]),
            _PermanentModbusError("permanent"),
            ValueError("bad"),
            ConnectionException("offline"),
        ]
    )
    owner._process_register_value = Mock(return_value=None)
    with pytest.raises(ConnectionException):
        await read_batches.read_holding_individually(
            owner, "read", 10, [None, "h1", "h2", "h3", "h4", "h5"], {}
        )
    assert owner._mark_registers_failed.call_count >= 4


@pytest.mark.asyncio
async def test_holding_optimized_no_group_disconnected_partial_and_failures() -> None:
    owner = _owner()
    assert await read_batches.read_holding_registers_optimized(owner) == {}

    owner.device_client._register_groups = {"holding_registers": [(20, 2)]}
    owner._find_register_name = Mock(side_effect=lambda _kind, addr: {20: "h1", 21: "h2"}.get(addr))
    assert await read_batches.read_holding_registers_optimized(owner) == {}

    transport = SimpleNamespace(
        is_connected=Mock(return_value=True), read_holding_registers=AsyncMock()
    )
    owner.device_client._transport = transport
    owner._read_with_retry = AsyncMock(return_value=SimpleNamespace(registers=[3]))
    owner._read_holding_individually = AsyncMock()
    result = await read_batches.read_holding_registers_optimized(owner)
    assert result == {"h1": 3}
    owner._read_holding_individually.assert_awaited_once()

    owner._read_holding_individually.reset_mock()
    owner._read_with_retry = AsyncMock(side_effect=_PermanentModbusError("permanent"))
    assert await read_batches.read_holding_registers_optimized(owner) == {}
    owner._mark_registers_failed.assert_called()

    owner._read_with_retry = AsyncMock(side_effect=ValueError("bad"))
    assert await read_batches.read_holding_registers_optimized(owner) == {}
    owner._read_holding_individually.assert_awaited()

    owner._read_with_retry = AsyncMock(side_effect=ConnectionException("offline"))
    with pytest.raises(ConnectionException):
        await read_batches.read_holding_registers_optimized(owner)


@pytest.mark.asyncio
async def test_execute_read_call_none_falls_back_to_call_modbus() -> None:
    client = SimpleNamespace(slave_id=10, _call_modbus=AsyncMock(return_value="fallback"))
    read = Mock(return_value=None)
    assert await read_batches.execute_read_call(client, read, 1, 2, 3) == "fallback"
    client._call_modbus.assert_awaited_once()


def test_error_response_classifier_non_error_illegal_and_transient() -> None:
    ok = SimpleNamespace(isError=lambda: False)
    read_batches.raise_for_error_response(object(), ok, register_type="input", start_address=1)

    illegal = SimpleNamespace(isError=lambda: True, exception_code=2)
    with pytest.raises(_PermanentModbusError):
        read_batches.raise_for_error_response(
            object(), illegal, register_type="input", start_address=1
        )

    transient = SimpleNamespace(isError=lambda: True, exception_code=4)
    with pytest.raises(ModbusException):
        read_batches.raise_for_error_response(
            object(), transient, register_type="input", start_address=1
        )