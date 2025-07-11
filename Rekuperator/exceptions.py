"""Custom exceptions for TeslaGreen Modbus Integration."""
from __future__ import annotations

from homeassistant.exceptions import HomeAssistantError


class TeslaGreenError(HomeAssistantError):
    """Base exception for TeslaGreen integration."""


class TeslaGreenConnectionError(TeslaGreenError):
    """Exception for connection errors."""


class TeslaGreenTimeoutError(TeslaGreenError):
    """Exception for timeout errors."""


class TeslaGreenAuthenticationError(TeslaGreenError):
    """Exception for authentication errors."""


class TeslaGreenDataError(TeslaGreenError):
    """Exception for data parsing errors."""


class TeslaGreenModbusError(TeslaGreenError):
    """Exception for Modbus communication errors."""
