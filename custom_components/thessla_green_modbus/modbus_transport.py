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

from .const import CONNECTION_TYPE_TCP, CONNECTION_TYPE_TCP_RTU
from .modbus_exceptions import ConnectionException, ModbusException, ModbusIOException
from .modbus_helpers import (
    _calculate_backoff_delay,
    _call_modbus,
    async_maybe_await_close,
    get_rtu_framer,
)

_LOGGER = logging.getLogger(__name__)


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

    def isError(self) -> bool:  # noqa: N802 - mimic pymodbus API
        return False


class RawModbusWriteResponse:
    """Minimal Modbus response container for raw RTU-over-TCP writes."""

    def isError(self) -> bool:  # noqa: N802 - mimic pymodbus API
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

    async def _execute(self, func: Any) -> Any:
        """Execute a transport operation with shared error handling."""

        try:
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
        except ModbusException as exc:
            _LOGGER.error("Permanent Modbus error: %s", exc)
            self.offline_state = True
            raise
        except Exception as exc:  # pragma: no cover - unexpected
            _LOGGER.error("Unexpected transport error: %s", exc)
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

        return await self._execute(_invoke)

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


class TcpModbusTransport(BaseModbusTransport):
    """TCP Modbus transport implementation."""

    def __init__(
        self,
        *,
        host: str,
        port: int,
        connection_type: str = CONNECTION_TYPE_TCP,
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
        self.connection_type = connection_type
        self.client: AsyncModbusTcpClient | None = None

    def _is_connected(self) -> bool:
        return bool(self.client and getattr(self.client, "connected", False))

    def _build_tcp_client(self, *, framer: Any | None = None) -> AsyncModbusTcpClient:
        from pymodbus.client import AsyncModbusTcpClient as AsyncTcpClient

        common_kwargs: dict[str, Any] = {
            "port": self.port,
            "timeout": self.timeout,
            "reconnect_delay": 1,
            "reconnect_delay_max": 300,
            "retries": self.max_retries,
        }
        if framer is not None:
            common_kwargs["framer"] = framer

        try:
            return AsyncTcpClient(self.host, **common_kwargs)
        except TypeError as exc:
            _LOGGER.debug(
                "AsyncModbusTcpClient does not accept reconnect parameters: %s",
                exc,
            )
            fallback_kwargs = {k: v for k, v in common_kwargs.items() if k in {"port", "timeout"}}
            if framer is not None:
                fallback_kwargs["framer"] = framer
            return AsyncTcpClient(self.host, **fallback_kwargs)

    async def _connect(self) -> None:
        if self.connection_type == CONNECTION_TYPE_TCP_RTU:
            framer = get_rtu_framer()
            if framer is None:
                message = (
                    "RTU over TCP requires pymodbus with RTU framer support "
                    "(FramerType.RTU or ModbusRtuFramer)."
                )
                _LOGGER.error(message)
                raise ConnectionException(message)
            _LOGGER.info(
                "Connecting Modbus TCP RTU to %s:%s (timeout=%s)",
                self.host,
                self.port,
                self.timeout,
            )
            try:
                self.client = self._build_tcp_client(framer=framer)
            except TypeError as exc:
                message = (
                    "RTU over TCP is not supported by the installed pymodbus client. "
                    "Please upgrade pymodbus."
                )
                _LOGGER.error("%s (%s)", message, exc)
                raise ConnectionException(message) from exc
        else:
            _LOGGER.info(
                "Connecting Modbus TCP to %s:%s (timeout=%s)",
                self.host,
                self.port,
                self.timeout,
            )
            self.client = self._build_tcp_client()
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
            await async_maybe_await_close(self.client)
        finally:
            self.client = None

    async def read_input_registers(
        self,
        slave_id: int,
        address: int,
        *,
        count: int,
        attempt: int = 1,
    ) -> Any:
        if self.client is None:
            raise ConnectionException("Modbus client is not connected")
        return await self.call(
            self.client.read_input_registers,
            slave_id,
            address,
            count=count,
            attempt=attempt,
        )

    async def read_holding_registers(
        self,
        slave_id: int,
        address: int,
        *,
        count: int,
        attempt: int = 1,
    ) -> Any:
        if self.client is None:
            raise ConnectionException("Modbus client is not connected")
        return await self.call(
            self.client.read_holding_registers,
            slave_id,
            address,
            count=count,
            attempt=attempt,
        )

    async def write_register(
        self,
        slave_id: int,
        address: int,
        *,
        value: int,
        attempt: int = 1,
    ) -> Any:
        if self.client is None:
            raise ConnectionException("Modbus client is not connected")
        return await self.call(
            self.client.write_register,
            slave_id,
            address,
            value=value,
            attempt=attempt,
        )

    async def write_registers(
        self,
        slave_id: int,
        address: int,
        *,
        values: list[int],
        attempt: int = 1,
    ) -> Any:
        if self.client is None:
            raise ConnectionException("Modbus client is not connected")
        return await self.call(
            self.client.write_registers,
            slave_id,
            address,
            values=values,
            attempt=attempt,
        )


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
            await async_maybe_await_close(self.client)
        finally:
            self.client = None

    async def read_input_registers(
        self,
        slave_id: int,
        address: int,
        *,
        count: int,
        attempt: int = 1,
    ) -> Any:
        if self.client is None:
            raise ConnectionException("Modbus serial client is not connected")
        return await self.call(
            self.client.read_input_registers,
            slave_id,
            address,
            count=count,
            attempt=attempt,
        )

    async def read_holding_registers(
        self,
        slave_id: int,
        address: int,
        *,
        count: int,
        attempt: int = 1,
    ) -> Any:
        if self.client is None:
            raise ConnectionException("Modbus serial client is not connected")
        return await self.call(
            self.client.read_holding_registers,
            slave_id,
            address,
            count=count,
            attempt=attempt,
        )

    async def write_register(
        self,
        slave_id: int,
        address: int,
        *,
        value: int,
        attempt: int = 1,
    ) -> Any:
        if self.client is None:
            raise ConnectionException("Modbus serial client is not connected")
        return await self.call(
            self.client.write_register,
            slave_id,
            address,
            value=value,
            attempt=attempt,
        )

    async def write_registers(
        self,
        slave_id: int,
        address: int,
        *,
        values: list[int],
        attempt: int = 1,
    ) -> Any:
        if self.client is None:
            raise ConnectionException("Modbus serial client is not connected")
        return await self.call(
            self.client.write_registers,
            slave_id,
            address,
            values=values,
            attempt=attempt,
        )


class RawRtuOverTcpTransport(BaseModbusTransport):
    """RTU-over-TCP transport that sends raw Modbus RTU frames over TCP."""

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
        self._reader: asyncio.StreamReader | None = None
        self._writer: asyncio.StreamWriter | None = None
        self._request_lock = asyncio.Lock()

    def _is_connected(self) -> bool:
        return bool(self._writer and not self._writer.is_closing())

    async def _connect(self) -> None:
        try:
            self._reader, self._writer = await asyncio.wait_for(
                asyncio.open_connection(self.host, self.port),
                timeout=self.timeout,
            )
        except TimeoutError as exc:
            raise TimeoutError(f"Timed out connecting to {self.host}:{self.port}") from exc
        except OSError as exc:
            raise ConnectionException(f"Could not connect to {self.host}:{self.port}") from exc

    async def _reset_connection(self) -> None:
        if self._writer is None:
            self._reader = None
            return
        try:
            self._writer.close()
            wait_closed = getattr(self._writer, "wait_closed", None)
            if callable(wait_closed):
                await wait_closed()
        finally:
            self._reader = None
            self._writer = None

    async def _read_exactly(self, size: int) -> bytes:
        if self._reader is None:
            raise ConnectionException("RTU-over-TCP socket not connected")
        try:
            return await asyncio.wait_for(self._reader.readexactly(size), timeout=self.timeout)
        except asyncio.IncompleteReadError as exc:
            raise ModbusIOException("Incomplete RTU response") from exc
        except TimeoutError as exc:
            raise TimeoutError("Timed out waiting for RTU response") from exc

    @staticmethod
    def _validate_crc(payload: bytes, crc_bytes: bytes) -> None:
        expected = _crc16(payload).to_bytes(2, "little")
        if crc_bytes != expected:
            raise ModbusIOException("CRC mismatch in RTU response")

    @staticmethod
    def _build_read_frame(slave_id: int, function: int, address: int, count: int) -> bytes:
        payload = bytes(
            [
                slave_id & 0xFF,
                function & 0xFF,
                (address >> 8) & 0xFF,
                address & 0xFF,
                (count >> 8) & 0xFF,
                count & 0xFF,
            ]
        )
        return _append_crc(payload)

    @staticmethod
    def _build_write_single_frame(slave_id: int, address: int, value: int) -> bytes:
        payload = bytes(
            [
                slave_id & 0xFF,
                6,
                (address >> 8) & 0xFF,
                address & 0xFF,
                (value >> 8) & 0xFF,
                value & 0xFF,
            ]
        )
        return _append_crc(payload)

    @staticmethod
    def _build_write_multiple_frame(slave_id: int, address: int, values: list[int]) -> bytes:
        qty = len(values)
        payload = bytearray(
            [
                slave_id & 0xFF,
                16,
                (address >> 8) & 0xFF,
                address & 0xFF,
                (qty >> 8) & 0xFF,
                qty & 0xFF,
                qty * 2,
            ]
        )
        for value in values:
            payload.extend([(value >> 8) & 0xFF, value & 0xFF])
        return _append_crc(bytes(payload))

    async def _read_response(self, slave_id: int, function: int) -> bytes:
        header = await self._read_exactly(2)
        resp_slave, resp_func = header

        if resp_slave != (slave_id & 0xFF):
            raise ModbusIOException("Unexpected slave ID in RTU response")

        if resp_func & 0x80:
            exception_code = await self._read_exactly(1)
            crc_bytes = await self._read_exactly(2)
            payload = header + exception_code
            self._validate_crc(payload, crc_bytes)
            raise ModbusException(f"Modbus exception {exception_code[0]} for function {resp_func}")

        if resp_func != (function & 0xFF):
            raise ModbusIOException("Unexpected function code in RTU response")

        if function in (3, 4):
            byte_count_raw = await self._read_exactly(1)
            byte_count = byte_count_raw[0]
            data = await self._read_exactly(byte_count)
            crc_bytes = await self._read_exactly(2)
            payload = header + byte_count_raw + data
            self._validate_crc(payload, crc_bytes)
            return data

        body = await self._read_exactly(4)
        crc_bytes = await self._read_exactly(2)
        payload = header + body
        self._validate_crc(payload, crc_bytes)
        return body

    async def _send_frame(self, frame: bytes, slave_id: int, function: int) -> bytes:
        async with self._request_lock:
            if self._writer is None:
                raise ConnectionException("RTU-over-TCP socket not connected")
            self._writer.write(frame)
            await self._writer.drain()
            return await self._read_response(slave_id, function)

    async def read_input_registers(
        self,
        slave_id: int,
        address: int,
        *,
        count: int,
        attempt: int = 1,
    ) -> Any:
        _ = attempt

        async def _invoke() -> RawModbusResponse:
            frame = self._build_read_frame(slave_id, 4, address, count)
            data = await self._send_frame(frame, slave_id, 4)
            if len(data) % 2:
                raise ModbusIOException("Invalid byte count in RTU response")
            registers = [
                int.from_bytes(data[i : i + 2], "big") for i in range(0, len(data), 2)
            ]
            return RawModbusResponse(registers)

        return await self._execute(_invoke)

    async def read_holding_registers(
        self,
        slave_id: int,
        address: int,
        *,
        count: int,
        attempt: int = 1,
    ) -> Any:
        _ = attempt

        async def _invoke() -> RawModbusResponse:
            frame = self._build_read_frame(slave_id, 3, address, count)
            data = await self._send_frame(frame, slave_id, 3)
            if len(data) % 2:
                raise ModbusIOException("Invalid byte count in RTU response")
            registers = [
                int.from_bytes(data[i : i + 2], "big") for i in range(0, len(data), 2)
            ]
            return RawModbusResponse(registers)

        return await self._execute(_invoke)

    async def write_register(
        self,
        slave_id: int,
        address: int,
        *,
        value: int,
        attempt: int = 1,
    ) -> Any:
        _ = attempt

        async def _invoke() -> RawModbusWriteResponse:
            frame = self._build_write_single_frame(slave_id, address, value)
            response = await self._send_frame(frame, slave_id, 6)
            if len(response) != 4:
                raise ModbusIOException("Invalid write response length")
            resp_addr = (response[0] << 8) | response[1]
            resp_value = (response[2] << 8) | response[3]
            if resp_addr != address or resp_value != (value & 0xFFFF):
                raise ModbusIOException("Write response does not match request")
            return RawModbusWriteResponse()

        return await self._execute(_invoke)

    async def write_registers(
        self,
        slave_id: int,
        address: int,
        *,
        values: list[int],
        attempt: int = 1,
    ) -> Any:
        _ = attempt

        async def _invoke() -> RawModbusWriteResponse:
            frame = self._build_write_multiple_frame(slave_id, address, values)
            response = await self._send_frame(frame, slave_id, 16)
            if len(response) != 4:
                raise ModbusIOException("Invalid write response length")
            resp_addr = (response[0] << 8) | response[1]
            resp_qty = (response[2] << 8) | response[3]
            if resp_addr != address or resp_qty != len(values):
                raise ModbusIOException("Write response does not match request")
            return RawModbusWriteResponse()

        return await self._execute(_invoke)
