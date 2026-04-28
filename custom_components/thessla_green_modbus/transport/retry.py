"""Shared transport retry/error classification helpers."""

from __future__ import annotations

import asyncio
import random
from dataclasses import dataclass
from enum import StrEnum

from ..modbus_exceptions import ConnectionException, ModbusException, ModbusIOException


class ErrorKind(StrEnum):
    """Normalized transport error kinds."""

    TRANSIENT = "transient"
    PERMANENT = "permanent"
    UNSUPPORTED_REGISTER = "unsupported_register"
    CANCELLED = "cancelled"


@dataclass(frozen=True, slots=True)
class RetryDecision:
    """Decision returned by transport error classification."""

    retry: bool
    kind: ErrorKind
    reason: str


def _is_unsupported_register_error(exc: BaseException) -> bool:
    message = str(exc).lower()
    unsupported_tokens = (
        "illegal data address",
        "illegal address",
        "unsupported register",
        "exception code 2",
    )
    return any(token in message for token in unsupported_tokens)


def classify_transport_error(exc: BaseException) -> RetryDecision:
    """Classify errors for transport/coordinator/scanner retry callers."""
    if isinstance(exc, asyncio.CancelledError):
        return RetryDecision(retry=False, kind=ErrorKind.CANCELLED, reason="cancelled")
    if isinstance(exc, TimeoutError):
        return RetryDecision(retry=True, kind=ErrorKind.TRANSIENT, reason="timeout")
    if isinstance(exc, ModbusIOException):
        msg = str(exc).lower()
        if "cancelled" in msg:
            return RetryDecision(retry=True, kind=ErrorKind.TRANSIENT, reason="cancelled")
        return RetryDecision(retry=True, kind=ErrorKind.TRANSIENT, reason="modbus_io")
    if isinstance(exc, ConnectionException | OSError):
        return RetryDecision(retry=True, kind=ErrorKind.TRANSIENT, reason="connection")
    if isinstance(exc, ModbusException):
        if _is_unsupported_register_error(exc):
            return RetryDecision(
                retry=False,
                kind=ErrorKind.UNSUPPORTED_REGISTER,
                reason="illegal_data_address",
            )
        return RetryDecision(retry=False, kind=ErrorKind.PERMANENT, reason="modbus")
    return RetryDecision(retry=False, kind=ErrorKind.PERMANENT, reason="unexpected")


def should_retry(
    decision: RetryDecision | ErrorKind,
    attempt: int,
    max_attempts: int,
) -> bool:
    """Return True when another retry should be attempted."""
    if attempt >= max_attempts:
        return False
    kind = decision.kind if isinstance(decision, RetryDecision) else decision
    return kind is ErrorKind.TRANSIENT


def calculate_backoff(
    *,
    attempt: int,
    base: float,
    max_backoff: float | None = None,
    jitter: float | tuple[float, float] | None = None,
) -> float:
    """Calculate bounded exponential backoff with optional jitter."""
    delay = max(0.0, float(base)) * (2 ** max(0, attempt - 1))
    if jitter is not None:
        if isinstance(jitter, tuple):
            low, high = float(jitter[0]), float(jitter[1])
            delay += random.uniform(low, high)
        else:
            delta = abs(float(jitter))
            delay += random.uniform(-delta, delta)
    if max_backoff is not None and max_backoff > 0:
        delay = min(delay, float(max_backoff))
    return max(0.0, float(delay))
