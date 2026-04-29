# mypy: ignore-errors
"""Pure helper tests for modbus transport.

Transport-specific behavior has been split into focused modules:
- test_modbus_transport_tcp.py
- test_modbus_transport_retry.py
- test_modbus_transport_lifecycle.py
- test_modbus_transport_errors.py
"""

from custom_components.thessla_green_modbus.modbus_transport import (
    RawModbusResponse,
    RawModbusWriteResponse,
    _append_crc,
    _crc16,
)


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
    assert _crc16(b"") == 0xFFFF


def test_append_crc_appends_two_bytes():
    data = bytes([1, 2, 3])
    result = _append_crc(data)
    assert len(result) == len(data) + 2
