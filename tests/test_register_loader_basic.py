"""Split register loader tests."""

import json
from pathlib import Path

from custom_components.thessla_green_modbus.registers.loader import (
    get_registers_by_function,
)
from custom_components.thessla_green_modbus.registers.parser import load_registers_from_file
from custom_components.thessla_green_modbus.registers.register_def import RegisterDef


def _add_desc(reg: dict) -> dict:
    return {**reg, "description": reg.get("description", "desc"), "description_en": reg.get("description_en", "desc")}


def _write(path: Path, regs: list[dict]) -> None:
    path.write_text(json.dumps({"registers": [_add_desc(r) for r in regs]}))

def test_example_register_mapping() -> None:
    """Verify example registers map to expected addresses."""

    def addr(fn: str, name: str) -> int:
        regs = get_registers_by_function(fn)
        reg = next(r for r in regs if r.name == name)
        return reg.address

    assert addr("01", "duct_water_heater_pump") == 5
    assert addr("02", "expansion") == 1
    assert addr("03", "mode") == 4208
    assert addr("04", "outside_temperature") == 16

def test_enum_multiplier_resolution_handling() -> None:
    """Ensure optional register metadata is preserved."""

    holding_regs = get_registers_by_function("03")

    special_mode = next(r for r in holding_regs if r.name == "special_mode")
    assert special_mode.enum and special_mode.enum[1] == "boost"

    required = next(r for r in holding_regs if r.name == "required_temperature")
    assert required.multiplier == 0.5
    assert required.resolution == 0.5
    assert required.decode(45) == 22.5

def test_default_multiplier_resolution(tmp_path) -> None:
    """Omitted multiplier/resolution fields default to 1."""

    reg = {
        "function": "03",
        "address_dec": 0,
        "name": "noscale",
        "access": "R",
    }

    path = tmp_path / "regs.json"
    _write(path, [reg])

    loaded = load_registers_from_file(path)[0]
    assert loaded.multiplier == 1
    assert loaded.resolution == 1

def test_multi_register_metadata() -> None:
    """Registers spanning multiple words expose length and type info."""

    holding_regs = get_registers_by_function("03")
    device_name = next(r for r in holding_regs if r.name == "device_name")
    assert device_name.length == 8
    assert device_name.extra["type"] == "string"

    lock = next(r for r in holding_regs if r.name == "lock_pass")
    assert lock.length == 2
    assert lock.extra["type"] == "u32"
    assert lock.extra["endianness"] == "little"

    input_regs = get_registers_by_function("04")
    serial = next(r for r in input_regs if r.name == "serial_number")
    assert serial.length == 6
    assert serial.extra["encoding"] == "ascii"

def test_decode_multi_register_string() -> None:
    """Multi-register strings decode without applying scaling."""
    reg = RegisterDef(
        function=3,
        address=0,
        name="device_name",
        access="ro",
        length=3,
        extra={"type": "string"},
        multiplier=2,
        resolution=1,
    )
    raw = [16706, 17220, 17664]  # "ABCDE"
    assert reg.decode(raw) == "ABCDE"

def test_decode_multi_register_string_with_non_ascii_bytes() -> None:
    """String decode should tolerate non-ASCII bytes without raising."""
    reg = RegisterDef(
        function=3,
        address=0,
        name="device_name",
        access="ro",
        length=2,
        extra={"type": "string", "encoding": "ascii"},
    )
    raw = [0x5445, 0xDF00]  # "TE" + 0xDF + NUL
    assert reg.decode(raw) == "TE�"

def test_decode_multi_register_number_scaled_once() -> None:
    """Numeric multi-register values apply multiplier/resolution exactly once."""
    reg = RegisterDef(
        function=3,
        address=0,
        name="counter",
        access="ro",
        length=2,
        extra={"type": "i32"},
        multiplier=10,
        resolution=1,
    )
    raw = [0, 1]
    assert reg.decode(raw) == 10

def test_decode_bitmask_ignores_scaling() -> None:
    """Bitmask registers return labels without scaling the raw value."""
    reg = RegisterDef(
        function=3,
        address=0,
        name="flags",
        access="ro",
        enum={1: "A", 2: "B", 4: "C"},
        extra={"bitmask": True},
        multiplier=2,
        resolution=1,
    )
    assert reg.decode(5) == ["A", "C"]

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
