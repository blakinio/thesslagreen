"""Custom exceptions for ThesslaGreen Modbus Integration."""
from __future__ import annotations

from homeassistant.exceptions import HomeAssistantError


class ThesslaGreenError(HomeAssistantError):
    """Base exception for ThesslaGreen integration."""


class ThesslaGreenConnectionError(ThesslaGreenError):
    """Exception for connection errors."""


class ThesslaGreenTimeoutError(ThesslaGreenError):
    """Exception for timeout errors."""


class ThesslaGreenAuthenticationError(ThesslaGreenError):
    """Exception for authentication errors."""


class ThesslaGreenDataError(ThesslaGreenError):
    """Exception for data parsing errors."""


class ThesslaGreenModbusError(ThesslaGreenError):
    """Exception for Modbus communication errors."""