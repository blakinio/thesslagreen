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
                scanner.failed_addresses["modbus_exceptions"]["input_registers"].update(
                    range(start, end + 1)
                )
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
        scanner.failed_addresses["modbus_exceptions"]["input_registers"].update(
            range(skip_start, skip_end + 1)
        )
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
                if response.isError():
                    code = getattr(response, "exception_code", None)
                    _LOGGER.warning(
                        "Exception code %s while reading input registers %d-%d",
                        code,
                        start,
                        end,
                    )
                    scanner._failed_input.update(range(start, end + 1))
                    scanner._mark_input_unsupported(start, end, code)
                    scanner.failed_addresses["modbus_exceptions"]["input_registers"].update(
                        range(start, end + 1)
                    )
                    return None
                if skip_cache and count == 1:
                    scanner._mark_input_supported(address)
                registers = cast(list[int], response.registers)
                _LOGGER.debug("Read input registers %d-%d: %s", start, end, registers)
                return registers
        except ModbusIOException as exc:
            decision = classify_transport_error(exc)
            log_scanner_retry(
                operation=f"read_input:{start}-{end}",
                attempt=attempt,
                max_attempts=scanner.retry,
                exc=exc,
                backoff=scanner.backoff,
            )
            if decision.kind is ErrorKind.CANCELLED or is_request_cancelled_error(exc):
                aborted_transiently = True
                break
            track_input_failure(scanner, count, address)
        except TimeoutError as exc:
            log_scanner_retry(
                operation=f"read_input:{start}-{end}",
                attempt=attempt,
                max_attempts=scanner.retry,
                exc=exc,
                backoff=scanner.backoff,
            )
            aborted_transiently = True
            break
        except OSError as exc:
            log_scanner_retry(
                operation=f"read_input:{start}-{end}",
                attempt=attempt,
                max_attempts=scanner.retry,
                exc=exc,
                backoff=scanner.backoff,
            )
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
        _LOGGER.warning(
            "Aborted reading input registers %d-%d after %d/%d attempts due to timeout/cancellation",
            start,
            end,
            attempted_reads,
            scanner.retry,
        )
        return None

    scanner.failed_addresses["modbus_exceptions"]["input_registers"].update(range(start, end + 1))
    _LOGGER.error(
        "Failed to read input registers %d-%d after %d retries", start, end, scanner.retry
    )
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
        for skip_start, skip_end in scanner._unsupported_holding_ranges:
            if skip_start <= start and end <= skip_end:
                scanner.failed_addresses["modbus_exceptions"]["holding_registers"].update(
                    range(start, end + 1)
                )
                return None
        cached_failed_range = _expand_cached_failed_range(
            start=start,
            end=end,
            failed_registers=scanner._failed_holding,
        )
        if cached_failed_range is not None:
            cached_start, cached_end = cached_failed_range
            if cached_start <= start and end <= cached_end:
                scanner.failed_addresses["modbus_exceptions"]["holding_registers"].update(
                    range(cached_start, cached_end + 1)
                )
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
                if response.isError():
                    code = getattr(response, "exception_code", None)
                    _LOGGER.warning(
                        "Exception code %s while reading holding registers %d-%d",
                        code,
                        start,
                        end,
                    )
                    if code == 2:
                        scanner._failed_holding.update(range(start, end + 1))
                        scanner._mark_holding_unsupported(start, end, code)
                        scanner.failed_addresses["modbus_exceptions"]["holding_registers"].update(
                            range(start, end + 1)
                        )
                        return None
                    if count == 1:
                        track_holding_failure(scanner, count, address)
                        if address in scanner._failed_holding:
                            scanner._failed_holding.update(range(start, end + 1))
                            scanner._mark_holding_unsupported(start, end, code or 0)
                            scanner.failed_addresses["modbus_exceptions"][
                                "holding_registers"
                            ].update(range(start, end + 1))
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
        _LOGGER.warning(
            "Aborted reading holding registers %d-%d after %d/%d attempts due to timeout/cancellation",
            start,
            end,
            attempted_reads,
            scanner.retry,
        )
        _LOGGER.error(
            "Failed to read holding registers %d-%d after %d retries", start, end, scanner.retry
        )
        return None

    _LOGGER.error(
        "Failed to read holding registers %d-%d after %d retries", start, end, scanner.retry
    )
    scanner.failed_addresses["modbus_exceptions"]["holding_registers"].update(range(start, end + 1))
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
