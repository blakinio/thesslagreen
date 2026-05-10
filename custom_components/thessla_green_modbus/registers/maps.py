"""Register map helpers for the ThesslaGreen Modbus integration."""

from __future__ import annotations

from functools import cache, lru_cache

from .loader import get_registers_by_function


@cache
def _build_map(fn: str) -> dict[str, int]:
    return {r.name: r.address for r in get_registers_by_function(fn) if r.name}


def coil_registers() -> dict[str, int]:
    return _build_map("coil")


def discrete_input_registers() -> dict[str, int]:
    return _build_map("discrete")


def holding_registers() -> dict[str, int]:
    return _build_map("holding")


def input_registers() -> dict[str, int]:
    return _build_map("input")


@lru_cache(maxsize=1)
def multi_register_sizes() -> dict[str, int]:
    return {
        r.name: r.length for r in get_registers_by_function("holding") if r.name and r.length > 1
    }


__all__ = [
    "_build_map",
    "coil_registers",
    "discrete_input_registers",
    "holding_registers",
    "input_registers",
    "multi_register_sizes",
]
