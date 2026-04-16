"""Scanner I/O helpers shared by scanner_core and compatibility imports."""

from __future__ import annotations

import asyncio
import importlib
from collections.abc import Awaitable, Callable
from typing import Any


def is_request_cancelled_error(exc: Exception) -> bool:
    """Return ``True`` when an exception indicates a cancelled Modbus request."""

    message = str(exc).lower()
    return "request cancelled outside pymodbus" in message or "cancelled" in message


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


async def maybe_retry_yield(backoff: float, attempt: int, retry: int) -> None:
    """Yield control between retries to allow cancellation to propagate."""

    if attempt >= retry or backoff > 0:
        return
    await asyncio.sleep(0)


async def call_modbus_compat(
    call_modbus: Callable[..., Awaitable[Any]],
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


async def sleep_retry_backoff(
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
        await maybe_retry_yield(backoff=backoff, attempt=attempt, retry=retry)


async def _maybe_retry_yield(backoff: float, attempt: int, retry: int) -> None:
    """Compatibility alias for ``maybe_retry_yield``."""
    await maybe_retry_yield(backoff=backoff, attempt=attempt, retry=retry)


async def _call_modbus_compat(
    call_modbus: Callable[..., Awaitable[Any]],
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
    """Compatibility alias for ``call_modbus_compat``."""
    return await call_modbus_compat(
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
    *,
    calculate_backoff_delay: Callable[[float, int, float | tuple[float, float] | None], float],
    backoff: float,
    backoff_jitter: float | tuple[float, float] | None,
    attempt: int,
    retry: int,
) -> None:
    """Compatibility alias for ``sleep_retry_backoff``."""
    await sleep_retry_backoff(
        calculate_backoff_delay=calculate_backoff_delay,
        backoff=backoff,
        backoff_jitter=backoff_jitter,
        attempt=attempt,
        retry=retry,
    )


def _ensure_pymodbus_client_module() -> None:
    """Compatibility alias for ``ensure_pymodbus_client_module``."""
    ensure_pymodbus_client_module()


__all__ = [
    "_call_modbus_compat",
    "_ensure_pymodbus_client_module",
    "_maybe_retry_yield",
    "_sleep_retry_backoff",
    "call_modbus_compat",
    "ensure_pymodbus_client_module",
    "is_request_cancelled_error",
]
