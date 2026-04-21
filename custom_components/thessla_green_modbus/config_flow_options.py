"""Normalization helpers for config flow option values."""

from __future__ import annotations

from typing import Any

from .const import DOMAIN


def strip_translation_prefix(value: str) -> str:
    """Remove integration/domain prefixes from option strings."""
    if value.startswith(f"{DOMAIN}."):
        value = value.split(".", 1)[1]
    return value


def normalize_baud_rate(value: Any) -> int:
    """Normalize a Modbus baud rate option to an integer."""
    if isinstance(value, int):
        if value <= 0:
            raise ValueError("invalid_baud_rate")
        return value
    if not isinstance(value, str):
        raise ValueError("invalid_baud_rate")
    option = strip_translation_prefix(value.strip())
    if option.startswith("modbus_baud_rate_"):
        option = option[len("modbus_baud_rate_") :]
    try:
        baud = int(option)
    except (TypeError, ValueError) as err:
        raise ValueError("invalid_baud_rate") from err
    if baud <= 0:
        raise ValueError("invalid_baud_rate")
    return baud


def normalize_parity(value: Any) -> str:
    """Normalize a parity option to one of ``none/even/odd``."""
    if not isinstance(value, str):
        if value is None:
            raise ValueError("invalid_parity")
        value = str(value)
    option = strip_translation_prefix(value.strip().lower())
    if option.startswith("modbus_parity_"):
        option = option[len("modbus_parity_") :]
    if option not in {"none", "even", "odd"}:
        raise ValueError("invalid_parity")
    return option


def normalize_stop_bits(value: Any) -> int:
    """Normalize stop bits option to integer 1 or 2."""
    if isinstance(value, int):
        stop_bits = value
    elif isinstance(value, str):
        option = strip_translation_prefix(value.strip())
        if option.startswith("modbus_stop_bits_"):
            option = option[len("modbus_stop_bits_") :]
        try:
            stop_bits = int(option)
        except (TypeError, ValueError) as err:
            raise ValueError("invalid_stop_bits") from err
    else:
        raise ValueError("invalid_stop_bits")

    if stop_bits not in {1, 2}:
        raise ValueError("invalid_stop_bits")
    return stop_bits


def denormalize_option(prefix: str, value: Any | None) -> Any | None:
    """Translate internal option value to translation-key token."""
    if value is None:
        return None
    if isinstance(value, str) and value.startswith(f"{DOMAIN}."):
        return value
    return f"{DOMAIN}.{prefix}{value}"
