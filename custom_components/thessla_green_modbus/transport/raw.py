"""Modbus response containers and protocol constants."""

from __future__ import annotations

_MIN_SLAVE_ID = 1
_MAX_SLAVE_ID = 247
_MAX_READ_REGISTERS = 125
_MAX_WRITE_REGISTERS = 123


class RawModbusResponse:
    """Minimal Modbus response container for raw RTU-over-TCP reads."""

    def __init__(self, registers: list[int] | None = None) -> None:
        self.registers = registers or []

    def isError(self) -> bool:
        return False


class RawModbusWriteResponse:
    """Minimal Modbus response container for raw RTU-over-TCP writes."""

    def isError(self) -> bool:
        return False


__all__ = [
    "_MAX_READ_REGISTERS",
    "_MAX_SLAVE_ID",
    "_MAX_WRITE_REGISTERS",
    "_MIN_SLAVE_ID",
    "RawModbusResponse",
    "RawModbusWriteResponse",
]
