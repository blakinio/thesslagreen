"""Tests for the register loader utility."""

import json
from pathlib import Path

from custom_components.thessla_green_modbus.register_loader import RegisterLoader


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
