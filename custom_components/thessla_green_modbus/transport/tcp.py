"""TCP transport helpers and implementation."""

from __future__ import annotations

import inspect
from typing import Any

from pymodbus.client import AsyncModbusTcpClient

from ..const import CONNECTION_TYPE_TCP, CONNECTION_TYPE_TCP_RTU
from ..modbus_exceptions import ConnectionException
from ..modbus_helpers import async_maybe_await_close, get_rtu_framer
from .base import BaseModbusTransport


class TcpModbusTransport(BaseModbusTransport):
    """TCP Modbus transport implementation."""

    def __init__(self, *, host: str, port: int, connection_type: str = CONNECTION_TYPE_TCP, **kwargs: Any) -> None:
        super().__init__(**kwargs)
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
        except TypeError:
            fallback = {k: v for k, v in common_kwargs.items() if k in {"port", "timeout", "framer"}}
            try:
                return AsyncModbusTcpClient(self.host, **fallback)
            except TypeError:
                client = AsyncModbusTcpClient()
                client.host = self.host
                client.port = self.port
                return client

    async def _connect(self) -> None:
        framer = None
        if self.connection_type == CONNECTION_TYPE_TCP_RTU:
            framer = get_rtu_framer()
            if framer is None:
                raise ConnectionException("RTU framer support is unavailable")
        self.client = self._build_tcp_client(framer=framer)
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
            raise ConnectionException(f"Could not connect to {self.host}:{self.port}")
        self.offline_state = False

    async def _reset_connection(self) -> None:
        if self.client is None:
            return
        try:
            await async_maybe_await_close(self.client)
        finally:
            self.client = None
