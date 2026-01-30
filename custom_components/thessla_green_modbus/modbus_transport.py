"""Transport abstractions for Modbus communication."""

from __future__ import annotations

import asyncio
import logging
from abc import ABC, abstractmethod
from typing import Any

from pymodbus.client import AsyncModbusTcpClient

try:  # pragma: no cover - serial extras optional at runtime
    from pymodbus.client import AsyncModbusSerialClient as _AsyncModbusSerialClient
except (ImportError, AttributeError) as serial_import_err:  # pragma: no cover
    _AsyncModbusSerialClient = None
    SERIAL_IMPORT_ERROR: Exception | None = serial_import_err
else:  # pragma: no cover - executed when serial client available
    SERIAL_IMPORT_ERROR = None

from .modbus_exceptions import ConnectionException, ModbusException, ModbusIOException
from .modbus_helpers import _calculate_backoff_delay, _call_modbus, async_close_client

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

    async def call(
        self,
        func: Any,
        slave_id: int,
        *args: Any,
        attempt: int = 1,
        max_attempts: int | None = None,
        backoff: float | None = None,
        backoff_jitter: float | tuple[float, float] | None = None,
        apply_backoff: bool = True,
        **kwargs: Any,
    ) -> Any:
        """Call a Modbus function with connection management and retries."""

        try:
            await self.ensure_connected()
            response = await _call_modbus(
                func,
                slave_id,
                *args,
                attempt=attempt,
                max_attempts=max_attempts or self.max_retries,
                timeout=self.timeout,
                backoff=backoff if backoff is not None else self.base_backoff,
                backoff_jitter=backoff_jitter,
                apply_backoff=apply_backoff,
                **kwargs,
            )
            self.offline_state = False
            return response
        except TimeoutError:
            self.offline_state = True
            await self._reset_connection()
            raise
        except ModbusIOException:
            self.offline_state = True
            await self._reset_connection()
            raise
        except (ConnectionException, OSError):
            self.offline_state = True
            await self._reset_connection()
            raise
        except ModbusException as exc:
            _LOGGER.error("Permanent Modbus error: %s", exc)
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

    async def _handle_timeout(self, attempt: int, exc: Exception) -> None:
        """Handle timeout errors with reconnection and backoff."""

        _LOGGER.warning(
            "Modbus call timed out on attempt %s/%s: %s",
            attempt,
            self.max_retries,
            exc,
        )
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
            await async_close_client(self.client)
        finally:
            self.client = None


class RtuModbusTransport(BaseModbusTransport):
    """RTU Modbus transport implementation using async serial client."""

    def __init__(
        self,
        *,
        serial_port: str,
        baudrate: int,
        parity: str,
        stopbits: int,
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
        self.serial_port = serial_port
        self.baudrate = baudrate
        self.parity = parity
        self.stopbits = stopbits
        self.client: _AsyncModbusSerialClient | None = None

    def _is_connected(self) -> bool:
        return bool(self.client and getattr(self.client, "connected", False))

    async def _connect(self) -> None:
        if _AsyncModbusSerialClient is None:
            message = "Modbus serial client is unavailable. Install pymodbus with serial support."
            if SERIAL_IMPORT_ERROR is not None:
                message = f"{message} ({SERIAL_IMPORT_ERROR})"
            raise ConnectionException(message)
        if not self.serial_port:
            raise ConnectionException("Serial port not configured for RTU transport")
        self.client = _AsyncModbusSerialClient(
            method="rtu",
            port=self.serial_port,
            baudrate=self.baudrate,
            parity=self.parity,
            stopbits=self.stopbits,
            timeout=self.timeout,
        )
        connected = await self.client.connect()
        if not connected:
            self.offline_state = True
            raise ConnectionException(f"Could not connect to {self.serial_port}")
        _LOGGER.debug("RTU Modbus connection established on %s", self.serial_port)
        self.offline_state = False

    async def _reset_connection(self) -> None:
        if self.client is None:
            return
        try:
            await async_close_client(self.client)
        finally:
            self.client = None
