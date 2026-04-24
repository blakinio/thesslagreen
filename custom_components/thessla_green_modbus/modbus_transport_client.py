"""Client-backed Modbus transport implementations."""

from __future__ import annotations

import inspect
import logging
import sys
from typing import Any

from pymodbus.client import AsyncModbusTcpClient

from .const import CONNECTION_TYPE_TCP, CONNECTION_TYPE_TCP_RTU
from .modbus_exceptions import ConnectionException
from .modbus_helpers import async_maybe_await_close, get_rtu_framer
from .modbus_transport_base import BaseModbusTransport

_LOGGER = logging.getLogger(__name__)

try:  # pragma: no cover
    from pymodbus.client import AsyncModbusSerialClient as _AsyncModbusSerialClient
except (ImportError, AttributeError) as serial_import_err:  # pragma: no cover
    _AsyncModbusSerialClient = None
    SERIAL_IMPORT_ERROR: Exception | None = serial_import_err
else:  # pragma: no cover
    SERIAL_IMPORT_ERROR = None


def _shim_attr(name: str, default: Any) -> Any:
    shim = sys.modules.get('custom_components.thessla_green_modbus.modbus_transport')
    if shim is None:
        return default
    return getattr(shim, name, default)


class _ClientBackedTransport(BaseModbusTransport):
    """Shared implementation for transports backed by a pymodbus-like client."""

    client: Any | None = None

    async def _ensure_client(self) -> Any:
        if self.client is None:
            await self.ensure_connected()
        assert self.client is not None
        return self.client

    async def _invoke_client(
        self, method_name: str, slave_id: int, address: int, **kwargs: Any
    ) -> Any:
        client = await self._ensure_client()
        func = getattr(client, method_name)
        return await self.call(func, slave_id, address, **kwargs)

    async def _connect_client(self, *, endpoint: str) -> None:
        client = self.client
        if client is None:  # pragma: no cover
            raise ConnectionException("Internal error: client not initialized before connect")
        connect_method = getattr(client, "connect", None)
        if callable(connect_method):
            connected = connect_method()
            if inspect.isawaitable(connected):
                connected = await connected
        else:
            connected = True
            client.connected = True
        if not connected:
            self.offline_state = True
            raise ConnectionException(f"Could not connect to {endpoint}")
        self.offline_state = False

    async def _reset_connection(self) -> None:
        client = self.client
        if client is None:
            return
        try:
            await async_maybe_await_close(client)
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
        return await self._invoke_client(
            "read_input_registers",
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
        return await self._invoke_client(
            "read_holding_registers",
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
        return await self._invoke_client(
            "write_register",
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
        return await self._invoke_client(
            "write_registers",
            slave_id,
            address,
            values=values,
            attempt=attempt,
        )


class TcpModbusTransport(_ClientBackedTransport):
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
            try:
                return AsyncTcpClient(self.host, **fallback_kwargs)
            except TypeError:
                client = AsyncTcpClient()
                client.host = self.host
                client.port = self.port
                return client

    async def _connect(self) -> None:
        if self.connection_type == CONNECTION_TYPE_TCP_RTU:
            framer = _shim_attr("get_rtu_framer", get_rtu_framer)()
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
        await self._connect_client(endpoint=f"{self.host}:{self.port}")
        _LOGGER.debug("TCP Modbus connection established to %s:%s", self.host, self.port)


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
        self.client: _AsyncModbusSerialClient | None = None

    def _is_connected(self) -> bool:
        return bool(self.client and getattr(self.client, "connected", False))

    async def _connect(self) -> None:
        serial_client_cls = _shim_attr("_AsyncModbusSerialClient", _AsyncModbusSerialClient)
        if serial_client_cls is None:
            message = "Modbus serial client is unavailable. Install pymodbus with serial support."
            if SERIAL_IMPORT_ERROR is not None:
                message = f"{message} ({SERIAL_IMPORT_ERROR})"
            raise ConnectionException(message)
        if not self.serial_port:
            raise ConnectionException("Serial port not configured for RTU transport")
        self.client = serial_client_cls(
            method="rtu",
            port=self.serial_port,
            baudrate=self.baudrate,
            parity=self.parity,
            stopbits=self.stopbits,
            timeout=self.timeout,
        )
        await self._connect_client(endpoint=self.serial_port)
        _LOGGER.debug("RTU Modbus connection established on %s", self.serial_port)



__all__ = [
    "RtuModbusTransport",
    "SERIAL_IMPORT_ERROR",
    "TcpModbusTransport",
    "_AsyncModbusSerialClient",
    "_ClientBackedTransport",
]
