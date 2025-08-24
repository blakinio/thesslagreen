"""Register definitions for the ThesslaGreen Modbus integration."""

from __future__ import annotations

from .loader import (
    Register,
    get_all_registers,
    get_registers_hash,
    get_registers_by_function,
)

__all__ = [
    "Register",
    "get_all_registers",
    "get_registers_hash",
    "get_registers_by_function",
]
