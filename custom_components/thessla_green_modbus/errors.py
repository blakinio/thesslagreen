"""Shared errors and helpers for the ThesslaGreen Modbus integration."""

from __future__ import annotations


class CannotConnect(Exception):
    """Error to indicate we cannot connect."""


class InvalidAuth(Exception):
    """Error to indicate there is invalid auth."""


def is_invalid_auth_error(exc: Exception) -> bool:
    """Check if exception message hints invalid authentication."""

    message = str(exc).lower()
    return any(token in message for token in ("auth", "credential", "password", "login"))
