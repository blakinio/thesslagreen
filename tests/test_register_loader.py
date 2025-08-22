"""Tests for the register loader utility."""

import json
import logging
from pathlib import Path

import custom_components.thessla_green_modbus.registers.loader as loader
from custom_components.thessla_green_modbus.registers import (
    get_all_registers,
    get_registers_by_function,
    group_reads,
)


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
    input_regs = {r.name: r.address for r in get_registers_by_function("input")}
    holding_regs = {r.name: r.address for r in get_registers_by_function("holding")}
    coil_regs = {r.name: r.address for r in get_registers_by_function("coil")}
    discrete_regs = {r.name: r.address for r in get_registers_by_function("discrete")}

    assert input_regs["outside_temperature"] == 16
    assert holding_regs["mode"] == 4097
    assert coil_regs["bypass"] == 9
    assert discrete_regs["expansion"] == 0


def test_enum_multiplier_resolution():
    """Check enum, multiplier and resolution extraction."""
    holding_regs = get_registers_by_function("holding")
    special_mode = next(r for r in holding_regs if r.name == "special_mode")
    required_temp = next(r for r in holding_regs if r.name == "required_temperature")

    assert special_mode.enum["boost"] == 1
    assert required_temp.multiplier == 0.5
    assert required_temp.resolution == 0.5


def test_group_reads_cover_addresses():
    """Ensure group reads cover all register addresses without gaps."""
    mapping = {
        "input": {r.name: r.address for r in get_registers_by_function("input")},
        "holding": {r.name: r.address for r in get_registers_by_function("holding")},
        "coil": {r.name: r.address for r in get_registers_by_function("coil")},
        "discrete": {r.name: r.address for r in get_registers_by_function("discrete")},
    }
    grouped: dict[str, list[int]] = {"input": [], "holding": [], "coil": [], "discrete": []}
    for plan in group_reads():
        grouped[plan.function].extend(range(plan.address, plan.address + plan.length))
    for func, regs in mapping.items():
        assert grouped[func] == sorted(regs.values())


def test_loader_csv_fallback(tmp_path, caplog, monkeypatch):
    """Loader should load CSV files with a deprecation warning."""
    csv_file = tmp_path / "regs.csv"
    csv_file.write_text(
        "function,address_dec,access,name,description\n"
        "input,1,ro,test_reg,Test register\n"
    )
    monkeypatch.setattr(loader, "_REGISTERS_FILE", tmp_path / "missing.json")
    loader._load_raw.cache_clear()
    loader._load_registers.cache_clear()
    with caplog.at_level(logging.WARNING):
        regs = {r.name: r.address for r in loader.get_registers_by_function("input")}
    assert regs["test_reg"] == 1
    assert "deprecated" in caplog.text.lower()
    loader._load_raw.cache_clear()
    loader._load_registers.cache_clear()
