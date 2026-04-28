"""Raw RTU-over-TCP transport implementation."""

from __future__ import annotations

import asyncio
from typing import Any

from .modbus_exceptions import ConnectionException, ModbusException, ModbusIOException
from .modbus_transport_base import (
    _MAX_READ_REGISTERS,
    _MAX_SLAVE_ID,
    _MAX_WRITE_REGISTERS,
    _MIN_SLAVE_ID,
    BaseModbusTransport,
    RawModbusResponse,
    RawModbusWriteResponse,
    _append_crc,
    _crc16,
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
    def _validate_slave_id(slave_id: int) -> None:
        if not (_MIN_SLAVE_ID <= slave_id <= _MAX_SLAVE_ID):
            raise ModbusIOException(
                f"Invalid slave_id={slave_id}; expected {_MIN_SLAVE_ID}-{_MAX_SLAVE_ID}"
            )

    @staticmethod
    def _validate_read_count(count: int) -> None:
        if not (1 <= count <= _MAX_READ_REGISTERS):
            raise ModbusIOException(f"Invalid read count={count}; expected 1-{_MAX_READ_REGISTERS}")

    @staticmethod
    def _validate_write_count(qty: int) -> None:
        if not (1 <= qty <= _MAX_WRITE_REGISTERS):
            raise ModbusIOException(
                f"Invalid write quantity={qty}; expected 1-{_MAX_WRITE_REGISTERS}"
            )

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

    @staticmethod
    def _decode_register_words(data: bytes, *, count: int) -> list[int]:
        expected_bytes = count * 2
        if len(data) != expected_bytes:
            raise ModbusIOException("Invalid byte count in RTU response")
        return [int.from_bytes(data[i : i + 2], "big") for i in range(0, len(data), 2)]

    @staticmethod
    def _validate_write_echo(response: bytes, *, address: int, expected_value: int) -> None:
        if len(response) != 4:
            raise ModbusIOException("Invalid write response length")
        resp_addr = (response[0] << 8) | response[1]
        resp_value = (response[2] << 8) | response[3]
        if resp_addr != address or resp_value != expected_value:
            raise ModbusIOException("Write response does not match request")

    async def _read_registers_common(
        self, *, slave_id: int, address: int, count: int, function: int
    ) -> RawModbusResponse:
        frame = self._build_read_frame(slave_id, function, address, count)
        data = await self._send_frame(frame, slave_id, function)
        return RawModbusResponse(self._decode_register_words(data, count=count))

    async def read_input_registers(
        self,
        slave_id: int,
        address: int,
        *,
        count: int,
        attempt: int = 1,
    ) -> Any:
        _ = attempt
        self._validate_slave_id(slave_id)
        self._validate_read_count(count)

        async def _invoke() -> RawModbusResponse:
            return await self._read_registers_common(
                slave_id=slave_id,
                address=address,
                count=count,
                function=4,
            )

        return await self._execute(_invoke, ensure_connection=True)

    async def read_holding_registers(
        self,
        slave_id: int,
        address: int,
        *,
        count: int,
        attempt: int = 1,
    ) -> Any:
        _ = attempt
        self._validate_slave_id(slave_id)
        self._validate_read_count(count)

        async def _invoke() -> RawModbusResponse:
            return await self._read_registers_common(
                slave_id=slave_id,
                address=address,
                count=count,
                function=3,
            )

        return await self._execute(_invoke, ensure_connection=True)

    async def write_register(
        self,
        slave_id: int,
        address: int,
        *,
        value: int,
        attempt: int = 1,
    ) -> Any:
        _ = attempt
        self._validate_slave_id(slave_id)

        async def _invoke() -> RawModbusWriteResponse:
            frame = self._build_write_single_frame(slave_id, address, value)
            response = await self._send_frame(frame, slave_id, 6)
            self._validate_write_echo(response, address=address, expected_value=(value & 0xFFFF))
            return RawModbusWriteResponse()

        return await self._execute(_invoke, ensure_connection=True)

    async def write_registers(
        self,
        slave_id: int,
        address: int,
        *,
        values: list[int],
        attempt: int = 1,
    ) -> Any:
        _ = attempt
        self._validate_slave_id(slave_id)
        self._validate_write_count(len(values))

        async def _invoke() -> RawModbusWriteResponse:
            frame = self._build_write_multiple_frame(slave_id, address, values)
            response = await self._send_frame(frame, slave_id, 16)
            self._validate_write_echo(response, address=address, expected_value=len(values))
            return RawModbusWriteResponse()

        return await self._execute(_invoke, ensure_connection=True)


__all__ = ["RawRtuOverTcpTransport"]
