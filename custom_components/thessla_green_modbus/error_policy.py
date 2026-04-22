"""Shared error and retry policy helpers."""

from __future__ import annotations

import asyncio
from enum import StrEnum

from .modbus_exceptions import ConnectionException, ModbusException, ModbusIOException


class ErrorKind(StrEnum):
    """Normalized error categories used by retry callers."""

    CANCELLED = "cancelled"
    TIMEOUT = "timeout"
    TRANSIENT = "transient"
    PERMANENT = "permanent"
    UNKNOWN = "unknown"


TIMEOUT_EXCEPTIONS: tuple[type[BaseException], ...] = (TimeoutError, asyncio.TimeoutError)


def is_request_cancelled_error(exc: ModbusIOException) -> bool:
    """Return True when a modbus IO error indicates a cancelled request."""
    message = str(exc).lower()
    return "request cancelled" in message or "cancelled" in message


def classify_exception(exc: BaseException) -> ErrorKind:
    """Classify runtime exceptions into shared retry categories."""
    if isinstance(exc, asyncio.CancelledError):
        return ErrorKind.CANCELLED
    if isinstance(exc, ModbusIOException):
        if is_request_cancelled_error(exc):
            return ErrorKind.TIMEOUT
        return ErrorKind.TRANSIENT
    if isinstance(exc, (*TIMEOUT_EXCEPTIONS, ConnectionException, OSError)):
        return ErrorKind.TRANSIENT
    if isinstance(exc, ModbusException):
        return ErrorKind.PERMANENT
    return ErrorKind.UNKNOWN


def should_retry(kind: ErrorKind, attempt: int, max_attempts: int) -> bool:
    """Return whether another retry should be attempted."""
    if attempt >= max_attempts:
        return False
    return kind in {ErrorKind.TIMEOUT, ErrorKind.TRANSIENT}


def next_backoff(
    *,
    attempt: int,
    base: float,
    max_backoff: float | None = None,
) -> float:
    """Return exponential-backoff delay for an attempt number."""
    delay = max(0.0, float(base)) * (2 ** max(0, attempt - 1))
    if max_backoff is not None and max_backoff > 0:
        delay = min(delay, max_backoff)
    return delay


def should_log_timeout_traceback(exc: BaseException) -> bool:
    """Return True when timeout traceback should be logged."""
    message = str(exc).lower()
    return "request cancelled" not in message and "cancelled" not in message


def to_log_message(exc: BaseException) -> str:
    """Return a concise exception log message."""
    return f"{type(exc).__name__}: {exc}"
