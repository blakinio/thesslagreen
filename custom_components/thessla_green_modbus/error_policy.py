"""Shared error and retry policy helpers."""

from __future__ import annotations

from .modbus_exceptions import ModbusIOException


def is_request_cancelled_error(exc: ModbusIOException) -> bool:
    """Return True when a modbus IO error indicates a cancelled request."""
    return "request cancelled" in str(exc).lower() or "cancelled" in str(exc).lower()


def should_log_timeout_traceback(exc: BaseException) -> bool:
    """Return True when timeout traceback should be logged."""
    message = str(exc).lower()
    return "request cancelled" not in message and "cancelled" not in message


def to_log_message(exc: BaseException) -> str:
    """Return a concise exception log message."""
    return f"{type(exc).__name__}: {exc}"
