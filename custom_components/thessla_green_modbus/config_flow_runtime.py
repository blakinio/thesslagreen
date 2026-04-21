"""Runtime helpers for config flow operations."""

from __future__ import annotations

import asyncio
import inspect
from collections.abc import Awaitable, Callable
from typing import Any

from .modbus_exceptions import ConnectionException, ModbusException, ModbusIOException

TIMEOUT_EXCEPTIONS = (TimeoutError, asyncio.TimeoutError)


def is_request_cancelled_error(exc: ModbusIOException) -> bool:
    """Return True when a modbus IO error indicates a cancelled request."""
    message = str(exc).lower()
    return "request cancelled" in message or "cancelled" in message


async def run_with_retry(
    func: Callable[[], Awaitable[Any]],
    *,
    retries: int,
    backoff: float,
) -> Any:
    """Execute ``func`` with retry and backoff."""
    for attempt in range(1, retries + 1):
        try:
            result = func()
            if inspect.isawaitable(result):
                return await result
            return result
        except asyncio.CancelledError:
            raise
        except ModbusIOException as exc:
            if is_request_cancelled_error(exc):
                raise TimeoutError("Modbus request cancelled") from exc
            if attempt >= retries:
                raise
            delay = backoff * 2 ** (attempt - 1)
            if delay:
                await asyncio.sleep(delay)
        except (*TIMEOUT_EXCEPTIONS, ConnectionException, ModbusException, OSError):
            if attempt >= retries:
                raise
            delay = backoff * 2 ** (attempt - 1)
            if delay:
                await asyncio.sleep(delay)

    raise RuntimeError("Retry wrapper failed without raising")


async def call_with_optional_timeout(func: Callable[[], Any], timeout: float) -> Any:
    """Call ``func`` and apply timeout only to awaitable results."""
    result = func()
    if inspect.isawaitable(result):
        return await asyncio.wait_for(result, timeout=timeout)
    return result

