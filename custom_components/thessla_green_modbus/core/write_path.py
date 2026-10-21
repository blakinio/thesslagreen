"""Write-path encoding helpers for device-domain writes."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

_LOGGER = logging.getLogger(__name__)


def encode_write_value(
    register_name: str,
    definition: Any,
    value: float | str | dict[str, Any] | list[int] | tuple[int, ...],
    offset: int,
) -> tuple[list[int] | None, Any]:
    """Encode *value* for writing. Returns (encoded_values, scalar_value).

    For multi-register definitions, returns (list[int], original_value).
    For single-register definitions, returns (None, int_value).
    Logs an error and returns (None, None) on validation failure.
    """
    if offset < 0 or offset >= definition.length:
        _LOGGER.error("Invalid register offset %s for %s", offset, register_name)
        return None, None
    if definition.length > 1:
        if isinstance(value, list | tuple) and not isinstance(value, bytes | bytearray | str):
            if len(value) + offset > definition.length:
                _LOGGER.error(
                    "Register %s expects at most %d values starting at offset %d",
                    register_name,
                    definition.length - offset,
                    offset,
                )
                return None, None
            if offset == 0 and len(value) != definition.length:
                _LOGGER.error(
                    "Register %s requires exactly %d values",
                    register_name,
                    definition.length,
                )
                return None, None
            try:
                return _checked_words(value), value
            except (TypeError, ValueError):
                _LOGGER.error("Register %s expects integer values", register_name)
                return None, None
        else:
            encoded = definition.encode(value)
            if isinstance(encoded, list):
                encoded_values: list[int] = _checked_words(encoded)
            else:
                encoded_values = _checked_words([encoded])
            if offset >= definition.length:
                _LOGGER.error(
                    "Register %s expects at most %d values starting at offset %d",
                    register_name,
                    definition.length - offset,
                    offset,
                )
                return None, None
            return encoded_values[offset:], value
    else:
        if isinstance(value, list | tuple) and not isinstance(value, bytes | bytearray | str):
            _LOGGER.error("Register %s expects a single value", register_name)
            return None, None
        return None, _checked_words([definition.encode(value)])[0]


def _checked_words(values: Any) -> list[int]:
    """Validate rather than truncate/wrap raw Modbus register words."""
    result = []
    for value in values:
        if isinstance(value, bool) or int(value) != value or not 0 <= value <= 0xFFFF:
            raise ValueError(f"Invalid 16-bit Modbus register value: {value!r}")
        result.append(int(value))
    return result


@dataclass(slots=True)
class SingleWritePlan:
    register_name: str
    address: int
    encoded_values: list[int] | None
    scalar_value: Any
    original_value: float | str | dict[str, Any] | list[int] | tuple[int, ...]


def validate_holding_write_span(start: int, values: list[int], definitions: Any) -> None:
    """Check raw FC16 addresses/words before any transport operation."""
    _checked_words(values)
    if (
        not values
        or not isinstance(start, int)
        or isinstance(start, bool)
        or start < 0
        or start + len(values) > 0x10000
    ):
        raise ValueError("Invalid holding-register address span")
    writable = {
        address
        for definition in definitions
        if definition.function == 3 and "W" in definition.access.upper()
        for address in range(definition.address, definition.address + definition.length)
    }
    if not all(address in writable for address in range(start, start + len(values))):
        raise ValueError("Raw write includes an unknown/read-only holding register")
