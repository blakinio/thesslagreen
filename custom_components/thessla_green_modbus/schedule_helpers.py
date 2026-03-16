"""Helpers for encoding/decoding BCD schedule times."""

from __future__ import annotations

from datetime import time

from .utils import decode_bcd_time, encode_bcd_time

# Mapping of "HH:MM" label → "HH:MM" value for every 30-minute slot.
# Used as the ``states`` dict for select entities backed by BCD time registers.
# The coordinator stores decoded "HH:MM" strings for these registers, so both
# key and value are strings; the register loader's encode() handles the
# string → BCD int conversion when writing.
TIME_SELECT_STATES: dict[str, str] = {
    f"{h:02d}:{m:02d}": f"{h:02d}:{m:02d}"
    for h in range(24)
    for m in (0, 30)
}

# Prefixes for schedule intensity/airflow setting registers.
SETTING_SCHEDULE_PREFIXES: tuple[str, ...] = ("setting_summer_", "setting_winter_")

# Mapping of "0%" … "100%" labels → integer values for schedule intensity
# select entities (step 10 %).
PERCENT_10_SELECT_STATES: dict[str, int] = {
    f"{pct}%": pct for pct in range(0, 101, 10)
}


def time_to_bcd(t: time) -> int:
    """Convert ``datetime.time`` to BCD encoded HHMM value."""

    return encode_bcd_time(t)


def bcd_to_time(value: int) -> time:
    """Convert BCD encoded HHMM value to ``datetime.time``."""

    decoded = decode_bcd_time(value)
    if decoded is None:
        raise ValueError("Invalid or disabled BCD time value")
    hours, minutes = (int(part) for part in decoded.split(":", 1))
    return time(hours, minutes)
