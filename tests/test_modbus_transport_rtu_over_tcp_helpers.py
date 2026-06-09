"""Tests for RTU-over-TCP framing helpers on the production transport."""

from __future__ import annotations

import importlib

import pytest
from custom_components.thessla_green_modbus.transport.crc import append_crc, crc16, crc16_bytes
from custom_components.thessla_green_modbus.transport.tcp_rtu import RawRtuOverTcpTransport
from pymodbus.exceptions import ModbusIOException


def test_crc16_and_bytes_use_little_endian() -> None:
    payload = bytes([0x01, 0x04, 0x00, 0x64, 0x00, 0x02])
    crc_value = crc16(payload)

    assert crc16_bytes(payload) == crc_value.to_bytes(2, "little")
    assert append_crc(payload) == payload + crc16_bytes(payload)


def test_validate_crc_accepts_valid_frame_crc() -> None:
    payload = bytes([0x0A, 0x04, 0x02, 0x12, 0x34])

    RawRtuOverTcpTransport._validate_crc(payload, crc16_bytes(payload))


def test_validate_crc_rejects_malformed_crc_bytes() -> None:
    payload = bytes([0x0A, 0x04, 0x02, 0x12, 0x34])

    with pytest.raises(ModbusIOException, match="CRC mismatch"):
        RawRtuOverTcpTransport._validate_crc(payload, b"\x00\x00")


def test_build_read_frame_wires_payload_and_crc() -> None:
    frame = RawRtuOverTcpTransport._build_read_frame(0x11, 0x04, 0x0064, 0x000A)

    assert frame[:6] == bytes([0x11, 0x04, 0x00, 0x64, 0x00, 0x0A])
    assert frame[6:] == crc16_bytes(frame[:6])


def test_rtu_over_tcp_dead_module_does_not_exist() -> None:
    """Guard: dead helper module must not be reintroduced."""
    with pytest.raises((ImportError, ModuleNotFoundError)):
        importlib.import_module("custom_components.thessla_green_modbus.transport.rtu_over_tcp")
