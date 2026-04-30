from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from custom_components.thessla_green_modbus.modbus_exceptions import (
    ConnectionException,
    ModbusIOException,
)
from custom_components.thessla_green_modbus.scanner.core import ThesslaGreenDeviceScanner


async def _make_scanner(**kwargs):
    return await ThesslaGreenDeviceScanner.create("192.168.1.1", 502, 1, **kwargs)


def _make_ok_response(registers):
    resp = MagicMock()
    resp.isError.return_value = False
    resp.registers = list(registers)
    return resp


def _make_transport(*, input_response=None, holding_response=None):
    transport = MagicMock()
    transport.close = AsyncMock()
    transport.ensure_connected = AsyncMock()
    transport.read_input_registers = AsyncMock(return_value=input_response or _make_ok_response([1]))
    transport.read_holding_registers = AsyncMock(
        return_value=holding_response or _make_ok_response([1])
    )
    transport.is_connected = MagicMock(return_value=True)
    return transport


@pytest.mark.asyncio
async def test_scan_device_auto_detect_all_fail():
    scanner = await _make_scanner(connection_mode="auto")
    failing_transport = MagicMock()
    failing_transport.ensure_connected = AsyncMock(side_effect=ConnectionException("no"))
    failing_transport.close = AsyncMock()

    with (
        patch.object(
            scanner,
            "_build_auto_tcp_attempts",
            return_value=[("tcp", failing_transport, 1.0)],
        ),
        pytest.raises(ConnectionException, match="Auto-detect Modbus transport failed"),
    ):
        await scanner.scan_device()


@pytest.mark.asyncio
async def test_scan_device_auto_detect_probe_timeout():
    scanner = await _make_scanner(connection_mode="auto")
    t1 = MagicMock()
    t1.ensure_connected = AsyncMock()
    t1.read_input_registers = AsyncMock(side_effect=TimeoutError("probe timeout"))
    t1.close = AsyncMock()

    t2 = _make_transport()
    t2.client = AsyncMock()

    with (
        patch.object(
            scanner,
            "_build_auto_tcp_attempts",
            return_value=[("tcp", t1, 1.0), ("tcp_rtu", t2, 1.0)],
        ),
        patch.object(scanner, "_read_input_block", AsyncMock(return_value=[])),
        patch.object(scanner, "_read_holding_block", AsyncMock(return_value=[])),
        patch.object(scanner, "_read_input", AsyncMock(return_value=None)),
        patch.object(scanner, "_read_holding", AsyncMock(return_value=None)),
        patch.object(scanner, "_read_coil", AsyncMock(return_value=None)),
        patch.object(scanner, "_read_discrete", AsyncMock(return_value=None)),
    ):
        result = await scanner.scan_device()

    assert "available_registers" in result


@pytest.mark.asyncio
async def test_scan_device_auto_detect_probe_modbus_io_cancelled():
    scanner = await _make_scanner(connection_mode="auto")
    t1 = MagicMock()
    t1.ensure_connected = AsyncMock()
    t1.read_input_registers = AsyncMock(
        side_effect=ModbusIOException("Request cancelled outside pymodbus")
    )
    t1.close = AsyncMock()

    t2 = _make_transport()
    t2.client = AsyncMock()

    with (
        patch.object(
            scanner,
            "_build_auto_tcp_attempts",
            return_value=[("tcp", t1, 1.0), ("tcp_rtu", t2, 1.0)],
        ),
        patch.object(scanner, "_read_input_block", AsyncMock(return_value=[])),
        patch.object(scanner, "_read_holding_block", AsyncMock(return_value=[])),
        patch.object(scanner, "_read_input", AsyncMock(return_value=None)),
        patch.object(scanner, "_read_holding", AsyncMock(return_value=None)),
        patch.object(scanner, "_read_coil", AsyncMock(return_value=None)),
        patch.object(scanner, "_read_discrete", AsyncMock(return_value=None)),
    ):
        result = await scanner.scan_device()

    assert "available_registers" in result
