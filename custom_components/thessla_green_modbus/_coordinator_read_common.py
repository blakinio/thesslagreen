"""Shared low-level read helpers for coordinator I/O retry paths."""

from __future__ import annotations

import inspect
import logging
from collections.abc import Callable
from typing import Any

from ._coordinator_retry import _PermanentModbusError
from .modbus_exceptions import ModbusException, ModbusIOException

_LOGGER = logging.getLogger(__name__)
ILLEGAL_DATA_ADDRESS = 2


def is_illegal_data_address_response(response: Any) -> bool:
    """Return True when response reports ILLEGAL DATA ADDRESS."""
    return getattr(response, "exception_code", None) == ILLEGAL_DATA_ADDRESS


def is_transient_error_response(response: Any) -> bool:
    """Return True when response looks transient and should be retried."""
    exception_code = getattr(response, "exception_code", None)
    return exception_code is None or exception_code != ILLEGAL_DATA_ADDRESS


async def execute_read_call(
    coordinator: Any,
    read_method: Callable[..., Any],
    start_address: int,
    count: int,
    attempt: int,
) -> Any:
    """Execute one read attempt with method fallback through `_call_modbus`."""
    call_result = read_method(
        coordinator.slave_id,
        start_address,
        count=count,
        attempt=attempt,
    )
    if call_result is None:
        call_result = coordinator._call_modbus(
            read_method,
            start_address,
            count=count,
            attempt=attempt,
        )
    return await call_result if inspect.isawaitable(call_result) else call_result


def log_read_retry(
    coordinator: Any,
    *,
    register_type: str,
    start_address: int,
    attempt: int,
    exc: Exception,
    timeout: bool = False,
) -> None:
    """Log retry information for read failures."""
    if timeout:
        _LOGGER.warning(
            "Timeout reading %s registers at %s (attempt %s/%s)",
            register_type,
            start_address,
            attempt,
            coordinator.retry,
        )
    _LOGGER.debug(
        "Retrying %s registers at %s (attempt %s/%s): %s",
        register_type,
        start_address,
        attempt + 1,
        coordinator.retry,
        exc,
    )


def raise_for_error_response(
    coordinator: Any,
    response: Any,
    *,
    register_type: str,
    start_address: int,
) -> None:
    """Raise specific exception for Modbus error responses."""
    if not response.isError():
        return
    if is_illegal_data_address_response(response):
        raise _PermanentModbusError(
            f"Illegal data address for {register_type} registers at {start_address}"
        )
    if is_transient_error_response(response):
        raise ModbusIOException(
            f"Transient error reading {register_type} registers at {start_address}"
        )
    raise ModbusException(
        # pragma: no cover - impossible: not illegal and not transient implies illegal
        f"Failed to read {register_type} registers at {start_address}"
    )
