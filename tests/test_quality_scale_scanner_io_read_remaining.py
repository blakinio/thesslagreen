# mypy: ignore-errors
"""Exercise remaining scanner read normalization, retry, and bit-read branches."""

from __future__ import annotations

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

import pytest
from custom_components.thessla_green_modbus.scanner import io_read
from pymodbus.exceptions import ConnectionException, ModbusException, ModbusIOException


def _scanner():
    return SimpleNamespace(
        _client=SimpleNamespace(read_coils=AsyncMock(), read_discrete_inputs=AsyncMock()),
        _transport=None,
        slave_id=10,
        retry=2,
        timeout=1,
        backoff=0,
        backoff_jitter=None,
        _failed_input=set(),
        _failed_holding=set(),
        _holding_failures={},
        _input_failures={},
        _unsupported_input_ranges=[],
        _unsupported_holding_ranges=[],
        _input_skip_log_ranges=set(),
        failed_addresses={
            "modbus_exceptions": {
                "input_registers": set(),
                "holding_registers": set(),
                "coil_registers": set(),
                "discrete_inputs": set(),
            }
        },
        _mark_input_supported=Mock(),
        _mark_holding_supported=Mock(),
        _mark_input_unsupported=Mock(),
        _mark_holding_unsupported=Mock(),
    )


def test_error_response_marks_input_and_holding_paths() -> None:
    scanner = _scanner()
    io_read._handle_error_response(scanner, register_type="input_registers", start=1, end=2, code=2)
    assert scanner._failed_input == {1, 2}
    scanner._mark_input_unsupported.assert_called_once_with(1, 2, 2)

    io_read._handle_error_response(
        scanner, register_type="holding_registers", start=3, end=4, code=2
    )
    assert scanner._failed_holding == {3, 4}
    scanner._mark_holding_unsupported.assert_called_once_with(3, 4, 2)


def test_abort_classifier_and_bit_request_normalization() -> None:
    cancelled = ModbusIOException("request cancelled outside pymodbus")
    assert io_read._should_abort_input_exception(cancelled) is True
    assert io_read._should_abort_input_exception(TimeoutError()) is True
    assert io_read._should_abort_input_exception(OSError()) is True
    assert io_read._should_abort_input_exception(ModbusException()) is False

    scanner = _scanner()
    assert io_read._normalize_bit_read_request(scanner, 10, 3, None) == (
        scanner._client,
        10,
        3,
    )
    assert io_read._normalize_bit_read_request(scanner, 10, 3, 5) == (
        scanner._client,
        10,
        3,
    )
    explicit = object()
    assert io_read._normalize_bit_read_request(scanner, explicit, 10, 3) == (
        explicit,
        10,
        3,
    )


def test_bit_client_resolution_prefers_fresh_transport_client() -> None:
    scanner = _scanner()
    with pytest.raises(ConnectionException):
        io_read._resolve_bit_read_client(scanner, None)

    fresh = object()
    scanner._transport = SimpleNamespace(client=fresh)
    assert io_read._resolve_bit_read_client(scanner, scanner._client) is fresh
    scanner._transport = SimpleNamespace(client=None)
    assert io_read._resolve_bit_read_client(scanner, scanner._client) is scanner._client


@pytest.mark.asyncio
async def test_bit_reconnect_success_failure_and_no_transport() -> None:
    scanner = _scanner()
    original = scanner._client
    assert await io_read._attempt_bit_reconnect(scanner, original) is original

    fresh = object()
    scanner._transport = SimpleNamespace(
        ensure_connected=AsyncMock(),
        client=fresh,
    )
    assert await io_read._attempt_bit_reconnect(scanner, original) is fresh
    assert scanner._client is fresh

    scanner._transport = SimpleNamespace(
        ensure_connected=AsyncMock(side_effect=ConnectionException("offline")),
        client=None,
    )
    assert await io_read._attempt_bit_reconnect(scanner, original) is original


def test_register_error_response_all_classification_paths() -> None:
    scanner = _scanner()
    assert io_read._handle_register_error_response(
        scanner,
        register_type="input_registers",
        start=4,
        end=4,
        address=4,
        count=1,
        code=2,
    ) == (True, None)

    scanner._holding_failures[20] = scanner.retry - 1
    with patch.object(io_read, "track_holding_failure") as track:

        def fail_now(_scanner, _count, address):
            scanner._failed_holding.add(address)

        track.side_effect = fail_now
        assert io_read._handle_register_error_response(
            scanner,
            register_type="holding_registers",
            start=20,
            end=20,
            address=20,
            count=1,
            code=4,
        ) == (True, None)
    assert 20 in scanner._failed_holding

    assert io_read._handle_register_error_response(
        scanner,
        register_type="holding_registers",
        start=30,
        end=31,
        address=30,
        count=2,
        code=4,
    ) == (False, None)


def test_process_response_none_error_success_and_failure_counter_clear() -> None:
    scanner = _scanner()
    assert io_read._process_register_response(
        scanner,
        response=None,
        register_type="input_registers",
        start=1,
        end=1,
        address=1,
        count=1,
        skip_cache=False,
    ) == (False, None)

    error = SimpleNamespace(isError=lambda: True, exception_code=2)
    assert io_read._process_register_response(
        scanner,
        response=error,
        register_type="input_registers",
        start=1,
        end=1,
        address=1,
        count=1,
        skip_cache=False,
    ) == (True, None)

    response = SimpleNamespace(isError=lambda: False, registers=[7])
    done, payload = io_read._process_register_response(
        scanner,
        response=response,
        register_type="input_registers",
        start=1,
        end=1,
        address=1,
        count=1,
        skip_cache=True,
    )
    assert done is True and payload == [7]
    scanner._mark_input_supported.assert_called_once_with(1)

    scanner._holding_failures[5] = 2
    done, payload = io_read._process_register_response(
        scanner,
        response=response,
        register_type="holding_registers",
        start=5,
        end=5,
        address=5,
        count=1,
        skip_cache=True,
    )
    assert done is True and payload == [7]
    scanner._mark_holding_supported.assert_called_once_with(5)
    assert 5 not in scanner._holding_failures


def test_finalize_failure_abort_and_terminal_mark_paths() -> None:
    scanner = _scanner()
    with (
        patch.object(io_read, "log_read_abort") as abort,
        patch.object(io_read, "log_read_failure") as failure,
        patch.object(io_read, "should_log_terminal_failure", return_value=True),
        patch.object(io_read, "mark_failed_addresses") as mark,
    ):
        io_read._finalize_register_read_failure(
            scanner,
            register_type="input_registers",
            start=1,
            end=2,
            retry=2,
            attempted_reads=1,
            aborted_transiently=True,
        )
    abort.assert_called_once()
    failure.assert_called_once()
    mark.assert_not_called()

    with (
        patch.object(io_read, "log_read_failure") as failure,
        patch.object(io_read, "mark_failed_addresses") as mark,
    ):
        io_read._finalize_register_read_failure(
            scanner,
            register_type="holding_registers",
            start=3,
            end=4,
            retry=2,
            attempted_reads=2,
            aborted_transiently=False,
        )
    failure.assert_called_once()
    mark.assert_called_once_with(scanner, "holding_registers", 3, 4)


def test_prepare_input_and_holding_skip_and_failure_thresholds() -> None:
    scanner = _scanner()
    with (
        patch.object(io_read, "_should_skip_input_range", return_value=(True, 1, 3)),
        patch.object(io_read, "mark_failed_addresses") as mark,
    ):
        assert io_read._prepare_input_read(scanner, 2, 2, False) is True
        assert (1, 3) in scanner._input_skip_log_ranges
    mark.assert_called_once_with(scanner, "input_registers", 1, 3)

    with patch.object(io_read, "_should_skip_input_range", return_value=(False, 1, 1)):
        assert io_read._prepare_input_read(scanner, 1, 1, False) is False

    with (
        patch.object(io_read, "_should_skip_holding_range", return_value=(True, 5, 6)),
        patch.object(io_read, "mark_failed_addresses") as mark,
    ):
        assert io_read._prepare_holding_read(scanner, 5, 6, 5, False) is True
    mark.assert_called_once_with(scanner, "holding_registers", 5, 6)

    with patch.object(io_read, "_should_skip_holding_range", return_value=(False, 5, 5)):
        scanner._holding_failures[5] = scanner.retry
        assert io_read._prepare_holding_read(scanner, 5, 5, 5, False) is True
        assert 5 in scanner.failed_addresses["modbus_exceptions"]["holding_registers"]


def test_input_exception_handler_all_expected_categories() -> None:
    scanner = _scanner()
    with patch.object(io_read, "track_input_failure") as track:
        assert io_read._handle_input_read_exception(
            scanner, ModbusIOException("busy"), start=1, end=1, address=1, count=1, attempt=1
        ) == (False, False)
        assert io_read._handle_input_read_exception(
            scanner, TimeoutError(), start=1, end=1, address=1, count=1, attempt=1
        ) == (True, True)
        assert io_read._handle_input_read_exception(
            scanner, OSError(), start=1, end=1, address=1, count=1, attempt=1
        ) == (False, True)
        assert io_read._handle_input_read_exception(
            scanner, ConnectionException("offline"), start=1, end=1, address=1, count=1, attempt=1
        ) == (False, False)
    assert track.call_count == 2
    with pytest.raises(ValueError):
        io_read._handle_input_read_exception(
            scanner, ValueError("bad"), start=1, end=1, address=1, count=1, attempt=1
        )


@pytest.mark.asyncio
async def test_word_attempt_transport_client_cancel_and_exception_paths() -> None:
    scanner = _scanner()
    transport = SimpleNamespace(
        read_input_registers=AsyncMock(
            return_value=SimpleNamespace(isError=lambda: False, registers=[1])
        )
    )
    result = await io_read._execute_word_read_attempt(
        scanner,
        transport=transport,
        client=None,
        method_name="read_input_registers",
        address=1,
        count=1,
        attempt=1,
    )
    assert result.registers == [1]

    handler = Mock(return_value=(True, True))
    with patch.object(
        io_read, "_execute_word_read_attempt", new=AsyncMock(side_effect=TimeoutError())
    ):
        assert await io_read._run_word_read_single_attempt(
            scanner,
            transport=None,
            client=object(),
            method_name="read_input_registers",
            address=1,
            count=1,
            start=1,
            end=1,
            skip_cache=False,
            register_type="input_registers",
            handle_attempt_exception=handler,
            log_success=False,
            attempt=1,
        ) == (False, True, True, None)

    with patch.object(
        io_read,
        "_execute_word_read_attempt",
        new=AsyncMock(side_effect=asyncio.CancelledError()),
    ):
        with pytest.raises(asyncio.CancelledError):
            await io_read._run_word_read_single_attempt(
                scanner,
                transport=None,
                client=object(),
                method_name="read_input_registers",
                address=1,
                count=1,
                start=1,
                end=1,
                skip_cache=False,
                register_type="input_registers",
                handle_attempt_exception=handler,
                log_success=False,
                attempt=1,
            )


@pytest.mark.asyncio
async def test_register_block_signature_paths_and_early_failure() -> None:
    scanner = _scanner()
    scanner.effective_batch = 2
    read_fn = AsyncMock(side_effect=[[1, 2], [3]])
    assert await io_read.read_register_block(scanner, read_fn, 10, 3) == [1, 2, 3]

    client = object()
    read_fn = AsyncMock(return_value=[1])
    assert await io_read.read_register_block(scanner, read_fn, client, 10, 1) == [1]
    read_fn.assert_awaited_with(client, 10, 1)

    read_fn = AsyncMock(return_value=None)
    assert await io_read.read_register_block(scanner, read_fn, 10, 1) is None


def test_holding_exception_handler_all_categories() -> None:
    scanner = _scanner()
    with patch.object(io_read, "track_holding_failure") as track:
        assert io_read._handle_holding_read_exception(
            scanner, TimeoutError(), start=1, end=1, address=1, count=1, attempt=1
        ) == (True, False)
        assert io_read._handle_holding_read_exception(
            scanner, ModbusIOException("cancelled"), start=1, end=1, address=1, count=1, attempt=1
        ) == (True, True)
        assert io_read._handle_holding_read_exception(
            scanner, ModbusIOException("busy"), start=1, end=1, address=1, count=1, attempt=1
        ) == (False, False)
        assert io_read._handle_holding_read_exception(
            scanner, ModbusException("bad"), start=1, end=1, address=1, count=1, attempt=1
        ) == (False, False)
        assert io_read._handle_holding_read_exception(
            scanner, OSError("os"), start=1, end=1, address=1, count=1, attempt=1
        ) == (False, True)
    assert track.call_count == 3
    with pytest.raises(ValueError):
        io_read._handle_holding_read_exception(
            scanner, ValueError("bad"), start=1, end=1, address=1, count=1, attempt=1
        )


@pytest.mark.asyncio
async def test_bit_reads_timeout_reconnect_oserror_cancel_and_failure_bucket() -> None:
    scanner = _scanner()
    scanner.retry = 1
    with patch.object(
        io_read, "_call_modbus_with_fallback", new=AsyncMock(side_effect=TimeoutError())
    ):
        assert await io_read.read_coil(scanner, 10, 2) is None
    assert scanner.failed_addresses["modbus_exceptions"]["coil_registers"] == {10, 11}

    scanner.failed_addresses["modbus_exceptions"]["discrete_inputs"].clear()
    scanner.retry = 2
    good = SimpleNamespace(isError=lambda: False, bits=[True, False])
    with (
        patch.object(
            io_read,
            "_call_modbus_with_fallback",
            new=AsyncMock(side_effect=[ConnectionException("offline"), good]),
        ),
        patch.object(
            io_read,
            "_attempt_bit_reconnect",
            new=AsyncMock(return_value=scanner._client),
        ) as reconnect,
        patch.object(io_read, "_sleep_retry_backoff", new=AsyncMock()),
    ):
        assert await io_read.read_discrete(scanner, 20, 2) == [True, False]
    reconnect.assert_awaited_once()

    scanner.retry = 1
    with patch.object(
        io_read, "_call_modbus_with_fallback", new=AsyncMock(side_effect=OSError("os"))
    ):
        assert await io_read.read_coil(scanner, 30, 1) is None

    with patch.object(
        io_read,
        "_call_modbus_with_fallback",
        new=AsyncMock(side_effect=asyncio.CancelledError()),
    ):
        with pytest.raises(asyncio.CancelledError):
            await io_read.read_coil(scanner, 40, 1)
