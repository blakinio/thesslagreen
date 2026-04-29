"""Tests for coordinator connection helper functions."""

from __future__ import annotations

import asyncio
import logging

import pytest
from custom_components.thessla_green_modbus.const import (
    CONNECTION_MODE_TCP_RTU,
    CONNECTION_TYPE_TCP,
)
from custom_components.thessla_green_modbus.coordinator.connection import (
    build_tcp_transport,
    connect_direct_tcp_client,
    connect_transport_or_client,
    ensure_transport_selected,
    setup_client_with_retry,
)
from custom_components.thessla_green_modbus.modbus_exceptions import (
    ConnectionException,
    ModbusException,
)
from custom_components.thessla_green_modbus.modbus_transport import (
    RawRtuOverTcpTransport,
    TcpModbusTransport,
)


class _AwaitableConnectClient:
    def __init__(
        self, host: str | None = None, *, port: int | None = None, timeout: float | None = None
    ) -> None:
        self.host = host
        self.port = port
        self.timeout = timeout
        self.connected = False

    async def connect(self) -> bool:
        self.connected = True
        return True


class _TypeErrorCtorClient:
    def __init__(self, *_args, **kwargs) -> None:
        if kwargs:
            raise TypeError("kwargs not supported")
        self.host = None
        self.port = None
        self.connected = False

    async def connect(self) -> bool:
        self.connected = True
        return True


def test_connect_direct_tcp_client_success() -> None:
    client = asyncio.run(
        connect_direct_tcp_client(
            host="127.0.0.1",
            port=502,
            timeout=5.0,
            tcp_client_cls=_AwaitableConnectClient,
            allow_parameterless_ctor=False,
        )
    )
    assert client is not None
    assert client.connected is True
    assert client.host == "127.0.0.1"


def test_connect_direct_tcp_client_parameterless_fallback() -> None:
    client = asyncio.run(
        connect_direct_tcp_client(
            host="127.0.0.1",
            port=1502,
            timeout=5.0,
            tcp_client_cls=_TypeErrorCtorClient,
            allow_parameterless_ctor=True,
        )
    )
    assert client is not None
    assert client.connected is True
    assert client.host == "127.0.0.1"
    assert client.port == 1502


def test_build_tcp_transport_rtu_over_tcp_mode() -> None:
    transport = build_tcp_transport(
        mode=CONNECTION_MODE_TCP_RTU,
        host="127.0.0.1",
        port=502,
        retry=3,
        backoff=0.1,
        max_backoff=1.0,
        timeout=5.0,
        offline_state=False,
        connection_type_tcp=CONNECTION_TYPE_TCP,
        connection_mode_tcp_rtu=CONNECTION_MODE_TCP_RTU,
    )
    assert isinstance(transport, RawRtuOverTcpTransport)


def test_build_tcp_transport_tcp_mode() -> None:
    transport = build_tcp_transport(
        mode="tcp",
        host="127.0.0.1",
        port=502,
        retry=3,
        backoff=0.1,
        max_backoff=1.0,
        timeout=5.0,
        offline_state=False,
        connection_type_tcp=CONNECTION_TYPE_TCP,
        connection_mode_tcp_rtu=CONNECTION_MODE_TCP_RTU,
    )
    assert isinstance(transport, TcpModbusTransport)


def test_setup_client_with_retry_success() -> None:
    async def _ensure() -> None:
        return None

    result = asyncio.run(
        setup_client_with_retry(
            ensure_connection=_ensure, logger=logging.getLogger("test.setup_client")
        )
    )
    assert result is True


def test_setup_client_with_retry_errors_return_false() -> None:
    async def _timeout() -> None:
        raise TimeoutError("timeout")

    async def _conn() -> None:
        raise ConnectionException("conn")

    async def _modbus() -> None:
        raise ModbusException("modbus")

    async def _os() -> None:
        raise OSError("os")

    logger = logging.getLogger("test.setup_client.errors")
    assert asyncio.run(setup_client_with_retry(ensure_connection=_timeout, logger=logger)) is False
    assert asyncio.run(setup_client_with_retry(ensure_connection=_conn, logger=logger)) is False
    assert asyncio.run(setup_client_with_retry(ensure_connection=_modbus, logger=logger)) is False
    assert asyncio.run(setup_client_with_retry(ensure_connection=_os, logger=logger)) is False


def test_ensure_transport_selected_rtu() -> None:
    selected, mode = asyncio.run(
        ensure_transport_selected(
            current_transport=None,
            connection_type="rtu",
            connection_mode=None,
            host="127.0.0.1",
            port=502,
            serial_port="/dev/ttyUSB0",
            baudrate=9600,
            parity="N",
            stopbits=1,
            retry=3,
            backoff=0.1,
            max_backoff=1.0,
            timeout=5.0,
            offline_state=False,
            connection_type_rtu="rtu",
            connection_mode_auto="auto",
            connection_mode_tcp="tcp",
            build_rtu_transport_fn=lambda **kwargs: RawRtuOverTcpTransport(
                host="127.0.0.1",
                port=502,
                max_retries=kwargs["retry"],
                base_backoff=kwargs["backoff"],
                max_backoff=kwargs["max_backoff"],
                timeout=kwargs["timeout"],
                offline_state=kwargs["offline_state"],
            ),
            build_tcp_transport_fn=lambda _mode: TcpModbusTransport(
                host="127.0.0.1",
                port=502,
                max_retries=3,
                base_backoff=0.1,
                max_backoff=1.0,
                timeout=5.0,
            ),
            select_auto_transport_fn=lambda: asyncio.sleep(0, result=(None, None)),
        )
    )
    assert isinstance(selected, RawRtuOverTcpTransport)
    assert mode is None


def test_ensure_transport_selected_auto_uses_selector() -> None:
    expected = TcpModbusTransport(
        host="127.0.0.1",
        port=502,
        max_retries=3,
        base_backoff=0.1,
        max_backoff=1.0,
        timeout=5.0,
    )

    selected, mode = asyncio.run(
        ensure_transport_selected(
            current_transport=None,
            connection_type="tcp",
            connection_mode="auto",
            host="127.0.0.1",
            port=502,
            serial_port="",
            baudrate=9600,
            parity="N",
            stopbits=1,
            retry=3,
            backoff=0.1,
            max_backoff=1.0,
            timeout=5.0,
            offline_state=False,
            connection_type_rtu="rtu",
            connection_mode_auto="auto",
            connection_mode_tcp="tcp",
            build_rtu_transport_fn=lambda **_kwargs: None,
            build_tcp_transport_fn=lambda _mode: expected,
            select_auto_transport_fn=lambda: asyncio.sleep(0, result=(expected, "tcp")),
        )
    )
    assert selected is expected
    assert mode == "tcp"


def test_connect_transport_or_client_with_transport() -> None:
    class _DummyTransport:
        def __init__(self) -> None:
            self.client = object()

        async def ensure_connected(self) -> None:
            return None

        def is_connected(self) -> bool:
            return True

    transport = _DummyTransport()
    result = asyncio.run(connect_transport_or_client(transport=transport, client=None))
    assert result is transport.client


def test_connect_transport_or_client_requires_client_or_transport() -> None:
    with pytest.raises(ConnectionException):
        asyncio.run(connect_transport_or_client(transport=None, client=None))
