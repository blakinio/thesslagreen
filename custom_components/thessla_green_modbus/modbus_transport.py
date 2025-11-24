"""Transport abstractions for Modbus communication."""

from __future__ import annotations

import asyncio
import logging
from abc import ABC, abstractmethod
from typing import Any

from pymodbus.client import AsyncModbusTcpClient

from .modbus_exceptions import ConnectionException, ModbusException, ModbusIOException
from .modbus_helpers import _call_modbus, _calculate_backoff_delay

_LOGGER = logging.getLogger(__name__)


class BaseModbusTransport(ABC):
    """Base interface for Modbus transports."""

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
        """Return whether the transport is offline."""

        return self.offline_state

    async def call(self, func: Any, slave_id: int, *args: Any, **kwargs: Any) -> Any:
        """Call a Modbus function with connection management and retries."""

        last_exc: Exception | None = None
        for attempt in range(1, self.max_retries + 1):
            try:
                await self.ensure_connected()
                response = await _call_modbus(
                    func,
                    slave_id,
                    *args,
                    attempt=attempt,
                    max_attempts=self.max_retries,
                    timeout=self.timeout,
                    backoff=0.0,
                    apply_backoff=False,
                    **kwargs,
                )
                self.offline_state = False
                return response
            except (asyncio.TimeoutError, TimeoutError) as exc:
                last_exc = exc
                await self._handle_timeout(attempt, exc)
            except ModbusIOException as exc:
                last_exc = exc
                await self._handle_transient(attempt, exc)
            except (ConnectionException, OSError) as exc:
                last_exc = exc
                await self._handle_transient(attempt, exc)
            except ModbusException as exc:
                _LOGGER.error("Permanent Modbus error: %s", exc)
                self.offline_state = True
                raise
            except Exception as exc:  # pragma: no cover - unexpected
                last_exc = exc
                _LOGGER.error("Unexpected transport error: %s", exc)
                self.offline_state = True
                raise

        if last_exc:
            raise last_exc
        raise ConnectionException("Modbus call failed without raising an error")

    async def ensure_connected(self) -> None:
        """Ensure the underlying transport is connected."""

        async with self._lock:
            if self._is_connected():
                return
            await self._reset_connection()
            await self._connect()

    async def close(self) -> None:
        """Close the transport."""

        async with self._lock:
            await self._reset_connection()
            self.offline_state = True

    async def _handle_timeout(self, attempt: int, exc: Exception) -> None:
        """Handle timeout errors with reconnection and backoff."""

        _LOGGER.warning("Modbus call timed out on attempt %s/%s: %s", attempt, self.max_retries, exc)
        self.offline_state = True
        await self._reset_connection()
        await self._apply_backoff(attempt)

    async def _handle_transient(self, attempt: int, exc: Exception) -> None:
        """Handle transient transport errors."""

        _LOGGER.warning(
            "Transient Modbus transport error on attempt %s/%s: %s",
            attempt,
            self.max_retries,
            exc,
        )
        self.offline_state = True
        await self._reset_connection()
        await self._apply_backoff(attempt)

    async def _apply_backoff(self, attempt: int) -> None:
        """Sleep for the calculated backoff duration respecting the maximum."""

        delay = _calculate_backoff_delay(base=self.base_backoff, attempt=attempt + 1, jitter=None)
        if self.max_backoff:
            delay = min(delay, self.max_backoff)
        if delay > 0:
            await asyncio.sleep(delay)

    @abstractmethod
    def _is_connected(self) -> bool:
        """Return whether the underlying client is connected."""

    @abstractmethod
    async def _connect(self) -> None:
        """Connect the underlying transport."""

    @abstractmethod
    async def _reset_connection(self) -> None:
        """Reset the underlying connection."""


class TcpModbusTransport(BaseModbusTransport):
    """TCP Modbus transport implementation."""

    def __init__(
        self,
        *,
        host: str,
        port: int,
        max_retries: int,
        base_backoff: float,
        max_backoff: float,
        timeout: float,
        offline_state: bool = False,
    ) -> None:
        super().__init__(
            max_retries=max_retries,
            base_backoff=base_backoff,
            max_backoff=max_backoff,
            timeout=timeout,
            offline_state=offline_state,
        )
        self.host = host
        self.port = port
        self.client: AsyncModbusTcpClient | None = None

    def _is_connected(self) -> bool:
        return bool(self.client and getattr(self.client, "connected", False))

    async def _connect(self) -> None:
        self.client = AsyncModbusTcpClient(self.host, port=self.port, timeout=self.timeout)
        connected = await self.client.connect()
        if not connected:
            self.offline_state = True
            raise ConnectionException(f"Could not connect to {self.host}:{self.port}")
        _LOGGER.debug("TCP Modbus connection established to %s:%s", self.host, self.port)
        self.offline_state = False

    async def _reset_connection(self) -> None:
        if self.client is None:
            return
        try:
            await self.client.close()
        finally:
            self.client = None


class RtuModbusTransport(BaseModbusTransport):
    """Placeholder RTU transport for future USB/serial support."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.client = None

    def _is_connected(self) -> bool:  # pragma: no cover - placeholder
        return False

    async def _connect(self) -> None:  # pragma: no cover - placeholder
        raise ConnectionException("RTU transport not yet implemented")

    async def _reset_connection(self) -> None:  # pragma: no cover - placeholder
        self.client = None
