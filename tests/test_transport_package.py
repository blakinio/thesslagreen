"""Canonical transport package integration tests.

Proves that transport/ is the authoritative source and that:
- BaseModbusTransport comes from transport.base
- Raw response classes live in transport.raw and behave correctly
- TcpModbusTransport and RtuModbusTransport can be instantiated from transport.*
"""

from __future__ import annotations

from custom_components.thessla_green_modbus.transport.base import BaseModbusTransport
from custom_components.thessla_green_modbus.transport.crc import append_crc, crc16
from custom_components.thessla_green_modbus.transport.raw import (
    _MAX_READ_REGISTERS,
    _MAX_SLAVE_ID,
    _MAX_WRITE_REGISTERS,
    _MIN_SLAVE_ID,
    RawModbusResponse,
    RawModbusWriteResponse,
)
from custom_components.thessla_green_modbus.transport.retry import (
    ErrorKind,
    classify_transport_error,
)
from custom_components.thessla_green_modbus.transport.rtu import RtuModbusTransport
from custom_components.thessla_green_modbus.transport.tcp import (
    TcpModbusTransport,
    _ClientBackedTransport,
)
from custom_components.thessla_green_modbus.transport.tcp_rtu import RawRtuOverTcpTransport

# ---------------------------------------------------------------------------
# Canonical class identity
# ---------------------------------------------------------------------------


def test_tcp_transport_inherits_canonical_base():
    assert issubclass(TcpModbusTransport, BaseModbusTransport)


def test_rtu_transport_inherits_client_backed_transport():
    assert issubclass(RtuModbusTransport, _ClientBackedTransport)
    assert issubclass(RtuModbusTransport, BaseModbusTransport)


def test_raw_rtu_over_tcp_inherits_canonical_base():
    assert issubclass(RawRtuOverTcpTransport, BaseModbusTransport)


# ---------------------------------------------------------------------------
# RawModbusResponse / RawModbusWriteResponse
# ---------------------------------------------------------------------------


def test_raw_modbus_response_is_error_false():
    assert RawModbusResponse([1, 2, 3]).isError() is False


def test_raw_modbus_response_empty_registers():
    assert RawModbusResponse().registers == []


def test_raw_modbus_write_response_is_error_false():
    assert RawModbusWriteResponse().isError() is False


# ---------------------------------------------------------------------------
# Protocol constants
# ---------------------------------------------------------------------------


def test_constants_have_correct_values():
    assert _MIN_SLAVE_ID == 1
    assert _MAX_SLAVE_ID == 247
    assert _MAX_READ_REGISTERS == 125
    assert _MAX_WRITE_REGISTERS == 123


# ---------------------------------------------------------------------------
# CRC helpers
# ---------------------------------------------------------------------------


def test_crc16_empty_payload_is_0xffff():
    assert crc16(b"") == 0xFFFF


def test_append_crc_adds_two_bytes():
    data = b"\x01\x02\x03"
    result = append_crc(data)
    assert len(result) == len(data) + 2


# ---------------------------------------------------------------------------
# TCP transport instantiation
# ---------------------------------------------------------------------------


def test_tcp_transport_instantiates():
    t = TcpModbusTransport(
        host="127.0.0.1",
        port=502,
        max_retries=1,
        base_backoff=0.0,
        max_backoff=0.0,
        timeout=1.0,
    )
    assert t.host == "127.0.0.1"
    assert t.port == 502
    assert not t.is_connected()


# ---------------------------------------------------------------------------
# Raw RTU-over-TCP transport instantiation
# ---------------------------------------------------------------------------


def test_raw_rtu_over_tcp_instantiates():
    t = RawRtuOverTcpTransport(
        host="10.0.0.1",
        port=502,
        max_retries=1,
        base_backoff=0.0,
        max_backoff=0.0,
        timeout=1.0,
    )
    assert t.host == "10.0.0.1"
    assert not t.is_connected()


# ---------------------------------------------------------------------------
# Error classification
# ---------------------------------------------------------------------------


def test_timeout_classified_transient():
    decision = classify_transport_error(TimeoutError("t/o"))
    assert decision.kind is ErrorKind.TRANSIENT
    assert decision.retry is True
