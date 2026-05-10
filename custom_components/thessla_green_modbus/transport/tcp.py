"""TCP transport implementation."""

from __future__ import annotations

import inspect
import logging
from typing import Any

from pymodbus.client import AsyncModbusTcpClient

from ..const import CONNECTION_TYPE_TCP, CONNECTION_TYPE_TCP_RTU
from ..modbus.client_close import async_maybe_await_close
from ..modbus.framer import get_rtu_framer
from ..modbus_exceptions import ConnectionException
from .base import BaseModbusTransport

_LOGGER = logging.getLogger(__name__)


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
            return AsyncModbusTcpClient(self.host, **common_kwargs)
        except TypeError as exc:
            _LOGGER.debug(
                "AsyncModbusTcpClient does not accept reconnect parameters: %s",
                exc,
            )
            fallback_kwargs = {k: v for k, v in common_kwargs.items() if k in {"port", "timeout"}}
            if framer is not None:
                fallback_kwargs["framer"] = framer
            try:
                return AsyncModbusTcpClient(self.host, **fallback_kwargs)
            except TypeError:
                client = AsyncModbusTcpClient()
                client.host = self.host
                client.port = self.port
                return client

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
        await self._connect_client(endpoint=f"{self.host}:{self.port}")
        _LOGGER.debug("TCP Modbus connection established to %s:%s", self.host, self.port)


__all__ = [
    "TcpModbusTransport",
    "_ClientBackedTransport",
]
