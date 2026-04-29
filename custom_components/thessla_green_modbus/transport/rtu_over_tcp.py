"""Raw RTU-over-TCP utilities."""

from __future__ import annotations

from .crc import append_crc, crc16


def validate_crc(payload: bytes, crc_bytes: bytes) -> None:
    expected = crc16(payload).to_bytes(2, "little")
    if crc_bytes != expected:
        raise ValueError("CRC mismatch in RTU response")


def build_read_frame(slave_id: int, function: int, address: int, count: int) -> bytes:
    payload = bytes(
        [
            slave_id & 0xFF,
            function & 0xFF,
            (address >> 8) & 0xFF,
            address & 0xFF,
            (count >> 8) & 0xFF,
            count & 0xFF,
        ]
    )
    return append_crc(payload)
