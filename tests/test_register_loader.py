"""Tests for JSON register loader."""

from custom_components.thessla_green_modbus.registers import (
    get_registers_by_function,
)


def test_example_register_mapping() -> None:
    """Verify example registers map to expected addresses."""

    def addr(fn: str, name: str) -> int:
        regs = get_registers_by_function(fn)
        reg = next(r for r in regs if r.name == name)
        return reg.address

    assert addr("01", "duct_water_heater_pump") == 5
    assert addr("02", "expansion") == 0
    assert addr("03", "mode") == 4097
    assert addr("04", "outside_temperature") == 16


def test_enum_multiplier_resolution_handling() -> None:
    """Ensure optional register metadata is preserved."""

    holding_regs = get_registers_by_function("03")

    special_mode = next(r for r in holding_regs if r.name == "special_mode")
    assert special_mode.enum and special_mode.enum["boost"] == 1

    required = next(r for r in holding_regs if r.name == "required_temperature")
    assert required.multiplier == 0.5
    assert required.resolution == 0.5
    assert required.decode(45) == 22.5

