"""Register definitions for the ThesslaGreen Modbus integration."""

from __future__ import annotations

from .loader import (
    Register,
    ReadPlan,
    get_all_registers,
    get_registers_hash,
    get_registers_by_function,
    plan_group_reads,
)

__all__ = [
    "Register",
    "ReadPlan",
    "get_all_registers",
    "get_registers_hash",
    "get_registers_by_function",
    "plan_group_reads",
]
