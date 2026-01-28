"""Helpers for encoding/decoding BCD schedule times."""

from __future__ import annotations

from datetime import time

from .utils import _decode_bcd_time

_BCD_DISABLED_VALUES = {32768, 65535}


def _int_to_bcd(value: int) -> int:
    return ((value // 10) << 4) | (value % 10)


def _bcd_to_int(value: int) -> int:
    return ((value >> 4) & 15) * 10 + (value & 15)


def time_to_bcd(t: time) -> int:
    """Convert ``datetime.time`` to BCD encoded HHMM value."""
    return (_int_to_bcd(t.hour) << 8) | _int_to_bcd(t.minute)


def bcd_to_time(value: int) -> time:
    """Convert BCD encoded HHMM value to ``datetime.time``."""
    hour = _bcd_to_int(value >> 8)
    minute = _bcd_to_int(value & 255)
    return time(hour, minute)


def decode_bcd_time(value: int) -> time | None:
    """Decode a BCD HHMM register to ``datetime.time``.

    Returns ``None`` for disabled or malformed values.
    """
    if value in _BCD_DISABLED_VALUES:
        return None
    minutes = _decode_bcd_time(value)
    if minutes is None:
        return None
    return time(minutes // 60, minutes % 60)


def encode_bcd_time(value: time) -> int:
    """Encode ``datetime.time`` to a BCD HHMM register value."""
    return time_to_bcd(value)
