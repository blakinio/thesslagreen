"""Tests for domain error classes."""

from __future__ import annotations

from custom_components.thessla_green_modbus.errors import (
    CannotConnect,
    ThesslaGreenConfigError,
    ThesslaGreenError,
    TransportUnavailableError,
    UnsupportedRegisterError,
    is_invalid_auth_error,
)


def test_domain_error_hierarchy() -> None:
    assert issubclass(ThesslaGreenConfigError, ThesslaGreenError)
    assert issubclass(TransportUnavailableError, ThesslaGreenError)
    assert issubclass(CannotConnect, TransportUnavailableError)
    assert issubclass(UnsupportedRegisterError, ThesslaGreenError)


def test_invalid_auth_message_detection() -> None:
    assert is_invalid_auth_error(Exception("Invalid password"))
    assert not is_invalid_auth_error(Exception("socket timeout"))

