from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from custom_components.thessla_green_modbus.coordinator import ThesslaGreenModbusCoordinator
from custom_components.thessla_green_modbus.modbus_exceptions import (
    ConnectionException,
    ModbusException,
    ModbusIOException,
)


def _make_coordinator(**kwargs) -> ThesslaGreenModbusCoordinator:
    hass = MagicMock()
    hass.async_add_executor_job = None
    return ThesslaGreenModbusCoordinator.from_params(
        hass=hass,
        host="192.168.1.1",
        port=502,
        slave_id=1,
        name="test",
        scan_interval=30,
        timeout=3,
        retry=2,
        **kwargs,
    )


async def test_read_coils_transport_raises_when_no_client():
    c = _make_coordinator()
    c.client = None
    c._transport = None
    with pytest.raises(ConnectionException):
        await c._read_coils_transport(1, 0, count=1)


async def test_read_discrete_inputs_transport_raises_when_no_client():
    c = _make_coordinator()
    c.client = None
    c._transport = None
    with pytest.raises(ConnectionException):
        await c._read_discrete_inputs_transport(1, 0, count=1)


async def test_read_with_retry_awaitable_returning_none_raises():
    c = _make_coordinator()
    c.retry = 1

    async def read_method(slave_id, addr, *, count, attempt):
        return None

    with pytest.raises(ModbusException):
        await c._read_with_retry(read_method, 0, 1, register_type="input_registers")


async def test_read_with_retry_transient_error_raises_modbus_io():
    c = _make_coordinator()
    c.retry = 1
    resp = MagicMock()
    resp.isError.return_value = True
    resp.exception_code = 3

    async def read_method(slave_id, addr, *, count, attempt):
        return resp

    with pytest.raises(ModbusIOException):
        await c._read_with_retry(read_method, 0, 1, register_type="input_registers")


async def test_async_write_register_multi_reg_offset_too_large():
    c = _make_coordinator()
    c._ensure_connection = AsyncMock()
    t = MagicMock()
    t.is_connected.return_value = True
    c._transport = t
    d = MagicMock()
    d.length = 2
    d.function = 3
    d.address = 100
    d.encode.return_value = [1, 2, 3]
    with patch(
        "custom_components.thessla_green_modbus.coordinator.coordinator.get_register_definition",
        return_value=d,
    ):
        assert await c.async_write_register("some_reg", [1, 2, 3], offset=1) is False


async def test_async_write_register_response_error_returns_false():
    c = _make_coordinator()
    c.retry = 1
    c._ensure_connection = AsyncMock()
    e = MagicMock()
    e.isError.return_value = True
    t = MagicMock()
    t.is_connected.return_value = True
    t.write_register = AsyncMock(return_value=e)
    c._transport = t
    assert await c.async_write_register("mode", 1) is False


async def test_async_write_registers_empty_values():
    assert await _make_coordinator().async_write_registers(100, []) is False


async def test_async_write_registers_too_many_for_single_request():
    from custom_components.thessla_green_modbus.const import MAX_REGS_PER_REQUEST

    assert (
        await _make_coordinator().async_write_registers(
            100, list(range(MAX_REGS_PER_REQUEST + 1)), require_single_request=True
        )
        is False
    )


async def test_async_write_register_non_writable_function():
    c = _make_coordinator()
    c._ensure_connection = AsyncMock()
    t = MagicMock()
    t.is_connected.return_value = True
    c._transport = t
    d = MagicMock()
    d.length = 1
    d.function = 2
    d.address = 100
    d.encode.return_value = 1
    with patch(
        "custom_components.thessla_green_modbus.coordinator.coordinator.get_register_definition",
        return_value=d,
    ):
        assert await c.async_write_register("some_reg", 1) is False


async def test_call_modbus_no_client_raises():
    c = _make_coordinator()
    c._transport = None
    c.client = None

    async def dummy(*args, **kwargs):
        return None

    with pytest.raises(ConnectionException):
        await c._call_modbus(dummy, 100, count=1)


async def test_read_with_retry_response_none_via_call_modbus():
    c = _make_coordinator()
    c.retry = 1
    c._call_modbus = AsyncMock(return_value=None)
    t = MagicMock()
    t.is_connected.return_value = True
    c._transport = t

    def read_method(slave_id, addr, *, count, attempt):
        return None

    with pytest.raises(ModbusException):
        await c._read_with_retry(read_method, 0, 1, register_type="input_registers")


async def test_async_write_register_multi_reg_non_int_values():
    c = _make_coordinator()
    c._ensure_connection = AsyncMock()
    d = MagicMock()
    d.length = 3
    d.function = 3
    d.address = 100
    t = MagicMock()
    t.is_connected.return_value = True
    c._transport = t
    with patch(
        "custom_components.thessla_green_modbus.coordinator.coordinator.get_register_definition",
        return_value=d,
    ):
        assert await c.async_write_register("some_reg", ["bad", "x", "y"], offset=0) is False


async def test_async_write_register_offset_exceeds_length():
    c = _make_coordinator()
    c._ensure_connection = AsyncMock()
    d = MagicMock()
    d.length = 2
    d.function = 3
    d.address = 100
    d.encode.return_value = [1, 2]
    t = MagicMock()
    t.is_connected.return_value = True
    c._transport = t
    with patch(
        "custom_components.thessla_green_modbus.coordinator.coordinator.get_register_definition",
        return_value=d,
    ):
        assert await c.async_write_register("some_reg", 1, offset=2) is False


async def test_async_write_registers_single_request_error_response():
    c = _make_coordinator()
    c._ensure_connection = AsyncMock()
    t = MagicMock()
    t.is_connected.return_value = True
    e = MagicMock()
    e.isError.return_value = True
    t.write_registers = AsyncMock(return_value=e)
    c._transport = t
    c.retry = 1
    assert await c.async_write_registers(100, [1, 2], require_single_request=True) is False
