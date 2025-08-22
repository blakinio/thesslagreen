"""Helpers for encoding/decoding BCD schedule times."""
from __future__ import annotations

from datetime import time


def _int_to_bcd(value: int) -> int:
    return ((value // 10) << 4) | (value % 10)


def _bcd_to_int(value: int) -> int:
    return ((value >> 4) & 0xF) * 10 + (value & 0xF)


def time_to_bcd(t: time) -> int:
    """Convert ``datetime.time`` to BCD encoded HHMM value."""
    return (_int_to_bcd(t.hour) << 8) | _int_to_bcd(t.minute)


def bcd_to_time(value: int) -> time:
    """Convert BCD encoded HHMM value to ``datetime.time``."""
    hour = _bcd_to_int(value >> 8)
    minute = _bcd_to_int(value & 0xFF)
    return time(hour, minute)
