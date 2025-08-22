"""Tests for the register loader utility."""

import json
import logging
from pathlib import Path

from custom_components.thessla_green_modbus.register_loader import RegisterLoader
from custom_components.thessla_green_modbus import loader as module_loader


def test_json_structure():
    """Validate structure of the registers JSON file."""
    path = (
        Path(__file__).resolve().parent.parent
        / "custom_components"
        / "thessla_green_modbus"
        / "registers"
        / "thessla_green_registers_full.json"
    )
    with path.open(encoding="utf-8") as f:
        data = json.load(f)
    required = {"function", "address_hex", "address_dec", "access", "name", "description"}
    for entry in data:
        assert required <= set(entry)


def test_register_lookup_and_properties():
    """Verify registers are loaded and accessible for all function codes."""
    loader = RegisterLoader()
    assert loader.input_registers["outside_temperature"] == 16
    assert loader.holding_registers["mode"] == 4097
    assert loader.coil_registers["bypass"] == 9
    assert loader.discrete_registers["expansion"] == 0


def test_enum_multiplier_resolution():
    """Check enum, multiplier and resolution extraction."""
    loader = RegisterLoader()
    assert loader.enums["special_mode"]["boost"] == 1
    assert loader.multipliers["required_temperature"] == 0.5
    assert loader.resolutions["required_temperature"] == 0.5


def test_group_reads_cover_addresses():
    """Ensure group reads cover all register addresses without gaps."""
    loader = RegisterLoader()
    mapping = {
        "input": loader.input_registers,
        "holding": loader.holding_registers,
        "coil": loader.coil_registers,
        "discrete": loader.discrete_registers,
    }
    for func, regs in mapping.items():
        addresses = sorted(regs.values())
        grouped: list[int] = []
        for start, count in loader.group_reads[func]:
            grouped.extend(range(start, start + count))
        assert grouped == addresses


def test_register_loader_csv_fallback(tmp_path, caplog):
    """RegisterLoader should load CSV files with a deprecation warning."""
    csv_file = tmp_path / "registers.csv"
    csv_file.write_text(
        "function,address_dec,access,name,description\n"
        "input,1,ro,test_reg,Test register\n"
    )
    with caplog.at_level(logging.WARNING):
        loader = RegisterLoader(path=csv_file)
    assert loader.input_registers["test_reg"] == 1
    assert "deprecated" in caplog.text.lower()


def test_loader_module_csv_fallback(tmp_path, caplog, monkeypatch):
    """Module level loader should fall back to CSV with warning."""
    csv_file = tmp_path / "regs.csv"
    csv_file.write_text(
        "function,address_dec,access,name,description\n"
        "input,2,ro,mod_reg,Mod register\n"
    )
    monkeypatch.setattr(module_loader, "_REGISTERS_FILE", tmp_path / "missing.json")
    module_loader._load_register_definitions.cache_clear()
    with caplog.at_level(logging.WARNING):
        regs = module_loader.get_registers_by_function("input")
    assert regs["mod_reg"] == 2
    assert "deprecated" in caplog.text.lower()
    module_loader._load_register_definitions.cache_clear()
