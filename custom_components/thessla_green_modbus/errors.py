"""Shared errors and helpers for the ThesslaGreen Modbus integration."""

from __future__ import annotations


class ThesslaGreenError(Exception):
    """Base integration exception."""


class ThesslaGreenConfigError(ThesslaGreenError):
    """Raised for invalid configuration/data."""


class ThesslaGreenProtocolError(ThesslaGreenError):
    """Raised for protocol-level errors."""


class UnsupportedRegisterError(ThesslaGreenProtocolError):
    """Raised when device reports unsupported/illegal register address."""


class TransportUnavailableError(ThesslaGreenError):
    """Raised when transport is unavailable."""


class CannotConnect(TransportUnavailableError):
    """Error to indicate we cannot connect."""


class InvalidAuth(ThesslaGreenConfigError):
    """Error to indicate there is invalid auth."""


def is_invalid_auth_error(exc: Exception) -> bool:
    """Check if exception message hints invalid authentication."""

    message = str(exc).lower()
    return any(token in message for token in ("auth", "credential", "password", "login"))
