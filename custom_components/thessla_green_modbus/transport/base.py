"""Base transport primitives used by transport implementations."""

from __future__ import annotations

import asyncio
import logging
from abc import ABC, abstractmethod
from typing import Any

from .._transport_retry import apply_transport_backoff, log_transport_retry
from ..error_policy import to_log_message
from ..modbus_exceptions import ConnectionException, ModbusException, ModbusIOException
from .retry import classify_transport_error

_LOGGER = logging.getLogger(__name__)


class BaseModbusTransport(ABC):
    """Base interface for transport implementations."""

    def __init__(
        self,
        *,
        max_retries: int,
        base_backoff: float,
        max_backoff: float,
        timeout: float,
        offline_state: bool = False,
    ) -> None:
        self.max_retries = max(1, int(max_retries))
        self.base_backoff = max(0.0, float(base_backoff))
        self.max_backoff = max(0.0, float(max_backoff))
        self.timeout = float(timeout)
        self.offline_state = offline_state
        self._lock = asyncio.Lock()

    @property
    def offline(self) -> bool:
        return self.offline_state

    def is_connected(self) -> bool:
        return self._is_connected()

    async def _mark_offline_and_reset(self) -> None:
        self.offline_state = True
        await self._reset_connection()

    async def _execute(self, func: Any, *, ensure_connection: bool = False) -> Any:
        try:
            if ensure_connection:
                await self.ensure_connected()
            result = await func()
            self.offline_state = False
            return result
        except asyncio.CancelledError:
            self.offline_state = True
            try:
                await self._reset_connection()
            except (ConnectionException, ModbusException, OSError, RuntimeError) as exc:
                _LOGGER.debug("Reset connection failed during CancelledError handling: %s", exc)
            raise
        except (TimeoutError, ModbusIOException, ConnectionException, OSError):
            await self._mark_offline_and_reset()
            raise
        except ModbusException as exc:
            decision = classify_transport_error(exc)
            _LOGGER.error(
                "Permanent Modbus error (%s/%s): %s",
                decision.kind.value,
                decision.reason,
                to_log_message(exc),
            )
            self.offline_state = True
            raise
        except (AttributeError, RuntimeError, TypeError, ValueError) as exc:  # pragma: no cover
            _LOGGER.error("Unexpected transport error: %s", to_log_message(exc))
            self.offline_state = True
            raise

    async def ensure_connected(self) -> None:
        async with self._lock:
            if self._is_connected():
                return
            await self._reset_connection()
            await self._connect()

    async def close(self) -> None:
        async with self._lock:
            await self._reset_connection()
            self.offline_state = True

    async def _handle_timeout(self, attempt: int, exc: Exception) -> None:
        log_transport_retry(
            logger=_LOGGER,
            operation="timeout",
            attempt=attempt,
            max_attempts=self.max_retries,
            exc=exc,
            base_backoff=self.base_backoff,
        )
        await self._mark_offline_and_reset()
        await self._apply_backoff(attempt)

    async def _handle_transient(self, attempt: int, exc: Exception) -> None:
        log_transport_retry(
            logger=_LOGGER,
            operation="transient",
            attempt=attempt,
            max_attempts=self.max_retries,
            exc=exc,
            base_backoff=self.base_backoff,
        )
        await self._mark_offline_and_reset()
        await self._apply_backoff(attempt)

    async def _apply_backoff(self, attempt: int) -> None:
        await apply_transport_backoff(
            attempt=attempt,
            base_backoff=self.base_backoff,
            max_backoff=self.max_backoff,
        )

    @abstractmethod
    def _is_connected(self) -> bool: ...

    @abstractmethod
    async def _connect(self) -> None: ...

    @abstractmethod
    async def _reset_connection(self) -> None: ...
