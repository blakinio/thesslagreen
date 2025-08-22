"""Utility helpers for ThesslaGreen Modbus integration."""

from __future__ import annotations

import re

__all__ = [
    "_to_snake_case",
    "_decode_register_time",
    "_decode_bcd_time",
    "parse_schedule_bcd",
    "BCD_TIME_PREFIXES",
    "TIME_REGISTER_PREFIXES",
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


def _decode_register_time(value: int) -> int | None:
    """Decode HH:MM byte-encoded value to minutes since midnight.

    The most significant byte stores the hour and the least significant byte
    stores the minute. ``None`` is returned if the value is negative or if the
    extracted hour/minute fall outside of valid ranges.
    """

    if value < 0:
        return None

    hour = (value >> 8) & 0xFF
    minute = value & 0xFF
    if 0 <= hour <= 23 and 0 <= minute <= 59:
        return hour * 60 + minute

    return None


def _decode_bcd_time(value: int) -> int | None:
    """Decode BCD or decimal HHMM values to minutes since midnight."""

    if value < 0:
        return None

    nibbles = [(value >> shift) & 0xF for shift in (12, 8, 4, 0)]
    if all(n <= 9 for n in nibbles):
        hours = nibbles[0] * 10 + nibbles[1]
        minutes = nibbles[2] * 10 + nibbles[3]
        if hours <= 23 and minutes <= 59:
            return hours * 60 + minutes

    hours_dec = value // 100
    minutes_dec = value % 100
    if 0 <= hours_dec <= 23 and 0 <= minutes_dec <= 59:
        return hours_dec * 60 + minutes_dec
    return None


def parse_schedule_bcd(value: int) -> int | None:
    """Parse schedule register values encoded as BCD HHMM.

    The schedule registers use the BCD time representation but also employ
    ``0x8000`` as a sentinel indicating that the entry is not configured.  This
    helper wraps :func:`_decode_bcd_time` and converts the sentinel to
    ``None`` while still validating the decoded time.
    """

    if value == 0x8000:
        return None
    return _decode_bcd_time(value)


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
