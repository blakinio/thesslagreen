"""Device scanner error-path tests."""

import logging
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from custom_components.thessla_green_modbus.const import CONNECTION_MODE_TCP
from custom_components.thessla_green_modbus.modbus_exceptions import (
    ModbusException,
    ModbusIOException,
)
from custom_components.thessla_green_modbus.scanner.core import (
    DeviceCapabilities,
    ThesslaGreenDeviceScanner,
)

pytestmark = pytest.mark.asyncio

async def test_read_coil_retries_on_failure(caplog):
    """Coil reads should retry on failure."""
    scanner = await ThesslaGreenDeviceScanner.create("192.168.1.1", 502, 10)
    mock_client = AsyncMock()

    with (
        patch(
            "custom_components.thessla_green_modbus.scanner.io_core._call_modbus",
            AsyncMock(side_effect=ModbusException("boom")),
        ) as call_mock,
        caplog.at_level(logging.DEBUG),
        patch("asyncio.sleep", AsyncMock()),
    ):
        result = await scanner._read_coil(mock_client, 0, 1)
        assert result is None
        assert call_mock.await_count == scanner.retry


async def test_read_discrete_retries_on_failure(caplog):
    """Discrete input reads should retry on failure."""
    scanner = await ThesslaGreenDeviceScanner.create("192.168.1.1", 502, 10)
    mock_client = AsyncMock()

    with (
        patch(
            "custom_components.thessla_green_modbus.scanner.io_core._call_modbus",
            AsyncMock(side_effect=ModbusException("boom")),
        ) as call_mock,
        caplog.at_level(logging.DEBUG),
        patch("asyncio.sleep", AsyncMock()),
    ):
        result = await scanner._read_discrete(mock_client, 0, 1)
        assert result is None
        assert call_mock.await_count == scanner.retry


async def test_scan_device_connection_failure():
    """Test device scan with connection failure."""
    scanner = await ThesslaGreenDeviceScanner.create("192.168.1.100", 502, 10)

    with patch("pymodbus.client.AsyncModbusTcpClient") as mock_client_class:
        mock_client = AsyncMock()
        mock_client.connect.return_value = False
        mock_client_class.return_value = mock_client

        with pytest.raises(Exception, match="Failed to connect"):
            scanner.connection_mode = CONNECTION_MODE_TCP
            await scanner.scan_device()
        await scanner.close()


async def test_scan_reports_diagnostic_registers_on_error():
    """Diagnostic registers that failed Modbus probing are NOT force-added.

    When all holding register reads fail (return None), the failed addresses
    are recorded in failed_addresses["modbus_exceptions"]["holding_registers"].
    The force-add loop must respect these failures and skip those addresses so
    HA does not create permanently-unavailable entities for unsupported registers.
    """
    scanner = await ThesslaGreenDeviceScanner.create("host", 502, 10)
    scanner._client = object()
    diag_regs = {"alarm": 0, "error": 1, "e_99": 2, "s_2": 3}
    scanner._registers = {
        4: {},
        3: {addr: name for name, addr in diag_regs.items()},
        1: {},
        2: {},
    }
    scanner.available_registers = {
        "input_registers": set(),
        "holding_registers": set(),
        "coil_registers": set(),
        "discrete_inputs": set(),
    }
    with (
        patch(
            "custom_components.thessla_green_modbus.scanner.core.HOLDING_REGISTERS",
            diag_regs,
        ),
        patch.object(scanner, "_read_input", AsyncMock(return_value=[])),
        patch.object(scanner, "_read_holding", AsyncMock(return_value=None)),
        patch.object(scanner, "_read_coil", AsyncMock(return_value=None)),
        patch.object(scanner, "_read_discrete", AsyncMock(return_value=None)),
        patch.object(scanner, "_analyze_capabilities", return_value=DeviceCapabilities()),
    ):
        result = await scanner.scan()

    # All four addresses (0-3) failed → none should be force-added
    assert result["available_registers"]["holding_registers"] == set()


@pytest.mark.parametrize("async_close", [True, False])
async def test_close_terminates_client(async_close):
    """Ensure close() handles both async and sync client close methods."""
    scanner = await ThesslaGreenDeviceScanner.create("192.168.1.100", 502, 10)
    mock_client = AsyncMock() if async_close else MagicMock()
    scanner._client = mock_client

    await scanner.close()

    if async_close:
        mock_client.close.assert_called_once()
        mock_client.close.assert_awaited_once()
    else:
        mock_client.close.assert_called_once()

    assert scanner._client is None


async def test_failed_addresses_recorded_on_exception():
    """Addresses are recorded when a Modbus read raises an exception."""
    scanner = await ThesslaGreenDeviceScanner.create("host", 502)
    scanner._client = AsyncMock()

    async def fake_call(func, slave_id, address, *, count=None):
        if address == 0 and count == 1:
            raise ModbusIOException("boom")
        resp = MagicMock()
        resp.isError.return_value = False
        if func.__name__ in ("read_input_registers", "read_holding_registers"):
            resp.registers = [0] * (count or 1)
        else:
            resp.bits = [0] * (count or 1)
        return resp

    with (
        patch.dict(
            "custom_components.thessla_green_modbus.scanner.core.INPUT_REGISTERS",
            {"version_major": 0},
        ),
        patch.dict(
            "custom_components.thessla_green_modbus.scanner.core.HOLDING_REGISTERS",
            {},
        ),
        patch.dict(
            "custom_components.thessla_green_modbus.scanner.core.COIL_REGISTERS",
            {},
        ),
        patch.dict(
            "custom_components.thessla_green_modbus.scanner.core.DISCRETE_INPUT_REGISTERS",
            {},
        ),
        patch(
            "custom_components.thessla_green_modbus.scanner.io_core._call_modbus",
            AsyncMock(side_effect=fake_call),
        ),
        patch("asyncio.sleep", AsyncMock()),
    ):
        result = await scanner.scan()

    failed = result["failed_addresses"]["modbus_exceptions"]
    assert failed


