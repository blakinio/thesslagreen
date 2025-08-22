"""Register definitions for the ThesslaGreen Modbus integration."""

from __future__ import annotations

from .loader import (
    Register,
    ReadPlan,
    get_register_definition,
    get_all_registers,
    get_registers_by_function,
    group_reads,
    group_addresses,
)

__all__ = [
    "Register",
    "ReadPlan",
    "get_register_definition",
    "get_all_registers",
    "get_registers_by_function",
    "group_reads",
    "group_addresses",
]
