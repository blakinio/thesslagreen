"""RTU serial transport implementation."""

from __future__ import annotations

import logging
from typing import Any

try:
    from pymodbus.client import AsyncModbusSerialClient as _AsyncModbusSerialClient
except (ImportError, AttributeError) as serial_import_err:  # pragma: no cover
    _AsyncModbusSerialClient = None
    SERIAL_IMPORT_ERROR: Exception | None = serial_import_err
else:  # pragma: no cover
    SERIAL_IMPORT_ERROR = None

from ..modbus.client_close import async_maybe_await_close
from ..modbus_exceptions import ConnectionException
from .tcp import _ClientBackedTransport

_LOGGER = logging.getLogger(__name__)


class RtuModbusTransport(_ClientBackedTransport):
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
        self.client: Any | None = None

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
        await self._connect_client(endpoint=self.serial_port)
        _LOGGER.debug("RTU Modbus connection established on %s", self.serial_port)

    async def _reset_connection(self) -> None:
        if self.client is None:
            return
        try:
            await async_maybe_await_close(self.client)
        finally:
            self.client = None


__all__ = [
    "SERIAL_IMPORT_ERROR",
    "RtuModbusTransport",
    "_AsyncModbusSerialClient",
]
