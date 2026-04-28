"""Shared retry/error classification contract across integration layers."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Literal

from .transport.retry import ErrorKind as RetryErrorKind
from .transport.retry import classify_transport_error

ErrorKind = Literal["transient", "permanent"]


@dataclass(frozen=True, slots=True)
class ErrorContract:
    """Normalized error classification output."""

    kind: ErrorKind
    reason: str


def classify_error(exc: BaseException) -> ErrorContract:
    """Classify exceptions into transient/permanent with normalized reasons."""
    decision = classify_transport_error(exc)
    if decision.kind is RetryErrorKind.TRANSIENT:
        return ErrorContract("transient", decision.reason)
    if decision.kind is RetryErrorKind.CANCELLED:
        return ErrorContract("transient", "cancelled")
    if decision.kind is RetryErrorKind.UNSUPPORTED_REGISTER:
        return ErrorContract("permanent", "illegal_data_address")
    return ErrorContract("permanent", decision.reason)


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
