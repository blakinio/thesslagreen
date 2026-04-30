"""Helper units for register loader orchestration."""

from __future__ import annotations

from pathlib import Path

from .register_def import RegisterDef


def resolve_registers_path(default_path: Path, json_path: Path | str | None) -> Path:
    """Resolve user-provided path or return bundled default path."""
    return Path(json_path) if json_path is not None else default_path


def sort_registers(registers: list[RegisterDef]) -> list[RegisterDef]:
    """Sort register definitions by function then address."""
    return sorted(registers, key=lambda reg: (reg.function, reg.address))


def filter_registers_by_function(registers: list[RegisterDef], function: int) -> list[RegisterDef]:
    """Return registers matching normalized function code."""
    return [reg for reg in registers if reg.function == function]


def build_register_map(registers: list[RegisterDef]) -> dict[str, RegisterDef]:
    """Build name -> RegisterDef map preserving existing loader behavior."""
    return {reg.name: reg for reg in registers}
