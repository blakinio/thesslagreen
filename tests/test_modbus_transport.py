# mypy: ignore-errors
"""Tests for modbus_transport.py — covers uncovered branches."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from custom_components.thessla_green_modbus.const import (
    CONNECTION_TYPE_TCP,
    CONNECTION_TYPE_TCP_RTU,
)
from custom_components.thessla_green_modbus.modbus_exceptions import ConnectionException
from custom_components.thessla_green_modbus.modbus_transport import (
    RawModbusResponse,
    RawModbusWriteResponse,
    TcpModbusTransport,
    _append_crc,
    _crc16,
)

# ---------------------------------------------------------------------------
# Pure helpers
# ---------------------------------------------------------------------------


def test_raw_modbus_response_is_error_false():
    resp = RawModbusResponse([1, 2, 3])
    assert resp.isError() is False


def test_raw_modbus_response_empty():
    resp = RawModbusResponse()
    assert resp.registers == []


def test_raw_modbus_write_response_is_error_false():
    resp = RawModbusWriteResponse()
    assert resp.isError() is False


def test_crc16_known_value():
    """CRC16 of empty bytes is 0xFFFF."""
    assert _crc16(b"") == 0xFFFF


def test_append_crc_appends_two_bytes():
    data = bytes([1, 2, 3])
    result = _append_crc(data)
    assert len(result) == len(data) + 2


# ---------------------------------------------------------------------------
# TcpModbusTransport helpers
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# TcpModbusTransport._build_tcp_client fallback paths
# ---------------------------------------------------------------------------


def test_build_tcp_client_fallback_stripped_kwargs():
    """_build_tcp_client falls back to minimal kwargs when reconnect params rejected."""
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
    """_build_tcp_client last resort creates bare instance and sets host/port."""
    import sys

    t = _make_tcp()

    bare_instance = MagicMock()
    call_count = [0]

    def patched(*args, **kwargs):
        call_count[0] += 1
        if call_count[0] <= 2:
            raise TypeError("no kwargs")
        # Third call: AsyncTcpClient() with no args — return bare instance
        return bare_instance

    original = sys.modules["pymodbus.client"].AsyncModbusTcpClient
    sys.modules["pymodbus.client"].AsyncModbusTcpClient = patched
    try:
        client = t._build_tcp_client()
    finally:
        sys.modules["pymodbus.client"].AsyncModbusTcpClient = original

    assert client is bare_instance
    assert call_count[0] == 3


# ---------------------------------------------------------------------------
# TcpModbusTransport._connect
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_tcp_connect_tcp_rtu_framer_none():
    """_connect raises ConnectionException when RTU framer is unavailable."""
    t = _make_tcp(connection_type=CONNECTION_TYPE_TCP_RTU)

    with (
        patch(
            "custom_components.thessla_green_modbus.modbus_transport.get_rtu_framer",
            return_value=None,
        ),
        pytest.raises(ConnectionException, match="RTU framer"),
    ):
        await t._connect()


@pytest.mark.asyncio
async def test_tcp_connect_tcp_rtu_success():
    """_connect with RTU framer sets offline_state to False on success."""
    t = _make_tcp(connection_type=CONNECTION_TYPE_TCP_RTU)

    mock_framer = MagicMock()
    mock_client = MagicMock()
    mock_client.connect = MagicMock(return_value=True)
    mock_client.connected = True

    with (
        patch(
            "custom_components.thessla_green_modbus.modbus_transport.get_rtu_framer",
            return_value=mock_framer,
        ),
        patch.object(t, "_build_tcp_client", return_value=mock_client),
    ):
        await t._connect()

    assert t.offline_state is False
    assert t.client is mock_client


@pytest.mark.asyncio
async def test_tcp_connect_non_awaitable_connect():
    """_connect handles non-coroutine connect() returning True."""
    t = _make_tcp()
    mock_client = MagicMock()
    mock_client.connect = MagicMock(return_value=True)
    mock_client.connected = True

    with patch.object(t, "_build_tcp_client", return_value=mock_client):
        await t._connect()

    assert t.offline_state is False


@pytest.mark.asyncio
async def test_tcp_connect_non_callable_connect():
    """_connect handles client without connect method (sets connected=True)."""
    t = _make_tcp()
    mock_client = MagicMock(spec=[])  # no connect attribute
    mock_client.connected = True

    with patch.object(t, "_build_tcp_client", return_value=mock_client):
        await t._connect()

    assert t.offline_state is False


@pytest.mark.asyncio
async def test_tcp_connect_returns_false():
    """_connect raises ConnectionException when connect() returns False."""
    t = _make_tcp()
    mock_client = MagicMock()
    mock_client.connect = MagicMock(return_value=False)

    with patch.object(t, "_build_tcp_client", return_value=mock_client):
        with pytest.raises(ConnectionException):
            await t._connect()

    assert t.offline_state is True


# ---------------------------------------------------------------------------
# TcpModbusTransport read/write when client is None
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_tcp_read_input_registers_ensures_connection():
    """read_input_registers calls ensure_connected when client is None."""
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
    """read_holding_registers calls ensure_connected when client is None."""
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
    """write_register calls ensure_connected when client is None."""
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
    """write_registers calls ensure_connected when client is None."""
    t = _make_tcp()
    mock_response = MagicMock()

    async def fake_ensure():
        t.client = MagicMock(connected=True)

    with patch.object(t, "ensure_connected", side_effect=fake_ensure):
        with patch.object(t, "call", new=AsyncMock(return_value=mock_response)):
            result = await t.write_registers(1, 100, values=[1, 2])

    assert result is mock_response


# ---------------------------------------------------------------------------
# BaseModbusTransport._execute error paths (via TcpModbusTransport)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_execute_success_clears_offline():
    """_execute clears offline_state on success."""
    t = _make_tcp(offline_state=True)

    async def success():
        return "ok"

    with patch.object(t, "ensure_connected", new=AsyncMock()):
        result = await t._execute(success)

    assert result == "ok"
    assert t.offline_state is False


# ---------------------------------------------------------------------------
# BaseModbusTransport._handle_timeout / _handle_transient / _apply_backoff
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_handle_timeout_sets_offline():
    t = _make_tcp()
    with patch.object(t, "_reset_connection", new=AsyncMock()):
        with patch.object(t, "_apply_backoff", new=AsyncMock()):
            await t._handle_timeout(1, TimeoutError("t"))
    assert t.offline_state is True


@pytest.mark.asyncio
async def test_handle_transient_sets_offline():
    t = _make_tcp()
    with patch.object(t, "_reset_connection", new=AsyncMock()):
        with patch.object(t, "_apply_backoff", new=AsyncMock()):
            await t._handle_transient(1, ConnectionException("c"))
    assert t.offline_state is True


@pytest.mark.asyncio
async def test_apply_backoff_zero():
    """_apply_backoff with base=0 does not sleep."""
    t = _make_tcp(base_backoff=0.0)
    with patch("asyncio.sleep", new=AsyncMock()) as mock_sleep:
        await t._apply_backoff(1)
    mock_sleep.assert_not_called()


@pytest.mark.asyncio
async def test_apply_backoff_respects_max():
    """_apply_backoff clamps delay to max_backoff."""
    t = _make_tcp(base_backoff=10.0, max_backoff=0.01)
    with patch("asyncio.sleep", new=AsyncMock()) as mock_sleep:
        await t._apply_backoff(1)
    mock_sleep.assert_called_once()
    assert mock_sleep.call_args[0][0] <= 0.01


def test_build_tcp_client_with_framer_first_attempt():
    """framer kwarg included in first TCP client call (line 314)."""
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
    """framer kwarg preserved in fallback call when first attempt raises TypeError (line 325)."""
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


# ---------------------------------------------------------------------------
# _execute — CancelledError suppresses _reset_connection exception (lines 124-125)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_execute_cancelled_suppresses_reset_exception():
    """Exception from _reset_connection during CancelledError is swallowed (lines 124-125)."""
    t = _make_tcp()
    t.client = MagicMock()
    t.client.connected = True

    async def failing_reset():
        raise RuntimeError("reset blew up")

    async def cancel_func():
        raise asyncio.CancelledError()

    with patch.object(t, "_reset_connection", side_effect=failing_reset):
        with pytest.raises(asyncio.CancelledError):
            await t._execute(cancel_func)
    # CancelledError propagated; RuntimeError was silently swallowed
