"""Utility helpers for ThesslaGreen Modbus integration."""

from __future__ import annotations

import re
from datetime import time


__all__ = [
    "_to_snake_case",
    "_normalise_name",
    "_decode_register_time",
    "_decode_bcd_time",
    "_decode_aatt",
    "BCD_TIME_PREFIXES",
    "TIME_REGISTER_PREFIXES",
    "default_connection_mode",
    "decode_int16",
    "decode_temp_01c",
    "decode_bcd_time",
    "decode_aatt",
    "encode_bcd_time",
    "resolve_connection_settings",
]


def _to_snake_case(name: str) -> str:
    """Convert register names to snake_case."""
    replacements = {"flowrate": "flow_rate"}
    for old, new in replacements.items():
        name = name.replace(old, new)
    name = re.sub(r"[\s\-/]", "_", name)
    name = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", name)
    name = re.sub(r"(?<=\D)(\d)", r"_\1", name)
    name = re.sub(r"__+", "_", name)
    name = name.lower()
    token_map = {"temp": "temperature"}
    tokens = [token_map.get(token, token) for token in name.split("_")]
    return "_".join(tokens)


def _normalise_name(name: str) -> str:
    """Convert register names to ``snake_case`` and fix known typos."""
    fixes = {
        "duct_warter_heater_pump": "duct_water_heater_pump",
        "required_temp": "required_temperature",
        "specialmode": "special_mode",
    }
    snake = _to_snake_case(name)
    return fixes.get(snake, snake)


def _decode_register_time(value: int) -> int | None:
    """Decode HH:MM byte-encoded value to minutes since midnight.

    The most significant byte stores the hour and the least significant byte
    stores the minute. ``None`` is returned if the value is negative or if the
    extracted hour/minute fall outside of valid ranges.
    """

    if value == 32768 or value < 0:
        return None

    hour = (value >> 8) & 255
    minute = value & 255
    if 0 <= hour <= 23 and 0 <= minute <= 59:
        return hour * 60 + minute

    return None


def _decode_bcd_time(value: int) -> int | None:
    """Decode BCD or decimal HHMM values to minutes since midnight."""

    decoded = _decode_bcd_time_to_time(value)
    if decoded is None:
        return None
    return decoded.hour * 60 + decoded.minute


def decode_int16(u16: int) -> int:
    """Decode a 16-bit unsigned value into a signed integer."""

    if u16 & 32768:
        return u16 - 65536
    return u16


def decode_temp_01c(u16: int) -> float | None:
    """Decode temperature scaled in 0.1°C with 32768 meaning invalid."""

    if u16 == 32768:
        return None
    return decode_int16(u16) / 10


def _decode_bcd_time_to_time(value: int) -> time | None:
    """Decode BCD or decimal HHMM values to ``datetime.time``."""

    if value in (32768, 65535) or value < 0:
        return None

    nibbles = [(value >> shift) & 15 for shift in (12, 8, 4, 0)]
    if all(n <= 9 for n in nibbles):
        hours = nibbles[0] * 10 + nibbles[1]
        minutes = nibbles[2] * 10 + nibbles[3]
        if hours == 24 and minutes == 0:
            return time(0, 0)
        if 0 <= hours <= 23 and 0 <= minutes <= 59:
            return time(hours, minutes)

    hours_dec = value // 100
    minutes_dec = value % 100
    if hours_dec == 24 and minutes_dec == 0:
        return time(0, 0)
    if 0 <= hours_dec <= 23 and 0 <= minutes_dec <= 59:
        return time(hours_dec, minutes_dec)
    return None


def decode_bcd_time(value: int) -> str | None:
    """Decode BCD or decimal HHMM values to ``HH:MM`` strings.

    Returns ``None`` for disabled/invalid values as defined by the Modbus spec.
    """

    decoded = _decode_bcd_time_to_time(value)
    if decoded is None:
        return None
    return f"{decoded.hour:02d}:{decoded.minute:02d}"


def encode_bcd_time(value: time) -> int:
    """Encode ``datetime.time`` into a BCD HHMM value."""

    def _int_to_bcd(val: int) -> int:
        return ((val // 10) << 4) | (val % 10)

    return (_int_to_bcd(value.hour) << 8) | _int_to_bcd(value.minute)


def _decode_aatt(value: int) -> dict[str, float | int] | None:
    """Decode airflow percentage and temperature encoded as ``AATT``."""

    if value == 32768 or value < 0:
        return None

    airflow = (value >> 8) & 255
    temp_double = value & 255

    if airflow > 150 or temp_double > 200:
        return None

    return {"airflow_pct": airflow, "temp_c": temp_double / 2}


def decode_aatt(value: int) -> dict[str, float | int] | None:
    """Decode airflow percentage and temperature encoded as ``AATT``."""

    return _decode_aatt(value)


def default_connection_mode(port: int | None) -> str:
    """Return the default TCP connection mode for config defaults."""

    from .const import CONNECTION_MODE_AUTO

    return CONNECTION_MODE_AUTO


def resolve_connection_settings(
    connection_type: str | None,
    connection_mode: str | None,
    port: int | None,
) -> tuple[str, str | None]:
    """Resolve connection type/mode with legacy handling and defaults."""

    from .const import (
        CONNECTION_MODE_AUTO,
        CONNECTION_MODE_TCP,
        CONNECTION_MODE_TCP_RTU,
        CONNECTION_TYPE_RTU,
        CONNECTION_TYPE_TCP,
        CONNECTION_TYPE_TCP_RTU,
        DEFAULT_CONNECTION_TYPE,
    )

    conn_type = (connection_type or DEFAULT_CONNECTION_TYPE).lower()
    if conn_type == CONNECTION_TYPE_RTU:
        return CONNECTION_TYPE_RTU, None

    if conn_type == CONNECTION_TYPE_TCP_RTU:
        conn_type = CONNECTION_TYPE_TCP
        if connection_mode is None:
            connection_mode = CONNECTION_MODE_TCP_RTU

    if conn_type != CONNECTION_TYPE_TCP:
        conn_type = DEFAULT_CONNECTION_TYPE

    if connection_mode in (CONNECTION_MODE_TCP, CONNECTION_MODE_TCP_RTU, CONNECTION_MODE_AUTO):
        return CONNECTION_TYPE_TCP, connection_mode

    return CONNECTION_TYPE_TCP, default_connection_mode(port)


# Registers storing times as BCD HHMM values
BCD_TIME_PREFIXES: tuple[str, ...] = (
    "schedule_",
    "airing_summer_",
    "airing_winter_",
    "pres_check_time",
    "start_gwc_regen",
    "stop_gwc_regen",
    "manual_airing_time_to_start",
)

# All registers storing times; used for generic time validation
TIME_REGISTER_PREFIXES: tuple[str, ...] = BCD_TIME_PREFIXES
