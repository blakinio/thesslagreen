# mypy: ignore-errors
"""Tests for modbus_transport.py — covers uncovered branches."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import custom_components.thessla_green_modbus.modbus_transport as _transport_mod
import pytest
from custom_components.thessla_green_modbus.const import (
    CONNECTION_TYPE_TCP,
    CONNECTION_TYPE_TCP_RTU,
)
from custom_components.thessla_green_modbus.modbus_exceptions import (
    ConnectionException,
    ModbusException,
    ModbusIOException,
)
from custom_components.thessla_green_modbus.modbus_transport import (
    RawModbusResponse,
    RawModbusWriteResponse,
    RawRtuOverTcpTransport,
    RtuModbusTransport,
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

    with patch(
        "custom_components.thessla_green_modbus.modbus_transport.get_rtu_framer",
        return_value=None,
    ):
        with pytest.raises(ConnectionException, match="RTU framer"):
            await t._connect()


@pytest.mark.asyncio
async def test_tcp_connect_tcp_rtu_success():
    """_connect with RTU framer sets offline_state to False on success."""
    t = _make_tcp(connection_type=CONNECTION_TYPE_TCP_RTU)

    mock_framer = MagicMock()
    mock_client = MagicMock()
    mock_client.connect = MagicMock(return_value=True)
    mock_client.connected = True

    with patch(
        "custom_components.thessla_green_modbus.modbus_transport.get_rtu_framer",
        return_value=mock_framer,
    ):
        with patch.object(t, "_build_tcp_client", return_value=mock_client):
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
async def test_execute_timeout_error():
    """_execute sets offline_state=True and re-raises TimeoutError."""
    t = _make_tcp()

    async def raises_timeout():
        raise TimeoutError("timeout")

    with patch.object(t, "_reset_connection", new=AsyncMock()):
        with pytest.raises(TimeoutError):
            await t._execute(raises_timeout)

    assert t.offline_state is True


@pytest.mark.asyncio
async def test_execute_modbus_io_exception():
    """_execute sets offline_state=True and re-raises ModbusIOException."""
    t = _make_tcp()

    async def raises_io():
        raise ModbusIOException("io error")

    with patch.object(t, "_reset_connection", new=AsyncMock()):
        with pytest.raises(ModbusIOException):
            await t._execute(raises_io)

    assert t.offline_state is True


@pytest.mark.asyncio
async def test_execute_connection_exception():
    """_execute sets offline_state=True and re-raises ConnectionException."""
    t = _make_tcp()

    async def raises_conn():
        raise ConnectionException("conn error")

    with patch.object(t, "_reset_connection", new=AsyncMock()):
        with pytest.raises(ConnectionException):
            await t._execute(raises_conn)

    assert t.offline_state is True


@pytest.mark.asyncio
async def test_execute_os_error():
    """_execute handles OSError the same as ConnectionException."""
    t = _make_tcp()

    async def raises_os():
        raise OSError("os error")

    with patch.object(t, "_reset_connection", new=AsyncMock()):
        with pytest.raises(OSError):
            await t._execute(raises_os)

    assert t.offline_state is True


@pytest.mark.asyncio
async def test_execute_modbus_exception():
    """_execute sets offline_state=True and re-raises ModbusException."""
    t = _make_tcp()

    async def raises_modbus():
        raise ModbusException("modbus err")

    with patch.object(t, "_reset_connection", new=AsyncMock()):
        with pytest.raises(ModbusException):
            await t._execute(raises_modbus)

    assert t.offline_state is True


@pytest.mark.asyncio
async def test_execute_cancelled_error():
    """_execute handles CancelledError and re-raises."""
    t = _make_tcp()

    async def raises_cancelled():
        raise asyncio.CancelledError()

    with patch.object(t, "_reset_connection", new=AsyncMock()):
        with pytest.raises(asyncio.CancelledError):
            await t._execute(raises_cancelled)

    assert t.offline_state is True


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


# ---------------------------------------------------------------------------
# RawRtuOverTcpTransport
# ---------------------------------------------------------------------------


def _make_raw_tcp(**kwargs):
    defaults = dict(
        host="127.0.0.1",
        port=502,
        max_retries=1,
        base_backoff=0.0,
        max_backoff=0.0,
        timeout=1.0,
    )
    defaults.update(kwargs)
    return RawRtuOverTcpTransport(**defaults)


@pytest.mark.asyncio
async def test_raw_tcp_connect_timeout():
    """_connect raises TimeoutError on connection timeout."""
    t = _make_raw_tcp()
    with patch(
        "asyncio.open_connection",
        side_effect=TimeoutError("connect timeout"),
    ):
        with pytest.raises(TimeoutError, match="Timed out connecting"):
            await t._connect()


@pytest.mark.asyncio
async def test_raw_tcp_connect_os_error():
    """_connect raises ConnectionException on OSError."""
    t = _make_raw_tcp()
    with patch(
        "asyncio.open_connection",
        side_effect=OSError("refused"),
    ):
        with pytest.raises(ConnectionException, match="Could not connect"):
            await t._connect()


@pytest.mark.asyncio
async def test_raw_tcp_reset_connection_no_writer():
    """_reset_connection with no writer just clears reader."""
    t = _make_raw_tcp()
    t._reader = MagicMock()
    t._writer = None
    await t._reset_connection()
    assert t._reader is None


@pytest.mark.asyncio
async def test_raw_tcp_reset_connection_with_writer():
    """_reset_connection closes writer and clears both attributes."""
    t = _make_raw_tcp()
    mock_writer = MagicMock()
    mock_writer.close = MagicMock()
    mock_writer.wait_closed = AsyncMock()
    t._writer = mock_writer
    t._reader = MagicMock()

    await t._reset_connection()

    mock_writer.close.assert_called_once()
    mock_writer.wait_closed.assert_awaited_once()
    assert t._reader is None
    assert t._writer is None


@pytest.mark.asyncio
async def test_raw_tcp_read_exactly_no_reader():
    """_read_exactly raises ConnectionException when reader is None."""
    t = _make_raw_tcp()
    with pytest.raises(ConnectionException, match="not connected"):
        await t._read_exactly(4)


@pytest.mark.asyncio
async def test_raw_tcp_read_exactly_incomplete_read():
    """_read_exactly raises ModbusIOException on IncompleteReadError."""
    t = _make_raw_tcp()
    mock_reader = AsyncMock()
    mock_reader.readexactly = AsyncMock(side_effect=asyncio.IncompleteReadError(b"", 4))
    t._reader = mock_reader

    with pytest.raises(ModbusIOException, match="Incomplete"):
        await t._read_exactly(4)


@pytest.mark.asyncio
async def test_raw_tcp_read_exactly_timeout():
    """_read_exactly raises TimeoutError when read times out."""
    t = _make_raw_tcp(timeout=0.001)
    mock_reader = AsyncMock()

    async def slow_read(n):
        await asyncio.sleep(10)
        return b"\x00" * n

    mock_reader.readexactly = slow_read
    t._reader = mock_reader

    with pytest.raises((TimeoutError, asyncio.TimeoutError)):
        await t._read_exactly(4)


def test_validate_crc_mismatch():
    """_validate_crc raises ModbusIOException on CRC mismatch."""
    from custom_components.thessla_green_modbus.modbus_transport import RawRtuOverTcpTransport

    with pytest.raises(ModbusIOException, match="CRC mismatch"):
        RawRtuOverTcpTransport._validate_crc(b"\x01\x03", b"\xff\xff")


def test_build_read_frame_structure():
    """_build_read_frame produces correct RTU frame."""
    from custom_components.thessla_green_modbus.modbus_transport import RawRtuOverTcpTransport

    frame = RawRtuOverTcpTransport._build_read_frame(1, 4, 0x0064, 10)
    # slave, func, addr_hi, addr_lo, count_hi, count_lo + 2 CRC bytes = 8
    assert len(frame) == 8
    assert frame[0] == 1  # slave_id
    assert frame[1] == 4  # function


def test_build_write_single_frame_structure():
    """_build_write_single_frame produces correct write single frame."""
    from custom_components.thessla_green_modbus.modbus_transport import RawRtuOverTcpTransport

    frame = RawRtuOverTcpTransport._build_write_single_frame(1, 0x0064, 42)
    assert len(frame) == 8
    assert frame[0] == 1  # slave_id
    assert frame[1] == 6  # function code for write single register


def test_build_write_multiple_frame_structure():
    """_build_write_multiple_frame produces correct write multiple frame."""
    from custom_components.thessla_green_modbus.modbus_transport import RawRtuOverTcpTransport

    frame = RawRtuOverTcpTransport._build_write_multiple_frame(1, 0x0064, [10, 20])
    # 1(slave) + 1(func) + 2(addr) + 2(qty) + 1(byte_count) + 4(2 values) + 2(CRC) = 13
    assert len(frame) == 13
    assert frame[0] == 1  # slave_id
    assert frame[1] == 16  # function code 0x10


# ---------------------------------------------------------------------------
# _read_response paths
# ---------------------------------------------------------------------------


def _make_raw_tcp_with_reader(responses: list[bytes]) -> RawRtuOverTcpTransport:
    """Create transport with a reader that returns given byte sequences."""
    t = _make_raw_tcp()
    read_iter = iter(responses)

    async def readexactly(n):
        return next(read_iter)

    mock_reader = AsyncMock()
    mock_reader.readexactly = readexactly
    t._reader = mock_reader
    return t


@pytest.mark.asyncio
async def test_read_response_wrong_slave():
    """_read_response raises ModbusIOException when slave ID doesn't match."""
    # response says slave=2, but we asked for slave=1
    t = _make_raw_tcp_with_reader([bytes([2, 4])])

    with pytest.raises(ModbusIOException, match="slave ID"):
        await t._read_response(1, 4)


@pytest.mark.asyncio
async def test_read_response_modbus_exception():
    """_read_response raises ModbusException when error bit is set."""
    # func = 0x84 (0x04 | 0x80), exception code = 2
    payload = bytes([1, 0x84])
    exception_code = bytes([2])
    # valid CRC for payload + exception_code
    full = payload + exception_code
    crc = _crc16(full).to_bytes(2, "little")
    t = _make_raw_tcp_with_reader([payload, exception_code, crc])

    with pytest.raises(ModbusException):
        await t._read_response(1, 4)


@pytest.mark.asyncio
async def test_read_response_wrong_function():
    """_read_response raises ModbusIOException when function code doesn't match."""
    # slave=1 matches, func=3 but we asked for 4
    t = _make_raw_tcp_with_reader([bytes([1, 3])])

    with pytest.raises(ModbusIOException, match="function code"):
        await t._read_response(1, 4)


@pytest.mark.asyncio
async def test_read_response_write_body():
    """_read_response returns 4-byte body for write operations (func != 3/4)."""
    # For write single (func=6): header + 4 body bytes + 2 CRC
    header = bytes([1, 6])
    body = bytes([0x00, 0x64, 0x00, 0x2A])  # addr=100, value=42
    payload = header + body
    crc = _crc16(payload).to_bytes(2, "little")
    t = _make_raw_tcp_with_reader([header, body, crc])

    result = await t._read_response(1, 6)
    assert result == body


@pytest.mark.asyncio
async def test_read_response_read_registers():
    """_read_response returns register data for func=4 (input registers)."""
    header = bytes([1, 4])
    data = bytes([0x00, 0x05])  # one register = 5
    byte_count = bytes([len(data)])
    payload = header + byte_count + data
    crc = _crc16(payload).to_bytes(2, "little")
    t = _make_raw_tcp_with_reader([header, byte_count, data, crc])

    result = await t._read_response(1, 4)
    assert result == data


# ---------------------------------------------------------------------------
# _send_frame when writer is None
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_send_frame_no_writer():
    """_send_frame raises ConnectionException when writer is None."""
    t = _make_raw_tcp()
    t._writer = None

    with pytest.raises(ConnectionException, match="not connected"):
        await t._send_frame(b"\x00", 1, 4)


# ---------------------------------------------------------------------------
# RawRtuOverTcpTransport read/write integration paths
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_raw_tcp_read_input_registers():
    """read_input_registers returns RawModbusResponse with parsed registers."""
    t = _make_raw_tcp()

    data = bytes([0x00, 0x2A])  # value = 42

    async def fake_send_frame(frame, slave, func):
        return data

    with patch.object(t, "_send_frame", side_effect=fake_send_frame):
        with patch.object(t, "ensure_connected", new=AsyncMock()):
            result = await t.read_input_registers(1, 100, count=1)

    assert result.registers == [42]


@pytest.mark.asyncio
async def test_raw_tcp_read_holding_registers():
    """read_holding_registers returns RawModbusResponse with parsed registers."""
    t = _make_raw_tcp()
    data = bytes([0x00, 0x0F])  # value = 15

    async def fake_send_frame(frame, slave, func):
        return data

    with patch.object(t, "_send_frame", side_effect=fake_send_frame):
        with patch.object(t, "ensure_connected", new=AsyncMock()):
            result = await t.read_holding_registers(1, 100, count=1)

    assert result.registers == [15]


@pytest.mark.asyncio
async def test_raw_tcp_write_register():
    """write_register returns RawModbusWriteResponse on matching response."""
    t = _make_raw_tcp()
    # response body: addr_hi, addr_lo, val_hi, val_lo
    response_body = bytes([0x00, 0x64, 0x00, 0x05])  # addr=100, value=5

    async def fake_send_frame(frame, slave, func):
        return response_body

    with patch.object(t, "_send_frame", side_effect=fake_send_frame):
        with patch.object(t, "ensure_connected", new=AsyncMock()):
            result = await t.write_register(1, 100, value=5)

    assert isinstance(result, RawModbusWriteResponse)


@pytest.mark.asyncio
async def test_raw_tcp_write_register_mismatch():
    """write_register raises ModbusIOException when response doesn't match."""
    t = _make_raw_tcp()
    # Wrong value returned
    response_body = bytes([0x00, 0x64, 0x00, 0x09])  # addr=100, value=9 (expected 5)

    async def fake_send_frame(frame, slave, func):
        return response_body

    with patch.object(t, "_send_frame", side_effect=fake_send_frame):
        with patch.object(t, "ensure_connected", new=AsyncMock()):
            with pytest.raises(ModbusIOException, match="does not match"):
                await t.write_register(1, 100, value=5)


@pytest.mark.asyncio
async def test_raw_tcp_write_registers():
    """write_registers returns RawModbusWriteResponse on matching response."""
    t = _make_raw_tcp()
    # response: addr=100, qty=2
    response_body = bytes([0x00, 0x64, 0x00, 0x02])

    async def fake_send_frame(frame, slave, func):
        return response_body

    with patch.object(t, "_send_frame", side_effect=fake_send_frame):
        with patch.object(t, "ensure_connected", new=AsyncMock()):
            result = await t.write_registers(1, 100, values=[1, 2])

    assert isinstance(result, RawModbusWriteResponse)


@pytest.mark.asyncio
async def test_raw_tcp_write_registers_mismatch():
    """write_registers raises ModbusIOException when qty doesn't match."""
    t = _make_raw_tcp()
    # response says qty=1, but we sent 2
    response_body = bytes([0x00, 0x64, 0x00, 0x01])

    async def fake_send_frame(frame, slave, func):
        return response_body

    with patch.object(t, "_send_frame", side_effect=fake_send_frame):
        with patch.object(t, "ensure_connected", new=AsyncMock()):
            with pytest.raises(ModbusIOException, match="does not match"):
                await t.write_registers(1, 100, values=[1, 2])


@pytest.mark.asyncio
async def test_raw_tcp_write_register_invalid_length():
    """write_register raises ModbusIOException when response length != 4."""
    t = _make_raw_tcp()

    async def fake_send_frame(frame, slave, func):
        return bytes([0x00, 0x64])  # only 2 bytes, should be 4

    with patch.object(t, "_send_frame", side_effect=fake_send_frame):
        with patch.object(t, "ensure_connected", new=AsyncMock()):
            with pytest.raises(ModbusIOException, match="length"):
                await t.write_register(1, 100, value=5)


@pytest.mark.asyncio
async def test_raw_tcp_read_input_registers_invalid_byte_count():
    """read_input_registers raises ModbusIOException on odd data length."""
    t = _make_raw_tcp()

    async def fake_send_frame(frame, slave, func):
        return bytes([0x00, 0x01, 0x02])  # 3 bytes = odd

    with patch.object(t, "_send_frame", side_effect=fake_send_frame):
        with patch.object(t, "ensure_connected", new=AsyncMock()):
            with pytest.raises(ModbusIOException, match="byte count"):
                await t.read_input_registers(1, 100, count=1)


# ---------------------------------------------------------------------------
# TcpModbusTransport._connect — TCP-RTU TypeError on _build_tcp_client
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_tcp_connect_rtu_build_client_type_error():
    """_connect for TCP-RTU raises ConnectionException when _build_tcp_client raises TypeError."""
    t = _make_tcp(connection_type=CONNECTION_TYPE_TCP_RTU)
    mock_framer = MagicMock()

    with patch(
        "custom_components.thessla_green_modbus.modbus_transport.get_rtu_framer",
        return_value=mock_framer,
    ):
        with patch.object(t, "_build_tcp_client", side_effect=TypeError("framer not supported")):
            with pytest.raises(ConnectionException, match="not supported"):
                await t._connect()


# ---------------------------------------------------------------------------
# RawRtuOverTcpTransport — odd byte count in read_holding_registers (line 797)
# and invalid length in write_registers (line 842)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_raw_tcp_read_holding_registers_invalid_byte_count():
    """read_holding_registers raises ModbusIOException on odd data length."""
    t = _make_raw_tcp()

    async def fake_send_frame(frame, slave, func):
        return bytes([0x00, 0x01, 0x02])  # 3 bytes = odd

    with patch.object(t, "_send_frame", side_effect=fake_send_frame):
        with patch.object(t, "ensure_connected", new=AsyncMock()):
            with pytest.raises(ModbusIOException, match="byte count"):
                await t.read_holding_registers(1, 100, count=1)


@pytest.mark.asyncio
async def test_raw_tcp_write_registers_invalid_length():
    """write_registers raises ModbusIOException when response length != 4."""
    t = _make_raw_tcp()

    async def fake_send_frame(frame, slave, func):
        return bytes([0x00, 0x64])  # only 2 bytes

    with patch.object(t, "_send_frame", side_effect=fake_send_frame):
        with patch.object(t, "ensure_connected", new=AsyncMock()):
            with pytest.raises(ModbusIOException, match="length"):
                await t.write_registers(1, 100, values=[1, 2])


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
