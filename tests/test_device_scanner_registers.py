from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from custom_components.thessla_green_modbus.const import CONNECTION_TYPE_RTU
from custom_components.thessla_green_modbus.modbus_exceptions import ConnectionException
from custom_components.thessla_green_modbus.scanner.core import ThesslaGreenDeviceScanner


async def _make_scanner(**kwargs):
    return await ThesslaGreenDeviceScanner.create("192.168.1.1", 502, 1, **kwargs)


def _make_ok_response(registers):
    resp = MagicMock()
    resp.isError.return_value = False
    resp.registers = list(registers)
    return resp


def _make_transport():
    transport = MagicMock()
    transport.close = AsyncMock()
    transport.ensure_connected = AsyncMock()
    transport.read_input_registers = AsyncMock(return_value=_make_ok_response([1]))
    transport.read_holding_registers = AsyncMock(return_value=_make_ok_response([1]))
    transport.is_connected = MagicMock(return_value=True)
    return transport


@pytest.mark.asyncio
async def test_scan_device_rtu_no_serial_port_raises():
    scanner = await _make_scanner(connection_type=CONNECTION_TYPE_RTU)
    scanner.serial_port = ""

    with pytest.raises(ConnectionException, match="Serial port not configured"):
        await scanner.scan_device()


@pytest.mark.asyncio
async def test_scan_device_rtu_creates_transport():
    scanner = await _make_scanner(connection_type=CONNECTION_TYPE_RTU, serial_port="/dev/ttyUSB0")
    mock_client = AsyncMock()
    mock_transport = _make_transport()
    mock_transport.ensure_connected = AsyncMock()
    mock_transport.client = mock_client

    with (
        patch(
            "custom_components.thessla_green_modbus.scanner.core.RtuModbusTransport",
            return_value=mock_transport,
        ) as mock_rtu,
        patch.object(scanner, "_read_input_block", AsyncMock(return_value=[])),
        patch.object(scanner, "_read_holding_block", AsyncMock(return_value=[])),
        patch.object(scanner, "_read_input", AsyncMock(return_value=None)),
        patch.object(scanner, "_read_holding", AsyncMock(return_value=None)),
        patch.object(scanner, "_read_coil", AsyncMock(return_value=None)),
        patch.object(scanner, "_read_discrete", AsyncMock(return_value=None)),
    ):
        result = await scanner.scan_device()

    mock_rtu.assert_called_once()
    assert "available_registers" in result


@pytest.mark.asyncio
async def test_load_registers_with_min_max():
    scanner = await _make_scanner()

    reg = MagicMock()
    reg.name = "test_reg_with_range"
    reg.function = 3
    reg.address = 9999
    reg.min = 0
    reg.max = 100

    with patch(
        "custom_components.thessla_green_modbus.scanner.core.async_get_all_registers",
        AsyncMock(return_value=[reg]),
    ):
        _register_map, register_ranges = await scanner._load_registers()

    assert "test_reg_with_range" in register_ranges
    assert register_ranges["test_reg_with_range"] == (0, 100)


@pytest.mark.asyncio
async def test_load_registers_empty_name():
    scanner = await _make_scanner()

    reg_empty = MagicMock()
    reg_empty.name = ""
    reg_empty.function = 3
    reg_empty.address = 9999
    reg_empty.min = None
    reg_empty.max = None

    reg_valid = MagicMock()
    reg_valid.name = "valid_reg"
    reg_valid.function = 4
    reg_valid.address = 100
    reg_valid.min = None
    reg_valid.max = None

    with patch(
        "custom_components.thessla_green_modbus.scanner.core.async_get_all_registers",
        AsyncMock(return_value=[reg_empty, reg_valid]),
    ):
        register_map, _register_ranges = await scanner._load_registers()

    assert 9999 not in register_map[3]
    assert 100 in register_map[4]
