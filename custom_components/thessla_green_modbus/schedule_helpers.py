"""Helpers for encoding/decoding BCD schedule times."""

from __future__ import annotations

from datetime import time

from .utils import decode_bcd_time, encode_bcd_time


def time_to_bcd(t: time) -> int:
    """Convert ``datetime.time`` to BCD encoded HHMM value."""

    return encode_bcd_time(t)


def bcd_to_time(value: int) -> time:
    """Convert BCD encoded HHMM value to ``datetime.time``."""

    decoded = decode_bcd_time(value)
    if decoded is None:
        raise ValueError("Invalid or disabled BCD time value")
    return decoded
