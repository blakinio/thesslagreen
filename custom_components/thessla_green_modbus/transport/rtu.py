"""RTU transport implementation."""

from __future__ import annotations

import inspect
from typing import Any

try:
    from pymodbus.client import AsyncModbusSerialClient as _AsyncModbusSerialClient
except (ImportError, AttributeError) as serial_import_err:  # pragma: no cover
    _AsyncModbusSerialClient = None
    SERIAL_IMPORT_ERROR: Exception | None = serial_import_err
else:  # pragma: no cover
    SERIAL_IMPORT_ERROR = None

from ..modbus_exceptions import ConnectionException
from ..modbus_helpers import async_maybe_await_close
from .base import BaseModbusTransport


class RtuModbusTransport(BaseModbusTransport):
    def __init__(self, *, serial_port: str, baudrate: int, parity: str, stopbits: int, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.serial_port = serial_port
        self.baudrate = baudrate
        self.parity = parity
        self.stopbits = stopbits
        self.client: Any | None = None

    def _is_connected(self) -> bool:
        return bool(self.client and getattr(self.client, "connected", False))

    async def _connect(self) -> None:
        if _AsyncModbusSerialClient is None:
            msg = "Modbus serial client is unavailable."
            if SERIAL_IMPORT_ERROR is not None:
                msg = f"{msg} ({SERIAL_IMPORT_ERROR})"
            raise ConnectionException(msg)
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
        connect_method = getattr(self.client, "connect", None)
        if callable(connect_method):
            connected = connect_method()
            if inspect.isawaitable(connected):
                connected = await connected
        else:
            connected = True
            self.client.connected = True
        if not connected:
            self.offline_state = True
            raise ConnectionException(f"Could not connect to {self.serial_port}")
        self.offline_state = False

    async def _reset_connection(self) -> None:
        if self.client is None:
            return
        try:
            await async_maybe_await_close(self.client)
        finally:
            self.client = None
