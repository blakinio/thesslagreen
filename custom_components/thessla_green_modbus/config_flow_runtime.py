"""Runtime helpers for config flow operations."""

from __future__ import annotations

import asyncio
import inspect
from collections.abc import Awaitable, Callable
from typing import Any

from .error_policy import (
    ErrorKind,
    classify_exception,
    next_backoff,
    should_retry,
)
from .error_policy import (
    is_request_cancelled_error as _is_request_cancelled_error_impl,
)
from .modbus_exceptions import ModbusIOException

TIMEOUT_EXCEPTIONS = (TimeoutError, asyncio.TimeoutError)


def is_request_cancelled_error(exc: ModbusIOException) -> bool:
    """Compatibility wrapper for config_flow imports/tests."""
    return _is_request_cancelled_error_impl(exc)


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
        except BaseException as exc:
            kind = classify_exception(exc)
            if kind is ErrorKind.CANCELLED:
                raise
            if isinstance(exc, ModbusIOException) and kind is ErrorKind.TIMEOUT:
                raise TimeoutError("Modbus request cancelled") from exc
            if not should_retry(kind, attempt, retries):
                raise
            delay = next_backoff(attempt=attempt, base=backoff)
            if delay > 0:
                await asyncio.sleep(delay)

    raise RuntimeError("Retry wrapper failed without raising")


async def call_with_optional_timeout(func: Callable[[], Any], timeout: float) -> Any:
    """Call ``func`` and apply timeout only to awaitable results."""
    result = func()
    if inspect.isawaitable(result):
        return await asyncio.wait_for(result, timeout=timeout)
    return result
