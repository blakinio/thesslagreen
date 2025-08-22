"""Tests for JSON register loader."""

import logging
from pathlib import Path

import json

from custom_components.thessla_green_modbus.register_loader import RegisterLoader
from custom_components.thessla_green_modbus.registers import (
    get_registers_by_function,
)
from custom_components.thessla_green_modbus.registers.loader import (
    _REGISTERS_PATH,
    _normalise_name,
)


def test_example_register_mapping() -> None:
    """Verify example registers map to expected addresses."""

    def addr(fn: str, name: str) -> int:
        regs = get_registers_by_function(fn)
        reg = next(r for r in regs if r.name == name)
        return reg.address

    assert addr("01", "duct_water_heater_pump") == 5
    assert addr("02", "expansion") == 0
    assert addr("03", "mode") == 4208
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


def test_registers_loaded_only_once(monkeypatch) -> None:
    """Ensure register file is read only once thanks to caching."""

    from pathlib import Path
    from custom_components.thessla_green_modbus.registers.loader import _load_registers

    read_calls = 0
    real_read_text = Path.read_text

    def spy(self, *args, **kwargs):
        nonlocal read_calls
        read_calls += 1
        return real_read_text(self, *args, **kwargs)

    # Spy on read_text to count disk reads
    monkeypatch.setattr(Path, "read_text", spy)

    _load_registers.cache_clear()

    _load_registers()
    _load_registers()

    # The file should be read only once thanks to caching
    assert read_calls == 1


def test_csv_loader_emits_warning(caplog) -> None:
    """Using a CSV file should emit a deprecation warning."""

    csv_path = (
        Path(__file__).resolve().parent.parent
        / "custom_components"
        / "thessla_green_modbus"
        / "data"
        / "modbus_registers.csv"
    )

    with caplog.at_level(logging.WARNING):
        loader = RegisterLoader(csv_path)

    assert loader.registers
    assert any("deprecated" in rec.message for rec in caplog.records)


def test_register_names_need_no_normalisation() -> None:
    """JSON register names should already be normalised."""

    raw = json.loads(_REGISTERS_PATH.read_text(encoding="utf-8"))
    items = raw.get("registers", raw) if isinstance(raw, dict) else raw
    corrections = [
        name
        for name in (str(item["name"]) for item in items)
        if _normalise_name(name) != name
    ]
    assert corrections == []
