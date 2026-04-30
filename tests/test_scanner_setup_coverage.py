"""Focused setup/config coverage tests for scanner."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from custom_components.thessla_green_modbus.const import CONNECTION_MODE_TCP, CONNECTION_TYPE_RTU
from custom_components.thessla_green_modbus.modbus_exceptions import ConnectionException


def _make_ok_response(registers):
    resp = MagicMock()
    resp.isError.return_value = False
    resp.registers = list(registers)
    return resp


async def _make_scanner(**kwargs):
    from custom_components.thessla_green_modbus.scanner.core import ThesslaGreenDeviceScanner

    return await ThesslaGreenDeviceScanner.create("192.168.1.1", 502, 1, **kwargs)


def _make_transport(
    *, raises_on_close=None, ensure_side_effect=None, input_response=None, holding_response=None
):
    transport = MagicMock()
    if raises_on_close:
        transport.close = AsyncMock(side_effect=raises_on_close)
    else:
        transport.close = AsyncMock()
    if ensure_side_effect:
        transport.ensure_connected = AsyncMock(side_effect=ensure_side_effect)
    else:
        transport.ensure_connected = AsyncMock()
    transport.read_input_registers = AsyncMock(return_value=input_response or _make_ok_response([1]))
    transport.read_holding_registers = AsyncMock(return_value=holding_response or _make_ok_response([1]))
    transport.is_connected = MagicMock(return_value=True)
    return transport


def test_ensure_pymodbus_import_fails():
    """Lines 119-120: except Exception: return when importlib raises."""
    from custom_components.thessla_green_modbus.scanner.io_runtime import (
        attach_pymodbus_client_module,
    )

    with patch(
        "custom_components.thessla_green_modbus.scanner.io_runtime.importlib.import_module",
        side_effect=ImportError("no pymodbus"),
    ):
        # Must not raise
        attach_pymodbus_client_module()

async def test_async_setup_load_registers_returns_plain_dict():
    """Lines 594-595: _async_setup when _load_registers returns a plain dict (not tuple)."""
    scanner = await _make_scanner()
    plain_dict = {3: {0: "test_reg"}, 4: {}, 1: {}, 2: {}}

    with (
        patch(
            "custom_components.thessla_green_modbus.scanner.setup.async_ensure_register_maps",
            AsyncMock(),
        ),
        patch.object(scanner, "_load_registers", AsyncMock(return_value=plain_dict)),
    ):
        await scanner._async_setup()

    assert scanner._registers == plain_dict
    assert scanner._register_ranges == {}

async def test_verify_connection_tcp_explicit_mode():
    """Lines 795-796: else branch in verify_connection with connection_mode=tcp."""

    scanner = await _make_scanner(connection_mode=CONNECTION_MODE_TCP)
    fake_transport = _make_transport(ensure_side_effect=asyncio.CancelledError())

    with patch.object(scanner, "_build_tcp_transport", return_value=fake_transport):
        with pytest.raises(asyncio.CancelledError):
            await scanner.verify_connection()

    fake_transport.ensure_connected.assert_called_once()

async def test_verify_connection_safe_holding_with_patched_definitions():
    """Lines 766, 824-829: safe_holding populated when REGISTER_DEFINITIONS has holding reg."""
    from custom_components.thessla_green_modbus.scanner.core import (
        REGISTER_DEFINITIONS,
        SAFE_REGISTERS,
    )

    # Find the holding SAFE_REGISTER name
    holding_name = next((name for func, name in SAFE_REGISTERS if func == 3), None)
    if holding_name is None:
        pytest.skip("No holding register in SAFE_REGISTERS")

    # Create mock register definition with a safe address
    mock_reg = MagicMock()
    mock_reg.address = 9998

    scanner = await _make_scanner()
    fake_transport = _make_transport()

    patched_defs = dict(REGISTER_DEFINITIONS)
    patched_defs[holding_name] = mock_reg

    with (
        patch.object(
            scanner,
            "_build_auto_tcp_attempts",
            return_value=[("tcp", fake_transport, scanner.timeout)],
        ),
        patch(
            "custom_components.thessla_green_modbus.scanner.core.REGISTER_DEFINITIONS",
            patched_defs,
        ),
    ):
        await scanner.verify_connection()

    fake_transport.read_holding_registers.assert_called()

async def test_verify_connection_rtu_no_serial_port_raises():
    """Line 771: RTU path in verify_connection raises when serial_port is empty."""
    scanner = await _make_scanner(connection_type=CONNECTION_TYPE_RTU, serial_port="")

    with pytest.raises(ConnectionException, match="Serial port not configured"):
        await scanner.verify_connection()

async def test_verify_connection_rtu_with_serial_port():
    """Lines 770, 772-776: RTU path in verify_connection creates RtuModbusTransport."""
    scanner = await _make_scanner(
        connection_type=CONNECTION_TYPE_RTU,
        serial_port="/dev/ttyUSB0",
    )
    fake_transport = _make_transport(ensure_side_effect=asyncio.CancelledError())

    with (
        patch(
            "custom_components.thessla_green_modbus.scanner.core.RtuModbusTransport",
            return_value=fake_transport,
        ),
        pytest.raises(asyncio.CancelledError),
    ):
        await scanner.verify_connection()
