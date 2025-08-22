"""Tests for the register loader utility."""

import json
from pathlib import Path

from custom_components.thessla_green_modbus.registers.loader import (
    get_coil_registers,
    get_discrete_input_registers,
    get_holding_registers,
    get_input_registers,
    get_register_definition,
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
    assert get_input_registers()["outside_temperature"] == 16
    assert get_holding_registers()["mode"] == 4097
    assert get_coil_registers()["bypass"] == 9
    assert get_discrete_input_registers()["expansion"] == 0


def test_enum_multiplier_resolution():
    """Check enum, multiplier and resolution extraction."""
    reg = get_register_definition("special_mode")
    assert reg and reg.enum and reg.enum["boost"] == 1
    reg2 = get_register_definition("required_temperature")
    assert reg2 and reg2.multiplier == 0.5
    assert reg2.resolution == 0.5


def test_group_reads_cover_addresses():
    """Ensure group reads cover all register addresses without gaps."""
    mapping = {
        "input": get_input_registers(),
        "holding": get_holding_registers(),
        "coil": get_coil_registers(),
        "discrete": get_discrete_input_registers(),
    }
    for regs in mapping.values():
        addresses = sorted(regs.values())
        covered: list[int] = []
        for start, count in group_reads(addresses):
            covered.extend(range(start, start + count))
        for addr in addresses:
            assert addr in covered
