"""Setup and initialization tests for device scanner."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from custom_components.thessla_green_modbus.modbus_exceptions import ConnectionException
from custom_components.thessla_green_modbus.scanner.core import ThesslaGreenDeviceScanner

pytestmark = pytest.mark.asyncio


async def test_scanner_core_initialization():
    """Test device scanner initialization."""
    scanner = await ThesslaGreenDeviceScanner.create("192.168.3.17", 8899, 10)

    assert hasattr(scanner, "_read_coil")
    assert hasattr(scanner, "_read_holding")
    assert hasattr(scanner, "_read_discrete")

    assert scanner.host == "192.168.3.17"
    assert scanner.port == 8899
    assert scanner.slave_id == 10
    assert scanner.retry == 3
    assert scanner.backoff == 0


async def test_verify_connection_close_non_awaitable_on_failure():
    """Verify close() handles non-awaitable result on connection failure."""
    scanner = await ThesslaGreenDeviceScanner.create("192.168.3.17", 8899, 10)
    fake_transport = MagicMock()
    fake_transport.ensure_connected = AsyncMock(side_effect=ConnectionException("fail"))
    fake_transport.read_input_registers = AsyncMock()
    fake_transport.read_holding_registers = AsyncMock()
    fake_transport.close = MagicMock(return_value=None)

    with patch.object(scanner, "_build_tcp_transport", return_value=fake_transport):
        with pytest.raises(ConnectionException):
            await scanner.verify_connection()

    fake_transport.close.assert_called_once()


async def test_verify_connection_close_non_awaitable_on_success():
    """Verify close() handles non-awaitable result on success."""
    scanner = await ThesslaGreenDeviceScanner.create("192.168.3.17", 8899, 10)
    fake_transport = MagicMock()
    fake_transport.ensure_connected = AsyncMock(return_value=True)
    fake_transport.read_input_registers = AsyncMock()
    fake_transport.read_holding_registers = AsyncMock()
    fake_transport.close = MagicMock(return_value=None)

    with patch.object(scanner, "_build_tcp_transport", return_value=fake_transport):
        await scanner.verify_connection()

    fake_transport.close.assert_called_once()


async def test_create_binds_read_helpers():
    """Scanner.create binds read helper methods to the instance."""
    scanner = await ThesslaGreenDeviceScanner.create("192.168.3.17", 8899, 10)
    assert hasattr(scanner, "_read_holding")
    assert hasattr(scanner, "_read_coil")
    assert hasattr(scanner, "_read_discrete")


async def test_scanner_has_read_coil_method():
    """Ensure scanner exposes coil reading helper."""
    scanner = await ThesslaGreenDeviceScanner.create("192.168.3.17", 8899, 10)
    assert hasattr(scanner, "_read_coil")
