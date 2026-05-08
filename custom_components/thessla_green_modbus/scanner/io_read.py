"""Read operations for scanner I/O."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from pymodbus.client import AsyncModbusTcpClient

from ..modbus_exceptions import ConnectionException, ModbusException, ModbusIOException
from ..transport.retry import ErrorKind, classify_transport_error
from .io_core import (
    _call_modbus_with_fallback,
    _expand_cached_failed_range,
    _sleep_retry_backoff,
    is_request_cancelled_error,
    log_scanner_retry,
    resolve_transport_and_client,
    track_holding_failure,
    track_input_failure,
    unpack_read_args,
)
from .io_read_helpers import (
    append_read_block,
    build_read_attempt_meta,
    build_register_chunks,
    build_success_result,
    classify_skip_range,
    log_read_abort,
    log_read_failure,
    mark_failed_addresses,
    normalize_bit_read_result,
    should_log_terminal_failure,
)

try:
    from pymodbus.client import AsyncModbusSerialClient as AsyncModbusSerialClientType
except (ImportError, AttributeError):
    AsyncModbusSerialClientType = Any

_LOGGER = logging.getLogger(__name__)


def _handle_error_response(
    scanner: Any, *, register_type: str, start: int, end: int, code: int | None
) -> None:
    """Record failed range and unsupported range hints from an exception response."""
    if register_type == "input_registers":
        scanner._failed_input.update(range(start, end + 1))
        scanner._mark_input_unsupported(start, end, code)
    else:
        scanner._failed_holding.update(range(start, end + 1))
        scanner._mark_holding_unsupported(start, end, code)
    mark_failed_addresses(scanner, register_type, start, end)


def _validate_register_response(response: Any) -> tuple[bool, int | None]:
    """Return (is_error, exception_code) for a Modbus response-like object."""
    if response is None:
        return False, None
    if response.isError():
        return True, getattr(response, "exception_code", None)
    return False, None


def _should_abort_input_exception(exc: Exception) -> bool:
    """Return True when input reads should stop retries immediately."""
    if isinstance(exc, ModbusIOException):
        return classify_transport_error(
            exc
        ).kind is ErrorKind.CANCELLED or is_request_cancelled_error(exc)
    return isinstance(exc, (TimeoutError, OSError))


def _normalize_bit_read_request(
    scanner: Any,
    client_or_address: AsyncModbusTcpClient | AsyncModbusSerialClientType | int,
    address_or_count: int,
    count: int | None,
) -> tuple[Any, int, int]:
    """Normalize bit-read call signatures to (client, address, count)."""
    if count is None:
        return scanner._client, int(client_or_address), address_or_count
    if isinstance(client_or_address, int):
        return scanner._client, client_or_address, address_or_count
    return client_or_address, address_or_count, count


def _resolve_bit_read_client(scanner: Any, client: Any) -> Any:
    """Prefer transport client when available for bit reads."""
    if client is None:
        raise ConnectionException("Modbus client is not connected")
    if client is scanner._client and scanner._transport is not None:
        fresh = getattr(scanner._transport, "client", None)
        if fresh is not None:
            return fresh
    return client


async def _attempt_bit_reconnect(scanner: Any, client: Any) -> Any:
    """Try to reconnect via transport after a connection error; return updated client."""
    if scanner._transport is None:
        return client
    try:
        await scanner._transport.ensure_connected()
        transport_client = getattr(scanner._transport, "client", None)
        if transport_client is not None:
            scanner._client = transport_client
            return transport_client
    except (
        ModbusException,
        ConnectionException,
        ModbusIOException,
        TimeoutError,
        OSError,
        AttributeError,
    ):
        pass
    return client


def _extend_or_abort_register_results(
    results: list[int], block: list[int] | None
) -> tuple[bool, list[int] | None]:
    """Append block values and indicate whether read batching should continue."""
    can_continue = append_read_block(results, block)
    if not can_continue:
        return False, None
    return True, results


def _process_register_response(
    scanner: Any,
    *,
    response: Any,
    register_type: str,
    start: int,
    end: int,
    address: int,
    count: int,
    skip_cache: bool,
) -> tuple[bool, list[int] | None]:
    """Normalize and classify a read response.

    Returns (done, payload):
    - done=True,payload=<values|None> when caller should return immediately.
    - done=False,payload=None when caller should continue retries.
    """
    if response is None:
        return False, None

    is_error, code = _validate_register_response(response)
    if is_error:
        _LOGGER.warning(
            "Exception code %s while reading %s %d-%d",
            code,
            register_type.replace("_", " "),
            start,
            end,
        )
        if register_type == "input_registers" or code == 2:
            _handle_error_response(
                scanner,
                register_type=register_type,
                start=start,
                end=end,
                code=code,
            )
            return True, None
        if count == 1:
            track_holding_failure(scanner, count, address)
            if address in scanner._failed_holding:
                _handle_error_response(
                    scanner,
                    register_type="holding_registers",
                    start=start,
                    end=end,
                    code=code or 0,
                )
                return True, None
        return False, None

    if skip_cache and count == 1:
        if register_type == "input_registers":
            scanner._mark_input_supported(address)
        else:
            scanner._mark_holding_supported(address)

    if register_type == "holding_registers" and address in scanner._holding_failures:
        del scanner._holding_failures[address]
    return True, build_success_result(response)


def _handle_terminal_read_failure(scanner: Any, register_type: str, start: int, end: int) -> None:
    """Mark all addresses in a terminally failed read range."""
    mark_failed_addresses(scanner, register_type, start, end)


def _finalize_register_read_failure(
    scanner: Any,
    *,
    register_type: str,
    start: int,
    end: int,
    retry: int,
    attempted_reads: int,
    aborted_transiently: bool,
) -> None:
    """Finalize shared failure state/logging for input/holding read loops."""
    kind = "input" if register_type == "input_registers" else "holding"
    if aborted_transiently:
        log_read_abort(kind, start, end, attempted_reads, retry)
        if should_log_terminal_failure(register_type, aborted_transiently):
            log_read_failure(kind, start, end, retry)
        return

    log_read_failure(kind, start, end, retry)
    _handle_terminal_read_failure(scanner, register_type, start, end)


def _should_skip_input_range(
    scanner: Any, start: int, end: int, skip_cache: bool
) -> tuple[bool, int, int]:
    """Return (skip, mark_start, mark_end) for unsupported/cached input ranges."""
    return classify_skip_range(
        start=start,
        end=end,
        skip_cache=skip_cache,
        unsupported_ranges=scanner._unsupported_input_ranges,
        failed_registers=scanner._failed_input,
        expand_cached_failed_range=_expand_cached_failed_range,
    )


def _should_skip_holding_range(
    scanner: Any, start: int, end: int, skip_cache: bool
) -> tuple[bool, int, int]:
    """Return (skip, mark_start, mark_end) for unsupported/cached holding ranges."""
    return classify_skip_range(
        start=start,
        end=end,
        skip_cache=skip_cache,
        unsupported_ranges=scanner._unsupported_holding_ranges,
        failed_registers=scanner._failed_holding,
        expand_cached_failed_range=_expand_cached_failed_range,
    )


def _prepare_input_read(scanner: Any, start: int, end: int, skip_cache: bool) -> bool:
    """Return True when input read should short-circuit as failed/unsupported."""
    should_skip, skip_start, skip_end = _should_skip_input_range(scanner, start, end, skip_cache)
    if not should_skip:
        return False
    if (skip_start, skip_end) != (start, end) and (
        skip_start,
        skip_end,
    ) not in scanner._input_skip_log_ranges:
        _LOGGER.debug("Skipping cached failed input registers %d-%d", skip_start, skip_end)
        scanner._input_skip_log_ranges.add((skip_start, skip_end))
    _handle_terminal_read_failure(scanner, "input_registers", skip_start, skip_end)
    return True


def _handle_input_read_exception(
    scanner: Any,
    exc: Exception,
    *,
    start: int,
    end: int,
    address: int,
    count: int,
    attempt: int,
) -> tuple[bool, bool]:
    """Handle input read exception.

    Returns (abort_transiently, stop_retries).
    """
    if isinstance(exc, ModbusIOException):
        if _should_abort_input_exception(exc):
            return True, True
        track_input_failure(scanner, count, address)
        return False, False
    if isinstance(exc, TimeoutError):
        return True, True
    if isinstance(exc, OSError):
        return False, True
    if isinstance(exc, (ModbusException, ConnectionException)):
        track_input_failure(scanner, count, address)
        return False, False
    raise exc


def _handle_input_attempt_exception(
    scanner: Any,
    exc: Exception,
    *,
    start: int,
    end: int,
    address: int,
    count: int,
    attempt: int,
) -> tuple[bool, bool]:
    """Log and normalize input-read attempt failures.

    Returns (abort_transiently, stop_retries).
    """
    log_scanner_retry(
        operation=f"read_input:{start}-{end}",
        attempt=attempt,
        max_attempts=scanner.retry,
        exc=exc,
        backoff=scanner.backoff,
    )
    return _handle_input_read_exception(
        scanner,
        exc,
        start=start,
        end=end,
        address=address,
        count=count,
        attempt=attempt,
    )


async def _execute_word_read_attempt(
    scanner: Any,
    *,
    transport: Any,
    client: Any,
    method_name: str,
    address: int,
    count: int,
    attempt: int,
) -> Any:
    """Execute one word-register read attempt via transport or client fallback."""
    if transport is not None:
        return await getattr(transport, method_name)(scanner.slave_id, address, count=count)
    return await _call_modbus_with_fallback(
        scanner,
        getattr(client, method_name),
        scanner.slave_id,
        address,
        count=count,
        attempt=attempt,
        retry=scanner.retry,
        timeout=scanner.timeout,
        backoff=scanner.backoff,
        backoff_jitter=scanner.backoff_jitter,
    )


async def _run_word_read_retry_loop(
    scanner: Any,
    *,
    transport: Any,
    client: Any,
    address: int,
    count: int,
    start: int,
    end: int,
    skip_cache: bool,
    method_name: str,
    register_type: str,
    handle_attempt_exception: Any,
    log_success: bool = False,
) -> list[int] | None:
    """Shared retry loop for word-register (input/holding) reads."""
    attempted_reads = 0
    aborted_transiently = False
    for attempt in range(1, scanner.retry + 1):
        attempted_reads = attempt
        try:
            response = await _execute_word_read_attempt(
                scanner,
                transport=transport,
                client=client,
                method_name=method_name,
                address=address,
                count=count,
                attempt=attempt,
            )
            done, payload = _process_register_response(
                scanner,
                response=response,
                register_type=register_type,
                start=start,
                end=end,
                address=address,
                count=count,
                skip_cache=skip_cache,
            )
            if done:
                if log_success and payload is not None:
                    _LOGGER.debug(
                        "Read %s %d-%d: %s",
                        register_type.replace("_", " "),
                        start,
                        end,
                        payload,
                    )
                return payload
        except asyncio.CancelledError:
            raise
        except (
            TimeoutError,
            ModbusIOException,
            OSError,
            ModbusException,
            ConnectionException,
        ) as exc:
            aborted, stop = handle_attempt_exception(
                scanner,
                exc,
                start=start,
                end=end,
                address=address,
                count=count,
                attempt=attempt,
            )
            aborted_transiently = aborted_transiently or aborted
            if stop:
                break
        await _sleep_retry_backoff(
            backoff=scanner.backoff,
            backoff_jitter=scanner.backoff_jitter,
            attempt=attempt,
            retry=scanner.retry,
        )
    _finalize_register_read_failure(
        scanner,
        register_type=register_type,
        start=start,
        end=end,
        retry=scanner.retry,
        attempted_reads=attempted_reads,
        aborted_transiently=aborted_transiently,
    )
    return None


async def _run_input_read_retry_loop(
    scanner: Any,
    *,
    transport: Any,
    client: Any,
    address: int,
    count: int,
    start: int,
    end: int,
    skip_cache: bool,
) -> list[int] | None:
    """Run input read retry loop and finalize failure state when needed."""
    return await _run_word_read_retry_loop(
        scanner,
        transport=transport,
        client=client,
        address=address,
        count=count,
        start=start,
        end=end,
        skip_cache=skip_cache,
        method_name="read_input_registers",
        register_type="input_registers",
        handle_attempt_exception=_handle_input_attempt_exception,
        log_success=True,
    )


async def read_input(
    scanner: Any,
    client_or_address: AsyncModbusTcpClient | AsyncModbusSerialClientType | int,
    address_or_count: int,
    count: int | None = None,
    *,
    skip_cache: bool = False,
) -> list[int] | None:
    """Read input registers with retry and backoff."""
    client, address, count = unpack_read_args(scanner, client_or_address, address_or_count, count)
    meta = build_read_attempt_meta(address, count)
    start = meta.start
    end = meta.end

    if _prepare_input_read(scanner, start, end, skip_cache):
        return None

    transport, client = resolve_transport_and_client(scanner, client)

    return await _run_input_read_retry_loop(
        scanner,
        transport=transport,
        client=client,
        address=address,
        count=count,
        start=start,
        end=end,
        skip_cache=skip_cache,
    )


async def read_register_block(
    scanner: Any,
    read_fn: Any,
    client_or_start: AsyncModbusTcpClient | AsyncModbusSerialClientType | int,
    start_or_count: int,
    count: int | None = None,
) -> list[int] | None:
    """Read a contiguous register block in MAX-sized chunks using read_fn."""
    if count is None:
        start = int(client_or_start)
        count = start_or_count
        client: AsyncModbusTcpClient | AsyncModbusSerialClientType | None = None
    elif isinstance(client_or_start, int):
        start = client_or_start
        count = start_or_count
        client = None
    else:
        client = client_or_start
        start = start_or_count

    results: list[int] = []
    active_client = client or scanner._client
    for chunk_start, chunk_count in build_register_chunks(start, count, scanner.effective_batch):
        block = await (
            read_fn(chunk_start, chunk_count)
            if active_client is None
            else read_fn(active_client, chunk_start, chunk_count)
        )
        can_continue, _ = _extend_or_abort_register_results(results, block)
        if not can_continue:
            return None
    return results


def _prepare_holding_read(
    scanner: Any, start: int, end: int, address: int, skip_cache: bool
) -> bool:
    """Return True when holding read should short-circuit as failed/unsupported."""
    should_skip, skip_start, skip_end = _should_skip_holding_range(scanner, start, end, skip_cache)
    if should_skip:
        _handle_terminal_read_failure(scanner, "holding_registers", skip_start, skip_end)
        return True

    failures = scanner._holding_failures.get(address, 0)
    if failures >= scanner.retry:
        scanner.failed_addresses["modbus_exceptions"]["holding_registers"].add(address)
        return True
    return False


def _handle_holding_read_exception(
    scanner: Any,
    exc: Exception,
    *,
    start: int,
    end: int,
    address: int,
    count: int,
    attempt: int,
) -> tuple[bool, bool]:
    """Handle holding read exception.

    Returns (abort_transiently, stop_retries).
    """
    if isinstance(exc, TimeoutError):
        _LOGGER.warning(
            "Timeout reading holding %d (attempt %d/%d)",
            address,
            attempt,
            scanner.retry,
        )
        track_holding_failure(scanner, count, address)
        return True, False
    if isinstance(exc, ModbusIOException):
        if is_request_cancelled_error(exc):
            _LOGGER.debug(
                "Cancelled reading holding registers %d-%d on attempt %d/%d: %s",
                start,
                end,
                attempt,
                scanner.retry,
                exc,
            )
            return True, True
        track_holding_failure(scanner, count, address)
        return False, False
    if isinstance(exc, (ModbusException, ConnectionException)):
        track_holding_failure(scanner, count, address)
        return False, False
    if isinstance(exc, OSError):
        _LOGGER.error(
            "Unexpected error reading holding %d on attempt %d: %s",
            address,
            attempt,
            exc,
            exc_info=True,
        )
        return False, True
    raise exc


async def _run_holding_read_retry_loop(
    scanner: Any,
    *,
    transport: Any,
    client: Any,
    address: int,
    count: int,
    start: int,
    end: int,
    skip_cache: bool,
) -> list[int] | None:
    """Run holding read retry loop and finalize failure state when needed."""
    return await _run_word_read_retry_loop(
        scanner,
        transport=transport,
        client=client,
        address=address,
        count=count,
        start=start,
        end=end,
        skip_cache=skip_cache,
        method_name="read_holding_registers",
        register_type="holding_registers",
        handle_attempt_exception=_handle_holding_read_exception,
        log_success=False,
    )


async def read_holding(
    scanner: Any,
    client_or_address: AsyncModbusTcpClient | AsyncModbusSerialClientType | int,
    address_or_count: int,
    count: int | None = None,
    *,
    skip_cache: bool = False,
) -> list[int] | None:
    """Read holding registers with retry, backoff and failure tracking."""
    client, address, count = unpack_read_args(scanner, client_or_address, address_or_count, count)
    meta = build_read_attempt_meta(address, count)
    start = meta.start
    end = meta.end

    if _prepare_holding_read(scanner, start, end, address, skip_cache):
        return None

    transport, client = resolve_transport_and_client(scanner, client)

    return await _run_holding_read_retry_loop(
        scanner,
        transport=transport,
        client=client,
        address=address,
        count=count,
        start=start,
        end=end,
        skip_cache=skip_cache,
    )


async def read_bit_registers(
    scanner: Any,
    method_name: str,
    failed_key: str,
    type_name: str,
    client_or_address: AsyncModbusTcpClient | AsyncModbusSerialClientType | int,
    address_or_count: int,
    count: int | None = None,
) -> list[bool] | None:
    """Shared implementation for coil/discrete reads with retry and backoff."""
    client, address, count = _normalize_bit_read_request(
        scanner, client_or_address, address_or_count, count
    )
    client = _resolve_bit_read_client(scanner, client)

    for attempt in range(1, scanner.retry + 1):
        try:
            response: Any = await _call_modbus_with_fallback(
                scanner,
                getattr(client, method_name),
                scanner.slave_id,
                address,
                count=count,
                attempt=attempt,
                retry=scanner.retry,
                timeout=scanner.timeout,
                backoff=scanner.backoff,
                backoff_jitter=scanner.backoff_jitter,
            )
            if (normalized_bits := normalize_bit_read_result(response, count)) is not None:
                return normalized_bits
        except TimeoutError:
            _LOGGER.warning(
                "Timeout reading %s %d on attempt %d",
                type_name,
                address,
                attempt,
            )
        except (ModbusException, ConnectionException):
            client = await _attempt_bit_reconnect(scanner, client)
        except asyncio.CancelledError:
            raise
        except OSError as exc:
            _LOGGER.error(
                "Unexpected error reading %s %d on attempt %d: %s",
                type_name,
                address,
                attempt,
                exc,
                exc_info=True,
            )
            break

        await _sleep_retry_backoff(
            backoff=scanner.backoff,
            backoff_jitter=scanner.backoff_jitter,
            attempt=attempt,
            retry=scanner.retry,
        )

    scanner.failed_addresses["modbus_exceptions"][failed_key].update(
        range(address, address + count)
    )
    return None


async def read_coil(
    scanner: Any,
    client_or_address: AsyncModbusTcpClient | AsyncModbusSerialClientType | int,
    address_or_count: int,
    count: int | None = None,
) -> list[bool] | None:
    """Read coil registers with retry and backoff."""
    return await read_bit_registers(
        scanner,
        "read_coils",
        "coil_registers",
        "coil",
        client_or_address,
        address_or_count,
        count,
    )


async def read_discrete(
    scanner: Any,
    client_or_address: AsyncModbusTcpClient | AsyncModbusSerialClientType | int,
    address_or_count: int,
    count: int | None = None,
) -> list[bool] | None:
    """Read discrete input registers with retry and backoff."""
    return await read_bit_registers(
        scanner,
        "read_discrete_inputs",
        "discrete_inputs",
        "discrete",
        client_or_address,
        address_or_count,
        count,
    )


__all__ = [
    "_attempt_bit_reconnect",
    "read_bit_registers",
    "read_coil",
    "read_discrete",
    "read_holding",
    "read_input",
    "read_register_block",
]
