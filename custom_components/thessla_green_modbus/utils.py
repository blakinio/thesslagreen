"""Utility helpers for ThesslaGreen Modbus integration."""

from __future__ import annotations

import re

__all__ = [
    "_to_snake_case",
    "_normalise_name",
    "_decode_register_time",
    "_decode_bcd_time",
    "_decode_aatt",
    "BCD_TIME_PREFIXES",
    "TIME_REGISTER_PREFIXES",
    "decode_int16",
    "decode_temp_01c",
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

    if value == 32768 or value < 0:
        return None

    nibbles = [(value >> shift) & 15 for shift in (12, 8, 4, 0)]
    if all(n <= 9 for n in nibbles):
        hours = nibbles[0] * 10 + nibbles[1]
        minutes = nibbles[2] * 10 + nibbles[3]
        if hours == 24 and minutes == 0:
            return 0
        if hours <= 23 and minutes <= 59:
            return hours * 60 + minutes

    hours_dec = value // 100
    minutes_dec = value % 100
    if 0 <= hours_dec <= 23 and 0 <= minutes_dec <= 59:
        return hours_dec * 60 + minutes_dec
    return None


def _decode_aatt(value: int) -> tuple[int, float] | None:
    """Decode airflow percentage and temperature encoded as ``0xAATT``."""

    if value == 32768 or value < 0:
        return None

    airflow = (value >> 8) & 255
    temp_double = value & 255

    if airflow > 100 or temp_double > 200:
        return None

    return airflow, temp_double / 2


# Registers storing times as BCD HHMM values
BCD_TIME_PREFIXES: tuple[str, ...] = (
    "schedule_",
    "airing_summer_",
    "airing_winter_",
    "pres_check_time",
    "start_gwc_regen",
    "stop_gwc_regen",
)

# All registers storing times; used for generic time validation
TIME_REGISTER_PREFIXES: tuple[str, ...] = BCD_TIME_PREFIXES + ("manual_airing_time_to_start",)


def decode_int16(u16: int) -> int:
    """Decode an unsigned 16-bit value as signed."""
    return u16 - 65536 if u16 >= 32768 else u16


def decode_temp_01c(u16: int) -> float | None:
    """Decode temperature in 0.1°C resolution, handling missing values."""
    if u16 == 32768:
        return None
    return decode_int16(u16) / 10
