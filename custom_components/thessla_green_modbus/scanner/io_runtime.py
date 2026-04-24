"""Low-level scanner runtime IO/bootstrap helpers."""

from __future__ import annotations

import importlib
from typing import Any

from .. import modbus_helpers as _mh
from ..error_contract import classify_error
from . import io as _scanner_io_impl


def attach_pymodbus_client_module() -> None:
    """Ensure `pymodbus.client` is importable and attached to `pymodbus`."""
    try:
        pymodbus: Any = importlib.import_module("pymodbus")
        pymodbus_client: Any = importlib.import_module("pymodbus.client")
        if not hasattr(pymodbus, "client"):
            pymodbus.client = pymodbus_client  # pragma: no cover - defensive
    except (ImportError, AttributeError):  # pragma: no cover
        return


async def maybe_retry_yield(backoff: float, attempt: int, retry: int) -> None:
    """Yield control between retries to allow cancellation to propagate."""
    await _scanner_io_impl._maybe_retry_yield(backoff=backoff, attempt=attempt, retry=retry)


async def call_modbus_with_fallback(
    call_modbus_fn: Any,
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
    return await _scanner_io_impl._call_modbus_with_fallback_fn(
        call_modbus_fn,
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


async def sleep_retry_backoff(
    *, backoff: float, backoff_jitter: float | tuple[float, float] | None, attempt: int, retry: int
) -> None:
    """Sleep between retries using modbus_helpers timing semantics."""
    await _scanner_io_impl._sleep_retry_backoff_fn(
        calculate_backoff_delay=lambda base, at, jitter: _mh._calculate_backoff_delay(
            base=base, attempt=at, jitter=jitter
        ),
        backoff=backoff,
        backoff_jitter=backoff_jitter,
        attempt=attempt,
        retry=retry,
    )


def classify_scanner_error(exc: BaseException) -> tuple[str, str]:
    """Expose normalized retry classification for scanner layer tests."""

    contract = classify_error(exc)
    return contract.kind, contract.reason


def log_scanner_retry(
    *,
    operation: str,
    attempt: int,
    max_attempts: int,
    exc: BaseException,
    backoff: float,
) -> None:
    """Expose scanner retry logging adapter for contract tests."""

    _scanner_io_impl.log_scanner_retry(
        operation=operation,
        attempt=attempt,
        max_attempts=max_attempts,
        exc=exc,
        backoff=backoff,
    )
