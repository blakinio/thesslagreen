"""Scanner I/O and retry behavior tests."""

import logging
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from custom_components.thessla_green_modbus.modbus_exceptions import (
    ConnectionException,
    ModbusException,
    ModbusIOException,
)
from custom_components.thessla_green_modbus.scanner.core import ThesslaGreenDeviceScanner
from custom_components.thessla_green_modbus.scanner.io_read import (
    _attempt_bit_reconnect,
    _extend_or_abort_register_results,
    _finalize_register_read_failure,
    _handle_input_attempt_exception,
    _handle_register_error_response,
)
from custom_components.thessla_green_modbus.scanner.io_read_helpers import (
    build_read_attempt_meta,
    build_register_chunks,
    classify_skip_range,
    normalize_bit_read_result,
    should_log_terminal_failure,
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
    scanner.failed_addresses = {
        "modbus_exceptions": {"input_registers": set(), "holding_registers": set()}
    }

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
    scanner.failed_addresses = {
        "modbus_exceptions": {"input_registers": set(), "holding_registers": set()}
    }

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
    assert build_register_chunks(10, 5, 2) == [(10, 2), (12, 2), (14, 1)]


def test_build_register_chunks_single_chunk_when_count_fits():
    """Single chunk produced when count does not exceed batch size."""
    assert build_register_chunks(0, 3, 10) == [(0, 3)]


def test_build_register_chunks_exact_multiple():
    """Produces even chunks when count is an exact multiple of batch size."""
    assert build_register_chunks(5, 6, 3) == [(5, 3), (8, 3)]


def test_extend_or_abort_register_results_handles_none_and_appends():
    """Result helper should abort on None and append successful blocks."""
    results = [1]
    can_continue, payload = _extend_or_abort_register_results(results, None)
    assert (can_continue, payload) == (False, None)
    assert results == [1]

    can_continue, payload = _extend_or_abort_register_results(results, [2, 3])
    assert can_continue is True
    assert payload == [1, 2, 3]


def test_build_read_attempt_meta_sets_expected_range():
    """Read-attempt metadata should normalize start/end from address/count."""
    meta = build_read_attempt_meta(30, 4)
    assert (meta.start, meta.end, meta.address, meta.count) == (30, 33, 30, 4)


def test_normalize_bit_read_result_handles_error_and_success():
    """Bit-result normalizer should filter errors and truncate to count."""
    error_response = MagicMock()
    error_response.isError.return_value = True
    assert normalize_bit_read_result(error_response, 2) is None

    ok_response = MagicMock()
    ok_response.isError.return_value = False
    ok_response.bits = [True, False, True]
    assert normalize_bit_read_result(ok_response, 2) == [True, False]


def test_classify_skip_range_covers_skip_cache_unsupported_and_failed():
    """Skip classifier should preserve unsupported and cached-failed semantics."""
    expand = MagicMock(return_value=(22, 24))
    assert classify_skip_range(
        start=20,
        end=21,
        skip_cache=True,
        unsupported_ranges={(20, 30)},
        failed_registers={20, 21},
        expand_cached_failed_range=expand,
    ) == (False, 20, 21)

    assert classify_skip_range(
        start=20,
        end=21,
        skip_cache=False,
        unsupported_ranges={(20, 30)},
        failed_registers=set(),
        expand_cached_failed_range=expand,
    ) == (True, 20, 21)

    expand.return_value = None
    assert classify_skip_range(
        start=20,
        end=21,
        skip_cache=False,
        unsupported_ranges=set(),
        failed_registers={20, 21},
        expand_cached_failed_range=expand,
    ) == (False, 20, 21)

    expand.return_value = (18, 25)
    assert classify_skip_range(
        start=20,
        end=21,
        skip_cache=False,
        unsupported_ranges=set(),
        failed_registers={20, 21},
        expand_cached_failed_range=expand,
    ) == (True, 18, 25)


def test_should_log_terminal_failure_tracks_holding_vs_input_aborts():
    """Terminal failure logging policy should match prior behavior."""
    assert should_log_terminal_failure("input_registers", True) is False
    assert should_log_terminal_failure("holding_registers", True) is True
    assert should_log_terminal_failure("input_registers", False) is True


async def test_attempt_bit_reconnect_no_transport_returns_original_client():
    """Returns original client unchanged when scanner has no transport."""
    scanner = MagicMock()
    scanner._transport = None
    original = AsyncMock()
    result = await _attempt_bit_reconnect(scanner, original)
    assert result is original


async def test_attempt_bit_reconnect_with_transport_returns_transport_client():
    """Returns transport client and updates scanner._client when reconnect succeeds."""
    scanner = MagicMock()
    transport_client = AsyncMock()
    mock_transport = MagicMock()
    mock_transport.ensure_connected = AsyncMock()
    mock_transport.client = transport_client
    scanner._transport = mock_transport

    original = AsyncMock()
    result = await _attempt_bit_reconnect(scanner, original)

    assert result is transport_client
    assert scanner._client is transport_client
    mock_transport.ensure_connected.assert_called_once()


async def test_attempt_bit_reconnect_transport_no_client_attr_returns_original():
    """Returns original client when transport has no .client attribute."""
    scanner = MagicMock()
    mock_transport = MagicMock()
    mock_transport.ensure_connected = AsyncMock()
    mock_transport.client = None
    scanner._transport = mock_transport

    original = AsyncMock()
    result = await _attempt_bit_reconnect(scanner, original)

    assert result is original


async def test_attempt_bit_reconnect_ensure_connected_raises_returns_original():
    """Returns original client when ensure_connected raises any connection error."""
    scanner = MagicMock()
    mock_transport = MagicMock()
    mock_transport.ensure_connected = AsyncMock(side_effect=ModbusException("lost"))
    scanner._transport = mock_transport

    original = AsyncMock()
    result = await _attempt_bit_reconnect(scanner, original)

    assert result is original


async def test_attempt_bit_reconnect_connection_exception_returns_original():
    """Returns original client when ensure_connected raises ConnectionException."""
    scanner = MagicMock()
    mock_transport = MagicMock()
    mock_transport.ensure_connected = AsyncMock(side_effect=ConnectionException("down"))
    scanner._transport = mock_transport

    original = AsyncMock()
    result = await _attempt_bit_reconnect(scanner, original)

    assert result is original


# ---------------------------------------------------------------------------
# _handle_register_error_response
# ---------------------------------------------------------------------------


def _make_error_scanner():
    scanner = MagicMock()
    scanner._failed_input = set()
    scanner._failed_holding = set()
    scanner._holding_failures = {}
    scanner.retry = 3
    return scanner


def test_handle_register_error_response_input_marks_failed_and_returns_done():
    """Input register error marks range failed and signals done=True."""
    scanner = _make_error_scanner()
    done, payload = _handle_register_error_response(
        scanner,
        register_type="input_registers",
        start=10,
        end=10,
        address=10,
        count=1,
        code=2,
    )
    assert done is True
    assert payload is None
    scanner._mark_input_unsupported.assert_called_once()


def test_handle_register_error_response_code2_holding_marks_failed():
    """Exception code 2 on holding registers marks range failed and signals done=True."""
    scanner = _make_error_scanner()
    done, payload = _handle_register_error_response(
        scanner,
        register_type="holding_registers",
        start=20,
        end=20,
        address=20,
        count=1,
        code=2,
    )
    assert done is True
    assert payload is None
    scanner._mark_holding_unsupported.assert_called_once()


def test_handle_register_error_response_holding_non_code2_returns_retry():
    """Holding register error with non-code-2 and count>1 returns done=False (retry)."""
    scanner = _make_error_scanner()
    done, payload = _handle_register_error_response(
        scanner,
        register_type="holding_registers",
        start=30,
        end=35,
        address=30,
        count=6,
        code=None,
    )
    assert done is False
    assert payload is None


def test_handle_register_error_response_holding_single_exhausted_marks_done():
    """Holding register single-address error returns done=True after failure threshold."""
    scanner = _make_error_scanner()
    scanner._failed_holding = {50}
    done, payload = _handle_register_error_response(
        scanner,
        register_type="holding_registers",
        start=50,
        end=50,
        address=50,
        count=1,
        code=None,
    )
    assert done is True
    assert payload is None
