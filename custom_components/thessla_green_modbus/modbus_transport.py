"""Transport abstractions for Modbus communication."""

from __future__ import annotations

import asyncio
import logging
from abc import ABC, abstractmethod
from typing import Any

from pymodbus.client import AsyncModbusTcpClient

from .modbus_exceptions import ConnectionException, ModbusException, ModbusIOException
from .modbus_helpers import _call_modbus
from .modbus_retry_policy import RetryPolicy

_LOGGER = logging.getLogger(__name__)


class BaseModbusTransport(ABC):
    """Base interface for Modbus transports."""

    def __init__(
        self,
        *,
        retry_policy: RetryPolicy | None,
        timeout: float,
        offline_state: bool = False,
    ) -> None:
        self.retry_policy = retry_policy or RetryPolicy()
        self.timeout = float(timeout)
        self.offline_state = offline_state
        self._lock = asyncio.Lock()

    @property
    def offline(self) -> bool:
        """Return whether the transport is offline."""

        return self.offline_state

    async def call(self, func: Any, slave_id: int, *args: Any, **kwargs: Any) -> Any:
        """Call a Modbus function with connection management."""

        await self.ensure_connected()
        try:
            response = await _call_modbus(
                func,
                slave_id,
                *args,
                attempt=1,
                max_attempts=self.retry_policy.max_attempts,
                timeout=self.timeout,
                backoff=0.0,
                apply_backoff=False,
                **kwargs,
            )
            self.offline_state = False
            return response
        except (asyncio.TimeoutError, TimeoutError) as exc:
            self.offline_state = True
            await self._reset_connection()
            _LOGGER.warning("Modbus call timed out: %s", exc)
            raise
        except ModbusIOException as exc:
            self.offline_state = True
            await self._reset_connection()
            _LOGGER.warning("Modbus I/O error: %s", exc)
            raise
        except (ConnectionException, OSError) as exc:
            self.offline_state = True
            await self._reset_connection()
            _LOGGER.warning("Modbus transport error: %s", exc)
            raise
        except ModbusException as exc:
            _LOGGER.error("Modbus protocol error: %s", exc)
            self.offline_state = True
            raise
        except Exception as exc:  # pragma: no cover - unexpected
            _LOGGER.error("Unexpected transport error: %s", exc)
            self.offline_state = True
            raise

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
        retry_policy: RetryPolicy | None,
        timeout: float,
        offline_state: bool = False,
    ) -> None:
        super().__init__(
            retry_policy=retry_policy,
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
