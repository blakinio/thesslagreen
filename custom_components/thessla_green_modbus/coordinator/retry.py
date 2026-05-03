"""Retry/disconnect helpers extracted from coordinator IO mixin."""

from __future__ import annotations

import logging
from typing import Any

from ..error_contract import log_retry_attempt
from ..modbus_exceptions import ConnectionException, ModbusException, ModbusIOException
from ..transport.retry import classify_transport_error

_LOGGER = logging.getLogger(__name__)

DISCONNECT_EXCEPTIONS = (
    TimeoutError,
    ModbusIOException,
    ConnectionException,
    OSError,
)


class _PermanentModbusError(ModbusException):
    """Modbus error that should not be retried."""


def log_coordinator_retry(
    *,
    operation: str,
    attempt: int,
    max_attempts: int,
    exc: BaseException,
    backoff: float | None = None,
) -> None:
    """Emit standardized coordinator retry log entry."""

    log_retry_attempt(
        logger=_LOGGER,
        layer="coordinator",
        operation=operation,
        attempt=attempt,
        max_attempts=max_attempts,
        exc=exc,
        backoff=backoff,
    )


def _log_disconnect_failure(
    *,
    register_type: str,
    start_address: int,
    attempt: int,
    retry: int,
    error: Exception,
) -> Exception:
    """Log disconnect failure and return the same exception for callers."""
    log_coordinator_retry(
        operation=f"disconnect:{register_type}:{start_address}",
        attempt=attempt,
        max_attempts=retry,
        exc=error,
    )
    return error


def classify_retry_error(exc: BaseException) -> tuple[str, str]:
    """Expose normalized retry classification for coordinator layer tests."""

    decision = classify_transport_error(exc)
    return decision.kind.value, decision.reason


async def _safe_disconnect_for_retry(
    owner: Any,
    *,
    register_type: str,
    start_address: int,
    attempt: int,
    restore_client: bool,
) -> Exception | None:
    """Execute disconnect hook and normalize transient disconnect failures."""
    disconnect_cb = getattr(owner, "_disconnect", None)
    if not callable(disconnect_cb):
        return None

    previous_client = owner.client if restore_client else None
    try:
        await disconnect_cb()  # pragma: no cover
    except DISCONNECT_EXCEPTIONS as disconnect_error:
        return _log_disconnect_failure(
            register_type=register_type,
            start_address=start_address,
            attempt=attempt,
            retry=owner.retry,
            error=disconnect_error,
        )

    if restore_client and owner.client is None and previous_client is not None:
        owner.client = previous_client
    return None


async def disconnect_and_reconnect_for_retry(
    owner: Any,
    *,
    register_type: str,
    start_address: int,
    attempt: int,
) -> Exception | None:
    """Reset connection before retry and reconnect transport if available."""
    disconnect_error = await _safe_disconnect_for_retry(
        owner,
        register_type=register_type,
        start_address=start_address,
        attempt=attempt,
        restore_client=owner._transport is None,
    )
    if disconnect_error is not None:
        return disconnect_error

    if owner._transport is None:
        # Legacy/unit-test path that relies on ``self.client`` mocks.
        # Keep the existing client intact between attempts.
        return None

    try:
        await owner._ensure_connection()
    except (
        TimeoutError,
        ModbusIOException,
        ConnectionException,
        OSError,
    ) as reconnect:
        log_coordinator_retry(
            operation=f"reconnect:{register_type}:{start_address}",
            attempt=attempt + 1,
            max_attempts=owner.retry,
            exc=reconnect,
            backoff=getattr(owner, "backoff", 0.0),
        )
        return reconnect
    return None


async def _handle_retry_exception(
    owner: Any,
    *,
    register_type: str,
    start_address: int,
    attempt: int,
    exc: Exception,
    reconnect: bool,
    timeout: bool = False,
) -> Exception:
    """Handle retryable read exception and return the most recent error."""
    if attempt >= owner.retry:
        raise exc

    if reconnect:
        reconnect_error = await disconnect_and_reconnect_for_retry(
            owner,
            register_type=register_type,
            start_address=start_address,
            attempt=attempt,
        )
        if reconnect_error is not None:
            return reconnect_error

    log_coordinator_retry(
        operation=f"read:{register_type}:{start_address}",
        attempt=attempt,
        max_attempts=owner.retry,
        exc=exc,
        backoff=getattr(owner, "backoff", 0.0),
    )
    owner._log_read_retry(
        register_type=register_type,
        start_address=start_address,
        attempt=attempt,
        exc=exc,
        timeout=timeout,
    )
    return exc


async def read_with_retry(
    owner: Any,
    read_method: Any,
    start_address: int,
    count: int,
    *,
    register_type: str,
) -> Any:
    """Read registers with retry/backoff on transient transport errors."""
    last_error: Exception | None = None
    for attempt in range(1, owner.retry + 1):
        try:
            response = await owner._execute_read_call(
                read_method,
                start_address,
                count,
                attempt,
            )
            if response is None:
                raise ModbusException(
                    f"Failed to read {register_type} registers at {start_address}"
                )
            owner._raise_for_error_response(
                response,
                register_type=register_type,
                start_address=start_address,
            )
            return response
        except _PermanentModbusError:
            raise
        except TimeoutError as exc:
            last_error = await _handle_retry_exception(
                owner,
                register_type=register_type,
                start_address=start_address,
                attempt=attempt,
                exc=exc,
                reconnect=True,
                timeout=True,
            )
        except (ModbusIOException, ConnectionException, OSError) as exc:
            last_error = await _handle_retry_exception(
                owner,
                register_type=register_type,
                start_address=start_address,
                attempt=attempt,
                exc=exc,
                reconnect=True,
            )
        except ModbusException as exc:
            last_error = await _handle_retry_exception(
                owner,
                register_type=register_type,
                start_address=start_address,
                attempt=attempt,
                exc=exc,
                reconnect=False,
            )
    if last_error is not None:  # pragma: no cover
        raise last_error  # pragma: no cover
    raise ModbusException(
        f"Failed to read {register_type} registers at {start_address}"
    )  # pragma: no cover
