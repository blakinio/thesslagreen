"""Tests for shared transport retry classification."""

from __future__ import annotations

from custom_components.thessla_green_modbus.errors import ThesslaGreenConfigError
from custom_components.thessla_green_modbus.modbus_exceptions import (
    ConnectionException,
    ModbusException,
    ModbusIOException,
)
from custom_components.thessla_green_modbus.transport.retry import (
    ErrorKind,
    calculate_backoff,
    classify_transport_error,
    should_retry,
)


def test_timeout_classified_as_transient_retryable() -> None:
    decision = classify_transport_error(TimeoutError("timeout"))
    assert decision.kind is ErrorKind.TRANSIENT
    assert decision.retry is True
    assert decision.reason == "timeout"


def test_connection_exception_classified_as_transient_retryable() -> None:
    decision = classify_transport_error(ConnectionException("conn"))
    assert decision.kind is ErrorKind.TRANSIENT
    assert decision.retry is True
    assert decision.reason == "connection"


def test_modbus_exception_is_permanent() -> None:
    decision = classify_transport_error(ModbusException("modbus"))
    assert decision.kind is ErrorKind.PERMANENT
    assert decision.retry is False


def test_unsupported_register_exception_is_non_retryable() -> None:
    decision = classify_transport_error(ModbusException("Illegal Data Address"))
    assert decision.kind is ErrorKind.UNSUPPORTED_REGISTER
    assert decision.retry is False
    assert decision.reason == "illegal_data_address"


def test_config_error_is_permanent_non_retryable() -> None:
    decision = classify_transport_error(ThesslaGreenConfigError("invalid cfg"))
    assert decision.kind is ErrorKind.PERMANENT
    assert decision.retry is False


def test_should_retry_respects_attempt_limit() -> None:
    decision = classify_transport_error(TimeoutError("timeout"))
    assert should_retry(decision, 1, 3) is True
    assert should_retry(decision, 3, 3) is False


def test_should_retry_does_not_retry_permanent_or_unsupported() -> None:
    permanent = classify_transport_error(ModbusException("bad frame"))
    unsupported = classify_transport_error(ModbusException("unsupported register"))
    assert should_retry(permanent, 1, 3) is False
    assert should_retry(unsupported, 1, 3) is False


def test_calculate_backoff_respects_base_max_and_jitter() -> None:
    no_jitter = calculate_backoff(attempt=3, base=0.5, max_backoff=10.0, jitter=None)
    assert no_jitter == 2.0

    bounded = calculate_backoff(attempt=6, base=1.0, max_backoff=4.0, jitter=0.5)
    assert 0.0 <= bounded <= 4.0


def test_cancelled_modbus_io_maps_to_transient_cancelled_reason() -> None:
    decision = classify_transport_error(ModbusIOException("request cancelled outside pymodbus"))
    assert decision.kind is ErrorKind.TRANSIENT
    assert decision.retry is True
    assert decision.reason == "cancelled"
