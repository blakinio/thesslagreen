# mypy: ignore-errors
"""TCP Modbus transport tests extracted from test_modbus_transport.py."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from custom_components.thessla_green_modbus.const import (
    CONNECTION_TYPE_TCP,
    CONNECTION_TYPE_TCP_RTU,
)
from custom_components.thessla_green_modbus.modbus_exceptions import ConnectionException
from custom_components.thessla_green_modbus.modbus_transport import TcpModbusTransport


def _make_tcp(connection_type=CONNECTION_TYPE_TCP, **kwargs):
    defaults = dict(
        host="127.0.0.1",
        port=502,
        connection_type=connection_type,
        max_retries=1,
        base_backoff=0.0,
        max_backoff=0.0,
        timeout=1.0,
    )
    defaults.update(kwargs)
    return TcpModbusTransport(**defaults)


def test_tcp_offline_property_default_false():
    t = _make_tcp()
    assert t.offline is False


def test_tcp_offline_property_true():
    t = _make_tcp(offline_state=True)
    assert t.offline is True


def test_tcp_is_connected_false_no_client():
    t = _make_tcp()
    assert t.is_connected() is False


def test_tcp_is_connected_true():
    t = _make_tcp()
    t.client = MagicMock(connected=True)
    assert t.is_connected() is True


def test_build_tcp_client_fallback_stripped_kwargs():
    import sys

    t = _make_tcp()
    call_count = [0]

    def patched_tcp_client(host, **kwargs):
        call_count[0] += 1
        if call_count[0] == 1:
            raise TypeError("unexpected kwarg")
        client = MagicMock()
        client.connected = True
        return client

    original = sys.modules["pymodbus.client"].AsyncModbusTcpClient
    sys.modules["pymodbus.client"].AsyncModbusTcpClient = patched_tcp_client
    try:
        client = t._build_tcp_client()
    finally:
        sys.modules["pymodbus.client"].AsyncModbusTcpClient = original

    assert client is not None
    assert call_count[0] == 2


def test_build_tcp_client_final_fallback():
    import sys

    t = _make_tcp()
    bare_instance = MagicMock()
    call_count = [0]

    def patched(*args, **kwargs):
        call_count[0] += 1
        if call_count[0] <= 2:
            raise TypeError("no kwargs")
        return bare_instance

    original = sys.modules["pymodbus.client"].AsyncModbusTcpClient
    sys.modules["pymodbus.client"].AsyncModbusTcpClient = patched
    try:
        client = t._build_tcp_client()
    finally:
        sys.modules["pymodbus.client"].AsyncModbusTcpClient = original

    assert client is bare_instance
    assert call_count[0] == 3


def test_build_tcp_client_with_framer_first_attempt():
    import sys

    t = _make_tcp()
    fake_framer = object()
    received_kwargs: dict = {}

    def patched(host, **kwargs):
        received_kwargs.update(kwargs)
        return MagicMock()

    original = sys.modules["pymodbus.client"].AsyncModbusTcpClient
    sys.modules["pymodbus.client"].AsyncModbusTcpClient = patched
    try:
        t._build_tcp_client(framer=fake_framer)
    finally:
        sys.modules["pymodbus.client"].AsyncModbusTcpClient = original

    assert received_kwargs.get("framer") is fake_framer


def test_build_tcp_client_with_framer_fallback():
    import sys

    t = _make_tcp()
    fake_framer = object()
    calls: list[dict] = []

    def patched(host, **kwargs):
        calls.append(dict(kwargs))
        if len(calls) == 1:
            raise TypeError("no reconnect params")
        return MagicMock()

    original = sys.modules["pymodbus.client"].AsyncModbusTcpClient
    sys.modules["pymodbus.client"].AsyncModbusTcpClient = patched
    try:
        t._build_tcp_client(framer=fake_framer)
    finally:
        sys.modules["pymodbus.client"].AsyncModbusTcpClient = original

    assert len(calls) == 2
    assert calls[1].get("framer") is fake_framer


@pytest.mark.asyncio
async def test_tcp_connect_tcp_rtu_framer_none():
    t = _make_tcp(connection_type=CONNECTION_TYPE_TCP_RTU)

    with (
        patch("custom_components.thessla_green_modbus.modbus_transport.get_rtu_framer", return_value=None),
        pytest.raises(ConnectionException, match="RTU framer"),
    ):
        await t._connect()


@pytest.mark.asyncio
async def test_tcp_connect_tcp_rtu_success():
    t = _make_tcp(connection_type=CONNECTION_TYPE_TCP_RTU)

    mock_framer = MagicMock()
    mock_client = MagicMock()
    mock_client.connect = MagicMock(return_value=True)
    mock_client.connected = True

    with (
        patch("custom_components.thessla_green_modbus.modbus_transport.get_rtu_framer", return_value=mock_framer),
        patch.object(t, "_build_tcp_client", return_value=mock_client),
    ):
        await t._connect()

    assert t.offline_state is False
    assert t.client is mock_client


@pytest.mark.asyncio
async def test_tcp_connect_non_awaitable_connect():
    t = _make_tcp()
    mock_client = MagicMock()
    mock_client.connect = MagicMock(return_value=True)
    mock_client.connected = True

    with patch.object(t, "_build_tcp_client", return_value=mock_client):
        await t._connect()

    assert t.offline_state is False


@pytest.mark.asyncio
async def test_tcp_connect_non_callable_connect():
    t = _make_tcp()
    mock_client = MagicMock(spec=[])
    mock_client.connected = True

    with patch.object(t, "_build_tcp_client", return_value=mock_client):
        await t._connect()

    assert t.offline_state is False


@pytest.mark.asyncio
async def test_tcp_connect_returns_false():
    t = _make_tcp()
    mock_client = MagicMock()
    mock_client.connect = MagicMock(return_value=False)

    with patch.object(t, "_build_tcp_client", return_value=mock_client):
        with pytest.raises(ConnectionException):
            await t._connect()

    assert t.offline_state is True


@pytest.mark.asyncio
async def test_tcp_read_input_registers_ensures_connection():
    t = _make_tcp()
    mock_client = MagicMock()
    mock_client.connected = True

    async def fake_ensure():
        t.client = mock_client

    mock_response = MagicMock()
    mock_response.isError.return_value = False
    mock_response.registers = [42]
    mock_client.read_input_registers = AsyncMock(return_value=mock_response)

    with patch.object(t, "ensure_connected", side_effect=fake_ensure):
        with patch.object(t, "call", new=AsyncMock(return_value=mock_response)):
            result = await t.read_input_registers(1, 100, count=1)

    assert result is mock_response


@pytest.mark.asyncio
async def test_tcp_read_holding_registers_ensures_connection():
    t = _make_tcp()
    mock_response = MagicMock()

    async def fake_ensure():
        t.client = MagicMock(connected=True)

    with patch.object(t, "ensure_connected", side_effect=fake_ensure):
        with patch.object(t, "call", new=AsyncMock(return_value=mock_response)):
            result = await t.read_holding_registers(1, 100, count=1)

    assert result is mock_response


@pytest.mark.asyncio
async def test_tcp_write_register_ensures_connection():
    t = _make_tcp()
    mock_response = MagicMock()

    async def fake_ensure():
        t.client = MagicMock(connected=True)

    with patch.object(t, "ensure_connected", side_effect=fake_ensure):
        with patch.object(t, "call", new=AsyncMock(return_value=mock_response)):
            result = await t.write_register(1, 100, value=5)

    assert result is mock_response


@pytest.mark.asyncio
async def test_tcp_write_registers_ensures_connection():
    t = _make_tcp()
    mock_response = MagicMock()

    async def fake_ensure():
        t.client = MagicMock(connected=True)

    with patch.object(t, "ensure_connected", side_effect=fake_ensure):
        with patch.object(t, "call", new=AsyncMock(return_value=mock_response)):
            result = await t.write_registers(1, 100, values=[1, 2])

    assert result is mock_response
