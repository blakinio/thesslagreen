"""Write-path encoding helpers for device-domain writes."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

_LOGGER = logging.getLogger(__name__)


def encode_write_value(
    register_name: str,
    definition: Any,
    value: float | str | list[int] | tuple[int, ...],
    offset: int,
) -> tuple[list[int] | None, Any]:
    """Encode *value* for writing. Returns (encoded_values, scalar_value).

    For multi-register definitions, returns (list[int], original_value).
    For single-register definitions, returns (None, int_value).
    Logs an error and returns (None, None) on validation failure.
    """
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
                return [int(v) for v in value], value
            except (TypeError, ValueError):
                _LOGGER.error("Register %s expects integer values", register_name)
                return None, None
        else:
            encoded = definition.encode(value)
            if isinstance(encoded, list):
                encoded_values: list[int] = [int(v) for v in encoded]
            else:
                encoded_values = [int(encoded)]
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
        return None, int(definition.encode(value))


@dataclass(slots=True)
class SingleWritePlan:
    register_name: str
    address: int
    encoded_values: list[int] | None
    scalar_value: Any
    original_value: float | str | list[int] | tuple[int, ...]
