"""Read operations for scanner I/O."""

from __future__ import annotations

import asyncio
import logging
from typing import Any, cast

from pymodbus.client import AsyncModbusTcpClient

from ..modbus_exceptions import ConnectionException, ModbusException, ModbusIOException
from ..modbus_helpers import chunk_register_range
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

try:
    from pymodbus.client import AsyncModbusSerialClient as AsyncModbusSerialClientType
except (ImportError, AttributeError):
    AsyncModbusSerialClientType = Any

_LOGGER = logging.getLogger(__name__)


def _mark_failed_addresses(scanner: Any, register_type: str, start: int, end: int) -> None:
    """Track read failures for a contiguous address range."""
    scanner.failed_addresses["modbus_exceptions"][register_type].update(range(start, end + 1))


def _is_unsupported_range(ranges: Any, start: int, end: int) -> bool:
    """Return True when start-end is fully covered by any unsupported range."""
    return any(skip_start <= start and end <= skip_end for skip_start, skip_end in ranges)


def _log_read_abort(kind: str, start: int, end: int, attempt: int, retry: int) -> None:
    """Log a transiently aborted read due to timeout/cancellation."""
    _LOGGER.warning(
        "Aborted reading %s registers %d-%d after %d/%d attempts due to timeout/cancellation",
        kind,
        start,
        end,
        attempt,
        retry,
    )

def _handle_error_response(scanner: Any, *, register_type: str, start: int, end: int, code: int | None) -> None:
    """Record failed range and unsupported range hints from an exception response."""
    if register_type == "input_registers":
        scanner._failed_input.update(range(start, end + 1))
        scanner._mark_input_unsupported(start, end, code)
    else:
        scanner._failed_holding.update(range(start, end + 1))
        scanner._mark_holding_unsupported(start, end, code)
    _mark_failed_addresses(scanner, register_type, start, end)


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
        return (
            classify_transport_error(exc).kind is ErrorKind.CANCELLED
            or is_request_cancelled_error(exc)
        )
    return isinstance(exc, (TimeoutError, OSError))


def _log_read_failure(kind: str, start: int, end: int, retry: int) -> None:
    """Log terminal read failure after retry budget is exhausted."""
    _LOGGER.error("Failed to read %s registers %d-%d after %d retries", kind, start, end, retry)


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
    start = address
    end = address + count - 1

    if not skip_cache:
        for skip_start, skip_end in scanner._unsupported_input_ranges:
            if skip_start <= start and end <= skip_end:
                _mark_failed_addresses(scanner, "input_registers", start, end)
                return None
    cached_failed_range = (
        None
        if skip_cache
        else _expand_cached_failed_range(
            start=start, end=end, failed_registers=scanner._failed_input
        )
    )
    if cached_failed_range is not None:
        skip_start, skip_end = cached_failed_range
        if (skip_start, skip_end) not in scanner._input_skip_log_ranges:
            _LOGGER.debug("Skipping cached failed input registers %d-%d", skip_start, skip_end)
            scanner._input_skip_log_ranges.add((skip_start, skip_end))
        _mark_failed_addresses(scanner, "input_registers", skip_start, skip_end)
        return None

    transport, client = resolve_transport_and_client(scanner, client)

    attempted_reads = 0
    aborted_transiently = False
    for attempt in range(1, scanner.retry + 1):
        attempted_reads = attempt
        try:
            if transport is not None:
                response = await transport.read_input_registers(
                    scanner.slave_id, address, count=count
                )
            else:
                response = await _call_modbus_with_fallback(
                    scanner,
                    client.read_input_registers,
                    scanner.slave_id,
                    address,
                    count=count,
                    attempt=attempt,
                    retry=scanner.retry,
                    timeout=scanner.timeout,
                    backoff=scanner.backoff,
                    backoff_jitter=scanner.backoff_jitter,
                )
            if response is not None:
                is_error, code = _validate_register_response(response)
                if is_error:
                    _LOGGER.warning(
                        "Exception code %s while reading input registers %d-%d",
                        code,
                        start,
                        end,
                    )
                    _handle_error_response(
                        scanner,
                        register_type="input_registers",
                        start=start,
                        end=end,
                        code=code,
                    )
                    return None
                if skip_cache and count == 1:
                    scanner._mark_input_supported(address)
                registers = cast(list[int], response.registers)
                _LOGGER.debug("Read input registers %d-%d: %s", start, end, registers)
                return registers
        except ModbusIOException as exc:
            log_scanner_retry(
                operation=f"read_input:{start}-{end}",
                attempt=attempt,
                max_attempts=scanner.retry,
                exc=exc,
                backoff=scanner.backoff,
            )
            if _should_abort_input_exception(exc):
                aborted_transiently = True
                break
            track_input_failure(scanner, count, address)
        except (TimeoutError, OSError) as exc:
            log_scanner_retry(
                operation=f"read_input:{start}-{end}",
                attempt=attempt,
                max_attempts=scanner.retry,
                exc=exc,
                backoff=scanner.backoff,
            )
            aborted_transiently = isinstance(exc, TimeoutError)
            break
        except (ModbusException, ConnectionException) as exc:
            log_scanner_retry(
                operation=f"read_input:{start}-{end}",
                attempt=attempt,
                max_attempts=scanner.retry,
                exc=exc,
                backoff=scanner.backoff,
            )
            track_input_failure(scanner, count, address)

        await _sleep_retry_backoff(
            backoff=scanner.backoff,
            backoff_jitter=scanner.backoff_jitter,
            attempt=attempt,
            retry=scanner.retry,
        )

    if aborted_transiently:
        _log_read_abort("input", start, end, attempted_reads, scanner.retry)
        return None

    _mark_failed_addresses(scanner, "input_registers", start, end)
    _log_read_failure("input", start, end, scanner.retry)
    return None


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
    for chunk_start, chunk_count in chunk_register_range(start, count, scanner.effective_batch):
        block = await (
            read_fn(chunk_start, chunk_count)
            if active_client is None
            else read_fn(active_client, chunk_start, chunk_count)
        )
        if block is None:
            return None
        results.extend(block)
    return results


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
    start = address
    end = address + count - 1

    if not skip_cache:
        if _is_unsupported_range(scanner._unsupported_holding_ranges, start, end):
            _mark_failed_addresses(scanner, "holding_registers", start, end)
            return None
        cached_failed_range = _expand_cached_failed_range(
            start=start,
            end=end,
            failed_registers=scanner._failed_holding,
        )
        if cached_failed_range is not None:
            cached_start, cached_end = cached_failed_range
            if cached_start <= start and end <= cached_end:
                _mark_failed_addresses(scanner, "holding_registers", cached_start, cached_end)
                return None

    failures = scanner._holding_failures.get(address, 0)
    if failures >= scanner.retry:
        scanner.failed_addresses["modbus_exceptions"]["holding_registers"].add(address)
        return None

    transport, client = resolve_transport_and_client(scanner, client)

    aborted_transiently = False
    attempted_reads = 0
    for attempt in range(1, scanner.retry + 1):
        attempted_reads = attempt
        try:
            if transport is not None:
                response = await transport.read_holding_registers(
                    scanner.slave_id, address, count=count
                )
            else:
                response = await _call_modbus_with_fallback(
                    scanner,
                    client.read_holding_registers,
                    scanner.slave_id,
                    address,
                    count=count,
                    attempt=attempt,
                    retry=scanner.retry,
                    timeout=scanner.timeout,
                    backoff=scanner.backoff,
                    backoff_jitter=scanner.backoff_jitter,
                )
            if response is not None:
                is_error, code = _validate_register_response(response)
                if is_error:
                    _LOGGER.warning(
                        "Exception code %s while reading holding registers %d-%d",
                        code,
                        start,
                        end,
                    )
                    if code == 2:
                        _handle_error_response(
                            scanner,
                            register_type="holding_registers",
                            start=start,
                            end=end,
                            code=code,
                        )
                        return None
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
                            return None
                    continue
                if skip_cache and count == 1:
                    scanner._mark_holding_supported(address)
                if address in scanner._holding_failures:
                    del scanner._holding_failures[address]
                return cast(list[int], response.registers)
        except TimeoutError:
            _LOGGER.warning(
                "Timeout reading holding %d (attempt %d/%d)",
                address,
                attempt,
                scanner.retry,
            )
            track_holding_failure(scanner, count, address)
            aborted_transiently = True
        except ModbusIOException as exc:
            if is_request_cancelled_error(exc):
                _LOGGER.debug(
                    "Cancelled reading holding registers %d-%d on attempt %d/%d: %s",
                    start,
                    end,
                    attempt,
                    scanner.retry,
                    exc,
                )
                aborted_transiently = True
                break
            track_holding_failure(scanner, count, address)
        except (ModbusException, ConnectionException):
            track_holding_failure(scanner, count, address)
        except asyncio.CancelledError:
            raise
        except OSError as exc:
            _LOGGER.error(
                "Unexpected error reading holding %d on attempt %d: %s",
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

    if aborted_transiently:
        _log_read_abort("holding", start, end, attempted_reads, scanner.retry)
        _log_read_failure("holding", start, end, scanner.retry)
        return None

    _log_read_failure("holding", start, end, scanner.retry)
    _mark_failed_addresses(scanner, "holding_registers", start, end)
    return None


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
    if count is None:
        address = int(client_or_address)
        count = address_or_count
        client = scanner._client
    elif isinstance(client_or_address, int):
        address = client_or_address
        count = address_or_count
        client = scanner._client
    else:
        client = client_or_address
        address = address_or_count

    if client is None:
        raise ConnectionException("Modbus client is not connected")
    if client is scanner._client and scanner._transport is not None:
        fresh = getattr(scanner._transport, "client", None)
        if fresh is not None:
            client = fresh

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
            if response is not None and not response.isError():
                return cast(list[bool], response.bits[:count])
        except TimeoutError:
            _LOGGER.warning(
                "Timeout reading %s %d on attempt %d",
                type_name,
                address,
                attempt,
            )
        except (ModbusException, ConnectionException):
            if scanner._transport is not None:
                try:
                    await scanner._transport.ensure_connected()
                    transport_client = getattr(scanner._transport, "client", None)
                    if transport_client is not None:
                        client = transport_client
                        scanner._client = transport_client
                except (
                    ModbusException,
                    ConnectionException,
                    ModbusIOException,
                    TimeoutError,
                    OSError,
                    AttributeError,
                ):
                    pass
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
    "read_bit_registers",
    "read_coil",
    "read_discrete",
    "read_holding",
    "read_input",
    "read_register_block",
]
