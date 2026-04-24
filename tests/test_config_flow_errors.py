"""Tests for config-flow specific error helpers."""

from __future__ import annotations

import socket

from custom_components.thessla_green_modbus import config_flow_errors


def test_classify_os_error_dns_failure() -> None:
    """socket.gaierror should map to dns_failure."""
    assert config_flow_errors.classify_os_error(socket.gaierror("dns")) == "dns_failure"


def test_classify_os_error_connection_refused() -> None:
    """ConnectionRefusedError should map to connection_refused."""
    assert (
        config_flow_errors.classify_os_error(ConnectionRefusedError("refused"))
        == "connection_refused"
    )


def test_classify_os_error_fallback() -> None:
    """Unhandled OSError variants should map to cannot_connect."""
    assert config_flow_errors.classify_os_error(OSError("other")) == "cannot_connect"


def test_should_log_timeout_traceback_for_cancelled_message() -> None:
    """Cancelled timeout messages should not trigger traceback logging."""
    assert (
        config_flow_errors.should_log_timeout_traceback(TimeoutError("request cancelled")) is False
    )


def test_should_log_timeout_traceback_for_regular_timeout() -> None:
    """Regular timeout messages should trigger traceback logging."""
    assert config_flow_errors.should_log_timeout_traceback(TimeoutError("timed out")) is True
