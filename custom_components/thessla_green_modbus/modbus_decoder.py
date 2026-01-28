"""Decode Modbus responses into usable payloads."""

from __future__ import annotations

import logging
from typing import Any, Iterable

from .modbus_exceptions import ModbusException

_LOGGER = logging.getLogger(__name__)


class ModbusDecodeError(ModbusException):
    """Raised when a Modbus response cannot be decoded."""


def _is_error_response(response: Any) -> bool:
    """Return True when the Modbus response reports an error."""
    if response is None:
        return True
    is_error = getattr(response, "isError", None)
    if callable(is_error):
        try:
            return bool(is_error())
        except Exception as err:  # pragma: no cover - defensive
            _LOGGER.warning("Failed to inspect Modbus response: %s", err)
            return True
    return False


def decode_registers_response(response: Any) -> list[int]:
    """Return register values from a Modbus response."""
    if _is_error_response(response):
        raise ModbusDecodeError("Modbus response indicates an error")
    registers: Iterable[int] | None = getattr(response, "registers", None)
    if registers is None:
        raise ModbusDecodeError("Modbus response missing registers")
    return list(registers)


def decode_bits_response(response: Any) -> list[bool]:
    """Return coil/discrete bit values from a Modbus response."""
    if _is_error_response(response):
        raise ModbusDecodeError("Modbus response indicates an error")
    bits: Iterable[bool] | None = getattr(response, "bits", None)
    if bits is None:
        raise ModbusDecodeError("Modbus response missing bits")
    return list(bits)
