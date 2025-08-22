"""Tests for JSON register loader."""

from pathlib import Path

from custom_components.thessla_green_modbus.registers.loader import (
    _RegisterFileModel,
    get_registers_by_function,
)


def _load_model() -> _RegisterFileModel:
    text = Path("thessla_green_registers_full.json").read_text(encoding="utf-8")
    try:
        return _RegisterFileModel.model_validate_json(text)
    except AttributeError:  # pragma: no cover - pydantic v1 fallback
        return _RegisterFileModel.parse_raw(text)


def test_json_schema_valid() -> None:
    """Validate the register file against the schema."""
    model = _load_model()
    assert model.schema_version
    assert model.registers


def test_example_register_mapping() -> None:
    """Verify example registers map to expected addresses."""
    def addr(fn: str, name: str) -> int:
        regs = get_registers_by_function(fn)
        reg = next(r for r in regs if r.name == name)
        return reg.address

    assert addr("01", "duct_warter_heater_pump") == 5
    assert addr("02", "duct_heater_protection") == 0
    assert addr("03", "date_time_rrmm") == 0
    assert addr("04", "VERSION_MAJOR") == 0


def test_enum_multiplier_resolution_handling() -> None:
    """Ensure optional register metadata is preserved."""
    coil = get_registers_by_function("01")[0]
    assert coil.enum == {"0": "OFF", "1": "ON"}

    outside = next(
        r for r in get_registers_by_function("04") if r.name == "outside_temperature"
    )
    assert outside.multiplier == 0.1

    supply_manual = next(
        r
        for r in get_registers_by_function("03")
        if r.name == "supplyAirTemperatureManual"
    )
    assert supply_manual.resolution == 0.5


def test_function_aliases() -> None:
    """Aliases with spaces/underscores should resolve to correct functions."""
    aliases = {
        "coil_registers": "01",
        "discrete_inputs": "02",
        "holding_registers": "03",
        "input_registers": "04",
        "input registers": "04",
    }
    for alias, code in aliases.items():
        alias_regs = get_registers_by_function(alias)
        code_regs = get_registers_by_function(code)
        assert {r.address for r in alias_regs} == {r.address for r in code_regs}

