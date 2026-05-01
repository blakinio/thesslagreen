# mypy: ignore-errors
"""Raw RTU-over-TCP transport tests extracted from test_modbus_transport.py."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from custom_components.thessla_green_modbus.modbus_exceptions import (
    ConnectionException,
    ModbusException,
    ModbusIOException,
)
from custom_components.thessla_green_modbus.modbus_transport import (
    RawModbusWriteResponse,
    RawRtuOverTcpTransport,
    _crc16,
)

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
    with (
        patch(
            "asyncio.open_connection",
            side_effect=TimeoutError("connect timeout"),
        ),
        pytest.raises(TimeoutError, match="Timed out connecting"),
    ):
        await t._connect()


@pytest.mark.asyncio
async def test_raw_tcp_connect_os_error():
    """_connect raises ConnectionException on OSError."""
    t = _make_raw_tcp()
    with (
        patch(
            "asyncio.open_connection",
            side_effect=OSError("refused"),
        ),
        pytest.raises(ConnectionException, match="Could not connect"),
    ):
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




def test_validate_response_header_wrong_slave():
    t = _make_raw_tcp()
    with pytest.raises(ModbusIOException, match="slave ID"):
        t._validate_response_header(bytes([2, 4]), slave_id=1, function=4)


def test_validate_response_header_wrong_function():
    t = _make_raw_tcp()
    with pytest.raises(ModbusIOException, match="function code"):
        t._validate_response_header(bytes([1, 3]), slave_id=1, function=4)


def test_validate_response_header_exception_function_passthrough():
    t = _make_raw_tcp()
    assert t._validate_response_header(bytes([1, 0x84]), slave_id=1, function=4) == 0x84


def test_is_exception_function_matches_request_function():
    t = _make_raw_tcp()
    assert t._is_exception_function(0x84, expected_function=4)
    assert not t._is_exception_function(0x83, expected_function=4)


def test_validate_response_header_rejects_mismatched_exception_function():
    t = _make_raw_tcp()
    with pytest.raises(ModbusIOException, match="function code"):
        t._validate_response_header(bytes([1, 0x83]), slave_id=1, function=4)


def test_parse_exception_response_payload_returns_exception_code():
    t = _make_raw_tcp()
    assert t._parse_exception_response_payload(bytes([1, 0x84, 2]), function=0x84) == 2


def test_parse_exception_response_payload_rejects_invalid_length():
    t = _make_raw_tcp()
    with pytest.raises(ModbusIOException, match="payload length"):
        t._parse_exception_response_payload(bytes([1, 0x84]), function=0x84)


def test_parse_exception_response_payload_rejects_wrong_function():
    t = _make_raw_tcp()
    with pytest.raises(ModbusIOException, match="function code"):
        t._parse_exception_response_payload(bytes([1, 0x83, 2]), function=0x84)


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
