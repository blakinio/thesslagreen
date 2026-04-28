"""Scanner I/O and retry behavior tests."""

import logging
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from custom_components.thessla_green_modbus.modbus_exceptions import ModbusIOException
from custom_components.thessla_green_modbus.scanner.core import ThesslaGreenDeviceScanner

pytestmark = pytest.mark.asyncio


async def test_read_holding_skips_after_failure():
    """Holding registers are cached after a failed read."""
    scanner = await ThesslaGreenDeviceScanner.create("192.168.3.17", 8899, 10, retry=2)
    mock_client = AsyncMock()

    with (
        patch(
            "custom_components.thessla_green_modbus.scanner.io_core._call_modbus",
            AsyncMock(side_effect=ModbusIOException("boom")),
        ) as call_mock1,
        patch("asyncio.sleep", AsyncMock()),
    ):
        result = await scanner._read_holding(mock_client, 168, 1)
        assert result is None
        assert call_mock1.await_count == scanner.retry

    with patch(
        "custom_components.thessla_green_modbus.scanner.io_core._call_modbus",
        AsyncMock(),
    ) as call_mock2:
        result = await scanner._read_holding(mock_client, 168, 1)
        assert result is None
        call_mock2.assert_not_called()

    assert 168 in scanner._failed_holding


async def test_read_holding_skips_cached_failed_range_for_multi_register_read():
    """Cached failed holding registers skip overlapping multi-register requests."""
    scanner = await ThesslaGreenDeviceScanner.create("192.168.3.17", 8899, 10, retry=2)
    mock_client = AsyncMock()
    scanner._failed_holding.update({170, 171, 172})

    with patch(
        "custom_components.thessla_green_modbus.scanner.io_core._call_modbus",
        AsyncMock(),
    ) as call_mock:
        result = await scanner._read_holding(mock_client, 170, 3)

    assert result is None
    call_mock.assert_not_called()
    assert scanner.failed_addresses["modbus_exceptions"]["holding_registers"].issuperset(
        {170, 171, 172}
    )


async def test_read_holding_exception_response(caplog):
    """Exception responses should include the exception code in logs."""
    scanner = await ThesslaGreenDeviceScanner.create("192.168.3.17", 8899, 10)
    mock_client = AsyncMock()

    error_response = MagicMock()
    error_response.isError.return_value = True
    error_response.exception_code = 6

    with (
        patch(
            "custom_components.thessla_green_modbus.scanner.io_core._call_modbus",
            AsyncMock(return_value=error_response),
        ) as call_mock,
        patch("asyncio.sleep", AsyncMock()),
        caplog.at_level(logging.DEBUG),
    ):
        result = await scanner._read_holding(mock_client, 1, 1)

    assert result is None
    assert call_mock.await_count == scanner.retry
    assert f"Exception code {error_response.exception_code}" in caplog.text


async def test_read_input_exception_response_mentions_input_registers(caplog):
    """Input exception responses should log the proper register type."""
    scanner = await ThesslaGreenDeviceScanner.create("192.168.3.17", 8899, 10)
    mock_client = AsyncMock()

    error_response = MagicMock()
    error_response.isError.return_value = True
    error_response.exception_code = 6

    with (
        patch(
            "custom_components.thessla_green_modbus.scanner.io_core._call_modbus",
            AsyncMock(return_value=error_response),
        ) as call_mock,
        patch("asyncio.sleep", AsyncMock()),
        caplog.at_level(logging.DEBUG),
    ):
        result = await scanner._read_input(mock_client, 1, 1)

    assert result is None
    assert call_mock.await_count == 1
    assert "while reading input registers 1-1" in caplog.text


async def test_read_holding_timeout_logging(caplog):
    """Timeout errors should log a warning and a final error."""
    scanner = await ThesslaGreenDeviceScanner.create("192.168.3.17", 8899, 10, retry=2)
    mock_client = AsyncMock()

    with (
        patch(
            "custom_components.thessla_green_modbus.scanner.io_core._call_modbus",
            AsyncMock(side_effect=TimeoutError()),
        ),
        patch("asyncio.sleep", AsyncMock()),
        caplog.at_level(logging.WARNING),
    ):
        result = await scanner._read_holding(mock_client, 1, 1)

    assert result is None
    warnings = [r.message for r in caplog.records if r.levelno == logging.WARNING]
    assert any("Timeout reading holding 1" in msg for msg in warnings)
    errors = [r.message for r in caplog.records if r.levelno == logging.ERROR]
    assert any("Failed to read holding registers 1-1" in msg for msg in errors)
