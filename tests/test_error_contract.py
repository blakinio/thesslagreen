"""Cross-layer tests for shared retry/error classification contract."""

from __future__ import annotations

import logging

import pytest
from custom_components.thessla_green_modbus.error_contract import classify_error
from custom_components.thessla_green_modbus.modbus_exceptions import (
    ConnectionException,
    ModbusException,
    ModbusIOException,
)


def test_classify_error_transient_vs_permanent() -> None:
    assert classify_error(TimeoutError()).kind == "transient"
    assert classify_error(ModbusIOException("io")).kind == "transient"
    assert classify_error(ConnectionException("conn")).kind == "transient"
    assert classify_error(OSError("os")).kind == "transient"
    assert classify_error(ModbusException("modbus")).kind == "permanent"


def test_classify_error_reasons() -> None:
    assert classify_error(TimeoutError()).reason == "timeout"
    assert (
        classify_error(ModbusIOException("request cancelled outside pymodbus")).reason
        == "cancelled"
    )
    assert classify_error(ConnectionException("x")).reason == "connection"


def test_cross_layer_classification_contract() -> None:
    from custom_components.thessla_green_modbus._coordinator_retry import classify_retry_error
    from custom_components.thessla_green_modbus.scanner.io_runtime import classify_scanner_error

    transport_module = pytest.importorskip(
        "custom_components.thessla_green_modbus.modbus_transport"
    )
    classify_transport_error = transport_module.classify_transport_error

    exc = ModbusIOException("temporary failure")
    expected = classify_error(exc)

    assert classify_retry_error(exc) == (expected.kind, expected.reason)
    assert classify_scanner_error(exc) == (expected.kind, expected.reason)
    assert classify_transport_error(exc) == (expected.kind, expected.reason)


def test_cross_layer_retry_logging_contract(caplog: pytest.LogCaptureFixture) -> None:
    from custom_components.thessla_green_modbus._coordinator_retry import log_coordinator_retry
    from custom_components.thessla_green_modbus._transport_retry import log_transport_retry
    from custom_components.thessla_green_modbus.scanner.io_runtime import log_scanner_retry

    caplog.set_level("WARNING")
    exc = TimeoutError("boom")

    log_coordinator_retry(
        operation="read:holding:100",
        attempt=1,
        max_attempts=3,
        exc=exc,
        backoff=0.2,
    )
    log_scanner_retry(
        operation="read_input:100-104",
        attempt=1,
        max_attempts=3,
        exc=exc,
        backoff=0.2,
    )
    log_transport_retry(
        logger=logging.getLogger("custom_components.thessla_green_modbus.modbus_transport"),
        operation="timeout",
        attempt=1,
        max_attempts=3,
        exc=exc,
        base_backoff=0.2,
    )

    messages = [record.getMessage() for record in caplog.records]
    assert any(
        "layer=coordinator" in message and "reason=timeout" in message for message in messages
    )
    assert any("layer=scanner" in message and "reason=timeout" in message for message in messages)
    assert any("layer=transport" in message and "reason=timeout" in message for message in messages)


@pytest.mark.parametrize(
    ("exc", "expected_kind", "expected_reason"),
    [
        (TimeoutError(), "transient", "timeout"),
        (ModbusIOException("request cancelled outside pymodbus"), "transient", "cancelled"),
        (ConnectionException("conn"), "transient", "connection"),
        (ModbusException("hard fail"), "permanent", "modbus"),
    ],
)
def test_cross_layer_classification_contract_matrix(
    exc: BaseException, expected_kind: str, expected_reason: str
) -> None:
    from custom_components.thessla_green_modbus._coordinator_retry import classify_retry_error
    from custom_components.thessla_green_modbus.scanner.io_runtime import classify_scanner_error

    transport_module = pytest.importorskip(
        "custom_components.thessla_green_modbus.modbus_transport"
    )
    classify_transport_error = transport_module.classify_transport_error

    expected = classify_error(exc)
    assert (expected.kind, expected.reason) == (expected_kind, expected_reason)
    assert classify_retry_error(exc) == (expected_kind, expected_reason)
    assert classify_scanner_error(exc) == (expected_kind, expected_reason)
    assert classify_transport_error(exc) == (expected_kind, expected_reason)
