"""Helper utilities for ThesslaGreen Modbus device scanning."""

from __future__ import annotations

from typing import Callable, Dict, Optional

from .const import SENSOR_UNAVAILABLE, MAX_BATCH_REGISTERS
from .utils import (
    BCD_TIME_PREFIXES,
    TIME_REGISTER_PREFIXES,
    _decode_aatt,
    _decode_bcd_time,
    _decode_register_time,
)

# Specific registers may only accept discrete values
REGISTER_ALLOWED_VALUES: dict[str, set[int]] = {
    "mode": {0, 1, 2},
    "season_mode": {0, 1},
    "special_mode": set(range(0, 12)),
    "antifreeze_mode": {0, 1},
}

# Registers storing combined airflow and temperature settings
SETTING_PREFIX = "setting_"


def _format_register_value(name: str, value: int) -> int | str | None:
    """Return a human-readable representation of a register value."""
    if name == "manual_airing_time_to_start":
        raw_value = value
        value = ((value & 0xFF) << 8) | ((value >> 8) & 0xFF)
        decoded = _decode_register_time(value)
        if decoded is None:
            return None if raw_value == SENSOR_UNAVAILABLE else f"0x{raw_value:04X} (invalid)"
        return f"{decoded // 60:02d}:{decoded % 60:02d}"

    if name.startswith(BCD_TIME_PREFIXES):
        decoded = _decode_bcd_time(value)
        if decoded is None:
            return None if value == SENSOR_UNAVAILABLE else f"0x{value:04X} (invalid)"
        return f"{decoded // 60:02d}:{decoded % 60:02d}"

    if name.startswith(TIME_REGISTER_PREFIXES):
        decoded = _decode_register_time(value)
        if decoded is None:
            return None if value == SENSOR_UNAVAILABLE else f"0x{value:04X} (invalid)"
        return f"{decoded // 60:02d}:{decoded % 60:02d}"

    if name.startswith(SETTING_PREFIX):
        decoded = _decode_aatt(value)
        if decoded is None:
            return None if value == SENSOR_UNAVAILABLE else value
        airflow, temp = decoded
        temp_str = f"{temp:g}"
        return f"{airflow}% @ {temp_str}°C"

    return None if value == SENSOR_UNAVAILABLE else value


def _decode_season_mode(value: int) -> Optional[int]:
    """Decode season mode register which may place value in high byte."""
    if value in (0xFF00, 0xFFFF, SENSOR_UNAVAILABLE):
        return None
    high = (value >> 8) & 0xFF
    low = value & 0xFF
    if high and low:
        return None
    return high or low


SPECIAL_VALUE_DECODERS: Dict[str, Callable[[int], Optional[int]]] = {
    "season_mode": _decode_season_mode,
}

# Maximum registers per batch read (defined in ``const`` for reuse)

# Optional UART configuration registers (Air-B and Air++ ports)
# According to the Series 4 Modbus documentation, both the Air-B
# (0x1164-0x1167) and Air++ (0x1168-0x116B) register blocks are
# optional and may be absent on devices without the corresponding
# hardware. They are skipped by default unless UART scanning is
# explicitly enabled.
UART_OPTIONAL_REGS = range(0x1164, 0x116C)

# Registers considered safe to read when verifying connectivity.
# Each entry is a tuple of Modbus function code and register name. The
# corresponding addresses are resolved from the JSON register definitions at
# runtime, ensuring we do not hardcode register addresses here.
SAFE_REGISTERS: list[tuple[int, str]] = [
    (4, "version_major"),
    (4, "version_minor"),
    (3, "date_time_rrmm"),
]

__all__ = [
    "REGISTER_ALLOWED_VALUES",
    "SETTING_PREFIX",
    "_decode_aatt",
    "_format_register_value",
    "_decode_season_mode",
    "SPECIAL_VALUE_DECODERS",
    "MAX_BATCH_REGISTERS",
    "UART_OPTIONAL_REGS",
    "SAFE_REGISTERS",
]
