"""CRC helpers for RTU framing."""

from __future__ import annotations


def crc16(data: bytes) -> int:
    crc = 0xFFFF
    for byte in data:
        crc ^= byte
        for _ in range(8):
            crc = (crc >> 1) ^ 0xA001 if crc & 1 else crc >> 1
    return crc & 0xFFFF


def crc16_bytes(data: bytes) -> bytes:
    """Return Modbus CRC16 serialized in little-endian order."""
    return crc16(data).to_bytes(2, "little")


def append_crc(data: bytes) -> bytes:
    return data + crc16_bytes(data)
