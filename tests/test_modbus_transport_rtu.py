# mypy: ignore-errors
"""RTU transport tests extracted from test_modbus_transport.py."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import custom_components.thessla_green_modbus.modbus_transport as _transport_mod
import pytest
from custom_components.thessla_green_modbus.modbus_exceptions import ConnectionException
from custom_components.thessla_green_modbus.modbus_transport import RtuModbusTransport

# ---------------------------------------------------------------------------
# RtuModbusTransport tests
# ---------------------------------------------------------------------------


def _make_rtu(**kwargs):
    defaults = dict(
        serial_port="/dev/ttyUSB0",
        baudrate=9600,
        parity="N",
        stopbits=1,
        max_retries=1,
        base_backoff=0.0,
        max_backoff=0.0,
        timeout=1.0,
    )
    defaults.update(kwargs)
    return RtuModbusTransport(**defaults)


@pytest.mark.asyncio
async def test_rtu_connect_serial_unavailable():
    """RtuModbusTransport._connect raises ConnectionException when serial client is None."""
    t = _make_rtu()
    with patch.object(_transport_mod, "_AsyncModbusSerialClient", None):
        with patch.object(_transport_mod, "SERIAL_IMPORT_ERROR", ImportError("no serial")):
            with pytest.raises(ConnectionException, match="serial"):
                await t._connect()


@pytest.mark.asyncio
async def test_rtu_connect_serial_unavailable_no_error():
    """RtuModbusTransport._connect message works even when SERIAL_IMPORT_ERROR is None."""
    t = _make_rtu()
    with patch.object(_transport_mod, "_AsyncModbusSerialClient", None):
        with patch.object(_transport_mod, "SERIAL_IMPORT_ERROR", None):
            with pytest.raises(ConnectionException, match="unavailable"):
                await t._connect()


@pytest.mark.asyncio
async def test_rtu_connect_empty_serial_port():
    """RtuModbusTransport._connect raises ConnectionException when serial_port is empty."""
    t = _make_rtu(serial_port="")
    mock_client_cls = MagicMock()
    with patch.object(_transport_mod, "_AsyncModbusSerialClient", mock_client_cls):
        with pytest.raises(ConnectionException, match="not configured"):
            await t._connect()


@pytest.mark.asyncio
async def test_rtu_connect_success_non_awaitable():
    """RtuModbusTransport._connect succeeds when connect() is synchronous."""
    t = _make_rtu()
    mock_client = MagicMock()
    mock_client.connect = MagicMock(return_value=True)
    mock_client.connected = True

    mock_cls = MagicMock(return_value=mock_client)
    with patch.object(_transport_mod, "_AsyncModbusSerialClient", mock_cls):
        await t._connect()

    assert t.offline_state is False
    assert t.client is mock_client


@pytest.mark.asyncio
async def test_rtu_connect_returns_false():
    """RtuModbusTransport._connect raises ConnectionException when connect() returns False."""
    t = _make_rtu()
    mock_client = MagicMock()
    mock_client.connect = MagicMock(return_value=False)

    mock_cls = MagicMock(return_value=mock_client)
    with patch.object(_transport_mod, "_AsyncModbusSerialClient", mock_cls):
        with pytest.raises(ConnectionException, match="Could not connect"):
            await t._connect()

    assert t.offline_state is True


@pytest.mark.asyncio
async def test_rtu_reset_connection():
    """RtuModbusTransport._reset_connection closes and clears client."""
    t = _make_rtu()
    mock_client = MagicMock()
    mock_client.close = AsyncMock()
    t.client = mock_client

    await t._reset_connection()

    assert t.client is None


@pytest.mark.asyncio
async def test_rtu_reset_connection_no_client():
    """RtuModbusTransport._reset_connection is a no-op when client is None."""
    t = _make_rtu()
    t.client = None
    await t._reset_connection()  # should not raise


@pytest.mark.asyncio
async def test_rtu_read_input_registers_ensures_connection():
    """RtuModbusTransport.read_input_registers calls ensure_connected when client is None."""
    t = _make_rtu()
    mock_response = MagicMock()

    async def fake_ensure():
        t.client = MagicMock(connected=True)

    with patch.object(t, "ensure_connected", side_effect=fake_ensure):
        with patch.object(t, "call", new=AsyncMock(return_value=mock_response)):
            result = await t.read_input_registers(1, 100, count=1)

    assert result is mock_response


@pytest.mark.asyncio
async def test_rtu_read_holding_registers_ensures_connection():
    """RtuModbusTransport.read_holding_registers calls ensure_connected when client is None."""
    t = _make_rtu()
    mock_response = MagicMock()

    async def fake_ensure():
        t.client = MagicMock(connected=True)

    with patch.object(t, "ensure_connected", side_effect=fake_ensure):
        with patch.object(t, "call", new=AsyncMock(return_value=mock_response)):
            result = await t.read_holding_registers(1, 100, count=1)

    assert result is mock_response


@pytest.mark.asyncio
async def test_rtu_write_register_ensures_connection():
    """RtuModbusTransport.write_register calls ensure_connected when client is None."""
    t = _make_rtu()
    mock_response = MagicMock()

    async def fake_ensure():
        t.client = MagicMock(connected=True)

    with patch.object(t, "ensure_connected", side_effect=fake_ensure):
        with patch.object(t, "call", new=AsyncMock(return_value=mock_response)):
            result = await t.write_register(1, 100, value=5)

    assert result is mock_response


@pytest.mark.asyncio
async def test_rtu_write_registers_ensures_connection():
    """RtuModbusTransport.write_registers calls ensure_connected when client is None."""
    t = _make_rtu()
    mock_response = MagicMock()

    async def fake_ensure():
        t.client = MagicMock(connected=True)

    with patch.object(t, "ensure_connected", side_effect=fake_ensure):
        with patch.object(t, "call", new=AsyncMock(return_value=mock_response)):
            result = await t.write_registers(1, 100, values=[1, 2])

    assert result is mock_response


# ---------------------------------------------------------------------------
# _build_tcp_client with framer kwarg (lines 314, 325)
# ---------------------------------------------------------------------------




# ---------------------------------------------------------------------------
# RtuModbusTransport._connect — no callable connect attr (lines 516-517)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_rtu_connect_no_callable_connect(monkeypatch):
    """RTU _connect sets connected=True when client.connect is not callable (lines 516-517)."""
    from custom_components.thessla_green_modbus.modbus_transport import RtuModbusTransport

    class NoConnectClient:
        connected = False
        connect = None  # not callable

        async def close(self):
            pass

    monkeypatch.setattr(
        "custom_components.thessla_green_modbus.modbus_transport._AsyncModbusSerialClient",
        lambda **kwargs: NoConnectClient(),
    )

    transport = RtuModbusTransport(
        serial_port="/dev/ttyUSB0",
        baudrate=9600,
        parity="N",
        stopbits=1,
        max_retries=2,
        base_backoff=0.1,
        max_backoff=1.0,
        timeout=2.0,
    )
    await transport._connect()

    assert transport.client.connected is True
    assert transport.offline_state is False
