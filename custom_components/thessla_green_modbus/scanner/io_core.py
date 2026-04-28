"""I/O-oriented scanner helpers."""

from __future__ import annotations

import asyncio
import importlib
import logging
import sys
from collections.abc import Callable
from typing import TYPE_CHECKING, Any, cast

from pymodbus.client import AsyncModbusTcpClient

from .. import modbus_helpers as _mh
from ..error_contract import log_retry_attempt
from ..modbus_exceptions import ConnectionException
from ..modbus_helpers import _call_modbus

if TYPE_CHECKING:
    from pymodbus.client import AsyncModbusSerialClient as AsyncModbusSerialClientType


_LOGGER = logging.getLogger(__name__)


def is_request_cancelled_error(exc: Exception) -> bool:
    """Return True when an exception indicates a cancelled Modbus request."""
    message = str(exc).lower()
    return "request cancelled outside pymodbus" in message or "cancelled" in message


def log_scanner_retry(
    *,
    operation: str,
    attempt: int,
    max_attempts: int,
    exc: BaseException,
    backoff: float,
) -> None:
    """Emit standardized scanner retry log entry."""

    log_retry_attempt(
        logger=_LOGGER,
        layer="scanner",
        operation=operation,
        attempt=attempt,
        max_attempts=max_attempts,
        exc=exc,
        backoff=backoff,
    )


def ensure_pymodbus_client_module() -> None:
    """Ensure ``pymodbus.client`` is importable and attached to ``pymodbus``."""
    try:
        pymodbus_mod: Any = importlib.import_module("pymodbus")
        client_mod: Any = importlib.import_module("pymodbus.client")
    except (ImportError, ModuleNotFoundError, AttributeError):
        return
    if not hasattr(pymodbus_mod, "client"):
        pymodbus_mod.client = client_mod
    if hasattr(client_mod, "AsyncModbusTcpClient") and not hasattr(client_mod, "ModbusTcpClient"):
        client_mod.ModbusTcpClient = client_mod.AsyncModbusTcpClient


async def _maybe_retry_yield(backoff: float, attempt: int, retry: int) -> None:
    """Yield control between retries to allow cancellation to propagate."""
    if attempt >= retry or backoff > 0:
        return
    await asyncio.sleep(0)


async def _call_modbus_with_fallback_fn(
    call_modbus: Callable[..., Any],
    func: Any,
    slave_id: int,
    address: int,
    *,
    count: int,
    attempt: int,
    retry: int,
    timeout: int,
    backoff: float,
    backoff_jitter: float | tuple[float, float] | None,
    apply_backoff: bool = True,
) -> Any:
    """Call ``call_modbus`` with rich kwargs, fallback to minimal mock signatures."""
    try:
        return await call_modbus(
            func,
            slave_id,
            address,
            count=count,
            attempt=attempt,
            max_attempts=retry,
            timeout=timeout,
            backoff=0.0,
            backoff_jitter=None,
            apply_backoff=False,
        )
    except TypeError as exc:
        if "unexpected keyword" not in str(exc):
            raise
        return await call_modbus(func, slave_id, address, count=count)


async def _sleep_retry_backoff_fn(
    *,
    calculate_backoff_delay: Callable[[float, int, float | tuple[float, float] | None], float],
    backoff: float,
    backoff_jitter: float | tuple[float, float] | None,
    attempt: int,
    retry: int,
) -> None:
    """Sleep between retries using provided backoff delay calculator."""
    if attempt >= retry:
        return
    delay = calculate_backoff_delay(backoff, attempt + 1, backoff_jitter)
    if delay > 0:
        await asyncio.sleep(delay)
    else:
        await _maybe_retry_yield(backoff=backoff, attempt=attempt, retry=retry)


async def _call_modbus_with_fallback(
    scanner: Any,
    func: Any,
    slave_id: int,
    address: int,
    *,
    count: int,
    attempt: int,
    retry: int,
    timeout: int,
    backoff: float,
    backoff_jitter: float | tuple[float, float] | None,
    apply_backoff: bool = True,
) -> Any:
    """Call `_call_modbus` with rich kwargs, fallback to minimal mock signatures."""
    scanner_module = sys.modules.get(scanner.__class__.__module__)
    call_modbus = getattr(scanner_module, "_call_modbus", _call_modbus)
    return await _call_modbus_with_fallback_fn(
        call_modbus,
        func,
        slave_id,
        address,
        count=count,
        attempt=attempt,
        retry=retry,
        timeout=timeout,
        backoff=backoff,
        backoff_jitter=backoff_jitter,
        apply_backoff=apply_backoff,
    )


async def _sleep_retry_backoff(
    *, backoff: float, backoff_jitter: float | tuple[float, float] | None, attempt: int, retry: int
) -> None:
    """Sleep between retries using modbus_helpers timing semantics."""
    await _sleep_retry_backoff_fn(
        calculate_backoff_delay=lambda base, at, jitter: _mh._calculate_backoff_delay(
            base=base, attempt=at, jitter=jitter
        ),
        backoff=backoff,
        backoff_jitter=backoff_jitter,
        attempt=attempt,
        retry=retry,
    )


def unpack_read_args(
    scanner: Any,
    client_or_address: AsyncModbusTcpClient | AsyncModbusSerialClientType | int,
    address_or_count: int,
    count: int | None,
) -> tuple[AsyncModbusTcpClient | AsyncModbusSerialClientType | None, int, int]:
    """Unpack the overloaded (client, address, count)/(address, count) signatures."""
    _ = scanner
    if count is None or isinstance(client_or_address, int):
        return None, int(client_or_address), address_or_count
    return client_or_address, address_or_count, count


def resolve_transport_and_client(
    scanner: Any,
    client: AsyncModbusTcpClient | AsyncModbusSerialClientType | None,
) -> tuple[Any, Any]:
    """Return (transport, client) ready for reads. Raises if neither available."""
    transport = scanner._transport if client is None else None
    if client is None and transport is None:
        client = scanner._client
    if client is None and transport is None:
        raise ConnectionException("Modbus transport is not connected")
    return transport, client


def track_input_failure(scanner: Any, count: int, address: int) -> None:
    """Increment the failure counter for an input register (single-reg reads)."""
    _track_register_failure(
        scanner=scanner,
        count=count,
        address=address,
        failures_attr="_input_failures",
        failed_attr="_failed_input",
        failed_bucket="input_registers",
    )


def track_holding_failure(scanner: Any, count: int, address: int) -> None:
    """Increment the failure counter for a holding register (single-reg reads)."""
    _track_register_failure(
        scanner=scanner,
        count=count,
        address=address,
        failures_attr="_holding_failures",
        failed_attr="_failed_holding",
        failed_bucket="holding_registers",
    )


def _track_register_failure(
    *,
    scanner: Any,
    count: int,
    address: int,
    failures_attr: str,
    failed_attr: str,
    failed_bucket: str,
) -> None:
    """Increment per-register failure counters and mark unsupported addresses."""
    if count != 1:
        return

    failures_map = cast(dict[int, int], getattr(scanner, failures_attr))
    failed_registers = cast(set[int], getattr(scanner, failed_attr))

    failures = failures_map.get(address, 0) + 1
    failures_map[address] = failures

    if failures >= scanner.retry and address not in failed_registers:
        failed_registers.add(address)
        scanner.failed_addresses["modbus_exceptions"][failed_bucket].add(address)
        _LOGGER.warning("Device does not expose register %d", address)


def _expand_cached_failed_range(
    *, start: int, end: int, failed_registers: set[int]
) -> tuple[int, int] | None:
    """Return contiguous cached-failure range overlapping ``start``-``end``."""
    failed_in_range = [reg for reg in range(start, end + 1) if reg in failed_registers]
    if not failed_in_range:
        return None

    range_start = range_end = failed_in_range[0]
    while range_start - 1 in failed_registers:
        range_start -= 1
    while range_end + 1 in failed_registers:
        range_end += 1
    return range_start, range_end



__all__ = [
    "_call_modbus_with_fallback",
    "_expand_cached_failed_range",
    "_sleep_retry_backoff",
    "ensure_pymodbus_client_module",
    "is_request_cancelled_error",
    "resolve_transport_and_client",
    "track_holding_failure",
    "track_input_failure",
    "unpack_read_args",
]
