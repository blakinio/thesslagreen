"""Transport abstractions for Modbus communication."""

from __future__ import annotations

import asyncio
import logging
from abc import ABC, abstractmethod
from typing import Any

try:  # pragma: no cover
    from pymodbus.client import AsyncModbusSerialClient as _AsyncModbusSerialClient
except (ImportError, AttributeError) as serial_import_err:  # pragma: no cover
    _AsyncModbusSerialClient = None
    SERIAL_IMPORT_ERROR: Exception | None = serial_import_err
else:  # pragma: no cover
    SERIAL_IMPORT_ERROR = None

from ._transport_retry import apply_transport_backoff, log_transport_retry
from .error_contract import classify_error
from .error_policy import to_log_message
from .modbus_exceptions import ConnectionException, ModbusException, ModbusIOException
from .modbus_helpers import (
    _call_modbus,
)

_LOGGER = logging.getLogger(__name__)
_MIN_SLAVE_ID = 1
_MAX_SLAVE_ID = 247
_MAX_READ_REGISTERS = 125
_MAX_WRITE_REGISTERS = 123


def classify_transport_error(exc: BaseException) -> tuple[str, str]:
    """Expose normalized retry classification for transport layer tests."""

    contract = classify_error(exc)
    return contract.kind, contract.reason


def _crc16(data: bytes) -> int:
    """Return Modbus RTU CRC16 for the provided payload."""

    crc = 0xFFFF
    for byte in data:
        crc ^= byte
        for _ in range(8):
            if crc & 1:
                crc = (crc >> 1) ^ 0xA001
            else:
                crc >>= 1
    return crc & 0xFFFF


def _append_crc(data: bytes) -> bytes:
    """Append Modbus RTU CRC16 in little-endian order."""

    return data + _crc16(data).to_bytes(2, "little")


class RawModbusResponse:
    """Minimal Modbus response container for raw RTU-over-TCP reads."""

    def __init__(self, registers: list[int] | None = None) -> None:
        self.registers = registers or []

    def isError(self) -> bool:
        return False


class RawModbusWriteResponse:
    """Minimal Modbus response container for raw RTU-over-TCP writes."""

    def isError(self) -> bool:
        return False


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

    def is_connected(self) -> bool:
        """Return whether the transport is currently connected."""

        return self._is_connected()

    async def _execute(self, func: Any, *, ensure_connection: bool = False) -> Any:
        """Execute a transport operation with shared error handling."""

        try:
            if ensure_connection:
                await self.ensure_connected()
            response = await func()
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
        except asyncio.CancelledError:
            self.offline_state = True
            try:
                await self._reset_connection()
            except (ConnectionException, ModbusException, OSError, RuntimeError) as exc:
                _LOGGER.debug("Reset connection failed during CancelledError handling: %s", exc)
            raise
        except ModbusException as exc:
            kind, reason = classify_transport_error(exc)
            _LOGGER.error("Permanent Modbus error (%s/%s): %s", kind, reason, to_log_message(exc))
            self.offline_state = True
            raise
        except (
            AttributeError,
            RuntimeError,
            TypeError,
            ValueError,
        ) as exc:  # pragma: no cover - unexpected
            _LOGGER.error("Unexpected transport error: %s", to_log_message(exc))
            self.offline_state = True
            raise

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

        async def _invoke() -> Any:
            return await _call_modbus(
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

        return await self._execute(_invoke, ensure_connection=True)

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

        log_transport_retry(
            logger=_LOGGER,
            operation="timeout",
            attempt=attempt,
            max_attempts=self.max_retries,
            exc=exc,
            base_backoff=self.base_backoff,
        )
        self.offline_state = True
        await self._reset_connection()
        await self._apply_backoff(attempt)

    async def _handle_transient(self, attempt: int, exc: Exception) -> None:
        """Handle transient transport errors."""

        log_transport_retry(
            logger=_LOGGER,
            operation="transient",
            attempt=attempt,
            max_attempts=self.max_retries,
            exc=exc,
            base_backoff=self.base_backoff,
        )
        self.offline_state = True
        await self._reset_connection()
        await self._apply_backoff(attempt)

    async def _apply_backoff(self, attempt: int) -> None:
        """Sleep for the calculated backoff duration respecting the maximum."""
        await apply_transport_backoff(
            attempt=attempt, base_backoff=self.base_backoff, max_backoff=self.max_backoff
        )

    @abstractmethod
    def _is_connected(self) -> bool:
        """Return whether the underlying client is connected."""

    @abstractmethod
    async def _connect(self) -> None:
        """Connect the underlying transport."""

    @abstractmethod
    async def _reset_connection(self) -> None:
        """Reset the underlying connection."""

    @abstractmethod
    async def read_input_registers(
        self,
        slave_id: int,
        address: int,
        *,
        count: int,
        attempt: int = 1,
    ) -> Any:
        """Read input registers from the device."""

    @abstractmethod
    async def read_holding_registers(
        self,
        slave_id: int,
        address: int,
        *,
        count: int,
        attempt: int = 1,
    ) -> Any:
        """Read holding registers from the device."""

    @abstractmethod
    async def write_register(
        self,
        slave_id: int,
        address: int,
        *,
        value: int,
        attempt: int = 1,
    ) -> Any:
        """Write a single holding register."""

    @abstractmethod
    async def write_registers(
        self,
        slave_id: int,
        address: int,
        *,
        values: list[int],
        attempt: int = 1,
    ) -> Any:
        """Write multiple holding registers."""



__all__ = [
    "_MAX_READ_REGISTERS",
    "_MAX_SLAVE_ID",
    "_MAX_WRITE_REGISTERS",
    "_MIN_SLAVE_ID",
    "BaseModbusTransport",
    "RawModbusResponse",
    "RawModbusWriteResponse",
    "_append_crc",
    "_crc16",
    "classify_transport_error",
]
