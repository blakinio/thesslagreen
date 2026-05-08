"""Runtime helpers for config flow operations."""

from __future__ import annotations

import asyncio
import inspect
from collections.abc import Awaitable, Callable
from importlib import import_module
from typing import Any

from .error_policy import (
    is_request_cancelled_error as _is_request_cancelled_error_impl,
)
from .modbus_exceptions import ModbusIOException
from .transport.retry import ErrorKind, calculate_backoff, classify_transport_error, should_retry

TIMEOUT_EXCEPTIONS = (TimeoutError, asyncio.TimeoutError)

_SCANNER_MODULE_PATH = "custom_components.thessla_green_modbus.scanner.core"


async def load_scanner_module(hass: Any) -> Any:
    """Import scanner.core via the HA executor to avoid blocking the event loop.

    When *hass* is ``None`` or lacks ``async_add_executor_job`` the import is
    performed synchronously (unit-test / offline environments).
    """
    if hass is None or not hasattr(hass, "async_add_executor_job"):
        return import_module(_SCANNER_MODULE_PATH)
    return await hass.async_add_executor_job(import_module, _SCANNER_MODULE_PATH)


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
            decision = classify_transport_error(exc)
            if decision.kind is ErrorKind.CANCELLED:
                raise
            if isinstance(exc, ModbusIOException) and decision.reason == "cancelled":
                raise TimeoutError("Modbus request cancelled") from exc
            if not should_retry(decision, attempt, retries):
                raise
            delay = calculate_backoff(attempt=attempt, base=backoff)
            if delay > 0:
                await asyncio.sleep(delay)

    raise RuntimeError("Retry wrapper failed without raising")


async def call_with_optional_timeout(func: Callable[[], Any], timeout: float) -> Any:
    """Call ``func`` and apply timeout only to awaitable results.

    This keeps synchronous helper callbacks inexpensive while still
    enforcing IO timeouts for coroutine-returning scanner operations.
    """
    result = func()
    if inspect.isawaitable(result):
        return await asyncio.wait_for(result, timeout=timeout)
    return result
