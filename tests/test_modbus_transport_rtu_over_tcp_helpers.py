"""Tests for transport RTU-over-TCP framing helpers."""

from __future__ import annotations

import pytest
from custom_components.thessla_green_modbus.transport.crc import append_crc, crc16, crc16_bytes
from custom_components.thessla_green_modbus.transport.rtu_over_tcp import (
    build_read_frame,
    validate_crc,
)


def test_crc16_and_bytes_use_little_endian() -> None:
    payload = bytes([0x01, 0x04, 0x00, 0x64, 0x00, 0x02])
    crc_value = crc16(payload)

    assert crc16_bytes(payload) == crc_value.to_bytes(2, "little")
    assert append_crc(payload) == payload + crc16_bytes(payload)


def test_validate_crc_accepts_valid_frame_crc() -> None:
    payload = bytes([0x0A, 0x04, 0x02, 0x12, 0x34])

    validate_crc(payload, crc16_bytes(payload))


def test_validate_crc_rejects_malformed_crc_bytes() -> None:
    payload = bytes([0x0A, 0x04, 0x02, 0x12, 0x34])

    with pytest.raises(ValueError, match="CRC mismatch"):
        validate_crc(payload, b"\x00\x00")


def test_build_read_frame_wires_payload_and_crc() -> None:
    frame = build_read_frame(0x11, 0x04, 0x0064, 0x000A)

    assert frame[:6] == bytes([0x11, 0x04, 0x00, 0x64, 0x00, 0x0A])
    assert frame[6:] == crc16_bytes(frame[:6])
