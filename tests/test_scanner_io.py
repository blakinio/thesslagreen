"""Scanner I/O and retry behavior tests."""

import logging
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from custom_components.thessla_green_modbus.modbus_exceptions import ModbusIOException
from custom_components.thessla_green_modbus.scanner.core import ThesslaGreenDeviceScanner
from custom_components.thessla_green_modbus.scanner.io_read import (
    _build_register_chunks,
    _extend_or_abort_register_results,
    _finalize_register_read_failure,
    _handle_input_attempt_exception,
)

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


async def test_read_holding_illegal_address_response_marks_unsupported():
    """Holding illegal-address response should terminate immediately and cache failure."""
    scanner = await ThesslaGreenDeviceScanner.create("192.168.3.17", 8899, 10, retry=3)
    mock_client = AsyncMock()
    error_response = MagicMock()
    error_response.isError.return_value = True
    error_response.exception_code = 2

    with patch(
        "custom_components.thessla_green_modbus.scanner.io_core._call_modbus",
        AsyncMock(return_value=error_response),
    ) as call_mock:
        result = await scanner._read_holding(mock_client, 50, 1)

    assert result is None
    assert call_mock.await_count == 1
    assert 50 in scanner._failed_holding


async def test_read_input_skip_cache_marks_single_register_supported():
    """Single-register input success with skip_cache should mark support."""
    scanner = await ThesslaGreenDeviceScanner.create("192.168.3.17", 8899, 10, retry=2)
    mock_client = AsyncMock()
    ok_response = MagicMock()
    ok_response.isError.return_value = False
    ok_response.registers = [77]

    with patch(
        "custom_components.thessla_green_modbus.scanner.io_core._call_modbus",
        AsyncMock(return_value=ok_response),
    ):
        result = await scanner._read_input(mock_client, 77, 1, skip_cache=True)

    assert result == [77]
    assert 77 not in scanner._failed_input


async def test_read_holding_cancelled_modbusio_stops_retry_loop():
    """Cancelled ModbusIOException aborts holding retries immediately."""
    scanner = await ThesslaGreenDeviceScanner.create("192.168.3.17", 8899, 10, retry=3)
    mock_client = AsyncMock()

    with (
        patch(
            "custom_components.thessla_green_modbus.scanner.io_core._call_modbus",
            AsyncMock(side_effect=ModbusIOException("request cancelled")),
        ) as call_mock,
        patch(
            "custom_components.thessla_green_modbus.scanner.io_read.is_request_cancelled_error",
            return_value=True,
        ),
        patch("asyncio.sleep", AsyncMock()) as sleep_mock,
    ):
        result = await scanner._read_holding(mock_client, 3, 1)

    assert result is None
    assert call_mock.await_count == 1
    sleep_mock.assert_not_called()


def test_handle_input_attempt_exception_logs_retry_and_delegates():
    """Input-attempt helper should centralize retry logging and delegation."""
    scanner = MagicMock(retry=3, backoff=0.1)
    exc = TimeoutError("timeout")
    with (
        patch(
            "custom_components.thessla_green_modbus.scanner.io_read.log_scanner_retry"
        ) as retry_log,
        patch(
            "custom_components.thessla_green_modbus.scanner.io_read._handle_input_read_exception",
            return_value=(True, True),
        ) as delegate,
    ):
        aborted, stop = _handle_input_attempt_exception(
            scanner,
            exc,
            start=10,
            end=11,
            address=10,
            count=2,
            attempt=2,
        )

    assert (aborted, stop) == (True, True)
    retry_log.assert_called_once_with(
        operation="read_input:10-11",
        attempt=2,
        max_attempts=3,
        exc=exc,
        backoff=0.1,
    )
    delegate.assert_called_once()


def test_finalize_register_read_failure_input_aborted_logs_abort_only(caplog):
    """Input aborted transiently should not mark failed range or emit terminal failure."""
    scanner = MagicMock()
    scanner.failed_addresses = {"modbus_exceptions": {"input_registers": set(), "holding_registers": set()}}

    with caplog.at_level(logging.WARNING):
        _finalize_register_read_failure(
            scanner,
            register_type="input_registers",
            start=4,
            end=5,
            retry=3,
            attempted_reads=1,
            aborted_transiently=True,
        )

    assert scanner.failed_addresses["modbus_exceptions"]["input_registers"] == set()
    assert "Aborted reading input registers 4-5" in caplog.text
    assert "Failed to read input registers 4-5" not in caplog.text


def test_finalize_register_read_failure_holding_non_aborted_marks_and_logs(caplog):
    """Holding terminal failure should mark full range and emit error log."""
    scanner = MagicMock()
    scanner.failed_addresses = {"modbus_exceptions": {"input_registers": set(), "holding_registers": set()}}

    with caplog.at_level(logging.ERROR):
        _finalize_register_read_failure(
            scanner,
            register_type="holding_registers",
            start=10,
            end=12,
            retry=2,
            attempted_reads=2,
            aborted_transiently=False,
        )

    assert scanner.failed_addresses["modbus_exceptions"]["holding_registers"] == {10, 11, 12}
    assert "Failed to read holding registers 10-12 after 2 retries" in caplog.text


def test_build_register_chunks_uses_effective_batch():
    """Chunk construction should respect effective batch size boundaries."""
    scanner = MagicMock()
    scanner.effective_batch = 2
    assert _build_register_chunks(scanner, 10, 5) == [(10, 2), (12, 2), (14, 1)]


def test_extend_or_abort_register_results_handles_none_and_appends():
    """Result helper should abort on None and append successful blocks."""
    results = [1]
    can_continue, payload = _extend_or_abort_register_results(results, None)
    assert (can_continue, payload) == (False, None)
    assert results == [1]

    can_continue, payload = _extend_or_abort_register_results(results, [2, 3])
    assert can_continue is True
    assert payload == [1, 2, 3]
