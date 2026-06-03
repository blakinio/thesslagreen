"""Tests for error_policy.py."""

from __future__ import annotations

from custom_components.thessla_green_modbus.error_policy import (
    is_request_cancelled_error,
    should_log_timeout_traceback,
    to_log_message,
)
from pymodbus.exceptions import ModbusIOException


def test_is_request_cancelled_true_for_request_cancelled():
    assert is_request_cancelled_error(ModbusIOException("request cancelled")) is True


def test_is_request_cancelled_true_for_cancelled_only():
    assert is_request_cancelled_error(ModbusIOException("cancelled")) is True


def test_is_request_cancelled_case_insensitive():
    assert is_request_cancelled_error(ModbusIOException("Request Cancelled")) is True


def test_is_request_cancelled_false_for_timeout():
    assert is_request_cancelled_error(ModbusIOException("timeout")) is False


def test_is_request_cancelled_false_for_connection_error():
    assert is_request_cancelled_error(ModbusIOException("connection refused")) is False


def test_should_log_timeout_traceback_true_for_timeout():
    assert should_log_timeout_traceback(RuntimeError("timeout reading registers")) is True


def test_should_log_timeout_traceback_false_for_cancelled():
    assert should_log_timeout_traceback(ModbusIOException("request cancelled")) is False


def test_should_log_timeout_traceback_false_for_cancelled_variant():
    assert should_log_timeout_traceback(RuntimeError("cancelled")) is False


def test_should_log_timeout_traceback_true_for_generic_error():
    assert should_log_timeout_traceback(OSError("connection reset")) is True


def test_to_log_message_includes_type_name():
    exc = RuntimeError("something broke")
    assert to_log_message(exc) == "RuntimeError: something broke"


def test_to_log_message_works_with_oserror():
    exc = OSError("file not found")
    assert to_log_message(exc) == "OSError: file not found"


def test_to_log_message_works_with_modbus_exception():
    exc = ModbusIOException("bad read")
    result = to_log_message(exc)
    assert "ModbusIOException" in result
    assert "bad read" in result
