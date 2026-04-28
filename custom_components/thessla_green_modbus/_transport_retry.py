"""Shared retry helpers for Modbus transport implementations."""

from __future__ import annotations

import asyncio
import logging

from .error_contract import log_retry_attempt
from .transport.retry import calculate_backoff


def log_transport_retry(
    *,
    logger: logging.Logger,
    operation: str,
    attempt: int,
    max_attempts: int,
    exc: BaseException,
    base_backoff: float,
) -> None:
    """Emit standardized transport retry log entry."""

    log_retry_attempt(
        logger=logger,
        layer="transport",
        operation=operation,
        attempt=attempt,
        max_attempts=max_attempts,
        exc=exc,
        backoff=base_backoff,
    )


async def apply_transport_backoff(*, attempt: int, base_backoff: float, max_backoff: float) -> None:
    """Sleep using standard exponential backoff calculation."""

    delay = calculate_backoff(attempt=attempt + 1, base=base_backoff, max_backoff=max_backoff)
    if delay > 0:
        await asyncio.sleep(delay)
