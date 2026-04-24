"""Shared retry/error classification contract across integration layers."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Literal

from .modbus_exceptions import ConnectionException, ModbusException, ModbusIOException

ErrorKind = Literal["transient", "permanent"]


@dataclass(frozen=True, slots=True)
class ErrorContract:
    """Normalized error classification output."""

    kind: ErrorKind
    reason: str


def classify_error(exc: BaseException) -> ErrorContract:
    """Classify exceptions into transient/permanent with normalized reasons."""

    if isinstance(exc, TimeoutError):
        return ErrorContract("transient", "timeout")
    if isinstance(exc, ModbusIOException):
        msg = str(exc).lower()
        if "cancelled" in msg:
            return ErrorContract("transient", "cancelled")
        return ErrorContract("transient", "modbus_io")
    if isinstance(exc, ConnectionException):
        return ErrorContract("transient", "connection")
    if isinstance(exc, OSError):
        return ErrorContract("transient", "os_error")
    if isinstance(exc, ModbusException):
        return ErrorContract("permanent", "modbus")
    return ErrorContract("permanent", "unexpected")


def is_transient(exc: BaseException) -> bool:
    """Return True when an error should be retried."""

    return classify_error(exc).kind == "transient"


def log_retry_attempt(
    *,
    logger: logging.Logger,
    layer: str,
    operation: str,
    attempt: int,
    max_attempts: int,
    exc: BaseException,
    backoff: float | None = None,
    extra: dict[str, Any] | None = None,
) -> None:
    """Emit standardized retry logs with attempt/backoff/reason information."""

    contract = classify_error(exc)
    details = {
        "layer": layer,
        "operation": operation,
        "attempt": attempt,
        "max_attempts": max_attempts,
        "reason": contract.reason,
        "kind": contract.kind,
    }
    if backoff is not None:
        details["backoff"] = backoff
    if extra:
        details.update(extra)

    logger.warning(
        "Retry context layer=%(layer)s op=%(operation)s attempt=%(attempt)s/%(max_attempts)s "
        "kind=%(kind)s reason=%(reason)s backoff=%(backoff)s exc=%(exc)s",
        {**details, "backoff": details.get("backoff", 0.0), "exc": exc},
    )
