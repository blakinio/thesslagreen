"""Unit tests for loader helper functions."""

from pathlib import Path

from custom_components.thessla_green_modbus.registers.loader_helpers import (
    build_register_map,
    filter_registers_by_function,
    resolve_registers_path,
    sort_registers,
)
from custom_components.thessla_green_modbus.registers.register_def import RegisterDef


def _reg(function: int, address: int, name: str) -> RegisterDef:
    return RegisterDef(function=function, address=address, name=name, access="ro")


def test_resolve_registers_path_prefers_explicit_path(tmp_path: Path) -> None:
    default = Path("/tmp/default.json")
    explicit = tmp_path / "custom.json"
    assert resolve_registers_path(default, explicit) == explicit


def test_resolve_registers_path_falls_back_to_default() -> None:
    default = Path("/tmp/default.json")
    assert resolve_registers_path(default, None) == default


def test_sort_registers_orders_by_function_then_address() -> None:
    regs = [_reg(3, 2, "c"), _reg(1, 1, "a"), _reg(3, 1, "b")]
    sorted_regs = sort_registers(regs)
    assert [(r.function, r.address) for r in sorted_regs] == [(1, 1), (3, 1), (3, 2)]


def test_filter_registers_by_function_returns_matching_items() -> None:
    regs = [_reg(3, 0, "hold"), _reg(4, 0, "input")]
    assert [r.name for r in filter_registers_by_function(regs, 3)] == ["hold"]


def test_build_register_map_uses_register_name_as_key() -> None:
    regs = [_reg(3, 0, "alpha"), _reg(3, 1, "beta")]
    reg_map = build_register_map(regs)
    assert set(reg_map) == {"alpha", "beta"}
    assert reg_map["alpha"].address == 0
