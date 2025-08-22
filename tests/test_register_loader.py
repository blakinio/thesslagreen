"""Tests for JSON register loader."""

import json
import logging
from pathlib import Path

from custom_components.thessla_green_modbus.register_loader import RegisterLoader
from custom_components.thessla_green_modbus.registers import (
    get_registers_by_function,
    get_registers_hash,
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

    from custom_components.thessla_green_modbus.registers.loader import _load_registers

    read_calls = 0
    real_read_text = Path.read_text

    def spy(self, *args, **kwargs):
        nonlocal read_calls
        read_calls += 1
        text = real_read_text(self, *args, **kwargs)
        json.loads(text)
        return text

    # Spy on read_text to count disk reads
    monkeypatch.setattr(Path, "read_text", spy)

    _load_registers.cache_clear()

    _load_registers()
    _load_registers()

    # The file should be read only once thanks to caching
    assert read_calls == 1


def test_path_argument_ignored(caplog) -> None:
    """Providing a path should not trigger any CSV handling."""

    csv_path = (
        Path(__file__).resolve().parent.parent / "tools" / "modbus_registers.csv"
    )

    with caplog.at_level(logging.WARNING):
        loader = RegisterLoader(csv_path)

    assert loader.registers
    assert not caplog.records


def test_cache_refresh_on_file_change(monkeypatch, tmp_path) -> None:
    """Modifying the register file should refresh the cache."""

    from custom_components.thessla_green_modbus.registers.loader import _load_registers

    data = {"registers": [{"function": "03", "address_dec": 1, "name": "first"}]}
    reg_file = tmp_path / "regs.json"
    reg_file.write_text(json.dumps(data), encoding="utf-8")

    # Point loader to the temporary file and prime the cache
    monkeypatch.setattr(
        "custom_components.thessla_green_modbus.registers.loader._REGISTERS_PATH",
        reg_file,
    )
    _load_registers.cache_clear()
    assert len(_load_registers()) == 1
    original_hash = get_registers_hash()

    # Modify the file and ensure cache is refreshed
    data["registers"].append({"function": "03", "address_dec": 2, "name": "second"})
    reg_file.write_text(json.dumps(data), encoding="utf-8")

    assert len(_load_registers()) == 2
    assert get_registers_hash() != original_hash

    _load_registers.cache_clear()
