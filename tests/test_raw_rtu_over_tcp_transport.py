import asyncio

import pytest

from custom_components.thessla_green_modbus.modbus_transport import (
    RawRtuOverTcpTransport,
    _crc16,
)


class DummyWriter:
    def __init__(self) -> None:
        self.buffer = bytearray()
        self._closed = False

    def write(self, data: bytes) -> None:
        self.buffer.extend(data)

    async def drain(self) -> None:
        return None

    def close(self) -> None:
        self._closed = True

    async def wait_closed(self) -> None:
        return None

    def is_closing(self) -> bool:
        return self._closed


def test_crc16_matches_fixture():
    payload = bytes.fromhex("0a0400010002")
    assert _crc16(payload) == 0x7021


def test_build_frames_match_hex_fixtures():
    read_frame = RawRtuOverTcpTransport._build_read_frame(0x0A, 4, 0x0001, 0x0002)
    assert read_frame.hex() == "0a04000100022170"

    write_single = RawRtuOverTcpTransport._build_write_single_frame(0x0A, 0x0010, 0x002A)
    assert write_single.hex() == "0a060010002a08ab"

    write_multiple = RawRtuOverTcpTransport._build_write_multiple_frame(
        0x0A, 0x0010, [0x002A, 0x002B]
    )
    assert write_multiple.hex() == "0a100010000204002a002bb650"


@pytest.mark.asyncio
async def test_raw_rtu_over_tcp_reads_registers(monkeypatch):
    reader = asyncio.StreamReader()
    reader.feed_data(bytes.fromhex("0a0304002a002b2124"))
    reader.feed_eof()
    writer = DummyWriter()

    async def open_connection(_host: str, _port: int):
        return reader, writer

    monkeypatch.setattr(asyncio, "open_connection", open_connection)

    transport = RawRtuOverTcpTransport(
        host="127.0.0.1",
        port=502,
        max_retries=1,
        base_backoff=0.0,
        max_backoff=0.0,
        timeout=1.0,
    )

    response = await transport.read_holding_registers(0x0A, 0x0010, count=2)

    assert response.registers == [0x002A, 0x002B]
    assert bytes(writer.buffer).hex() == "0a0300100002c4b5"
