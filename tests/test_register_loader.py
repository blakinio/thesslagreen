"""Tests for JSON register loader."""

import json
from pathlib import Path

import pytest

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


def test_multi_register_metadata() -> None:
    """Registers spanning multiple words expose length and type info."""

    holding_regs = get_registers_by_function("03")
    device_name = next(r for r in holding_regs if r.name == "device_name")
    assert device_name.length == 8
    assert device_name.extra["type"] == "string"

    lock = next(r for r in holding_regs if r.name == "lock_pass")
    assert lock.length == 2
    assert lock.extra["type"] == "uint32"
    assert lock.extra["endianness"] == "little"

    input_regs = get_registers_by_function("04")
    serial = next(r for r in input_regs if r.name == "serial_number")
    assert serial.length == 6
    assert serial.extra["encoding"] == "ascii"


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

    from custom_components.thessla_green_modbus.registers import loader

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

    loader.clear_cache()

    loader.get_all_registers()
    loader.get_all_registers()

    # The file should be read only once thanks to caching
    assert read_calls == 1


@pytest.mark.parametrize(
    "registers",
    [
        [
            {"function": "01", "address_dec": 1, "name": "dup1", "access": "R"},
            {"function": "01", "address_dec": 1, "name": "dup2", "access": "R"},
        ],
        [
            {"function": "01", "address_dec": 1, "name": "dup", "access": "R"},
            {"function": "02", "address_dec": 2, "name": "dup", "access": "R"},
        ],
    ],
)
def test_duplicate_registers_raise_error(tmp_path, monkeypatch, registers) -> None:
    """Duplicate names or addresses should raise an error."""

    from custom_components.thessla_green_modbus.registers import loader

    path = tmp_path / "regs.json"
    path.write_text(json.dumps({"registers": registers}))
    monkeypatch.setattr(loader, "_REGISTERS_PATH", path)

    with pytest.raises(ValueError):
        loader._load_registers_from_file(path, file_hash="")


@pytest.mark.parametrize(
    "register",
    [
        {
            "function": "03",
            "address_dec": 1,
            "address_hex": "0x2",
            "name": "bad_addr",
            "access": "R",
        },
        {
            "function": "03",
            "address_dec": 0,
            "address_hex": "0x0",
            "name": "bad_len",
            "access": "R",
            "length": 1,
            "extra": {"type": "uint32"},
        },
        {
            "function": "01",
            "address_dec": 0,
            "address_hex": "0x0",
            "name": "bad_access",
            "access": "R/W",
        },
        {
            "function": "03",
            "address_dec": 0,
            "address_hex": "0x0",
            "name": "bad_bits",
            "access": "R",
            "bits": ["a"],
        },
    ],
)
def test_invalid_registers_rejected(tmp_path, monkeypatch, register) -> None:
    """Registers violating schema constraints should raise an error."""

    from custom_components.thessla_green_modbus.registers import loader

    path = tmp_path / "regs.json"
    path.write_text(json.dumps({"registers": [register]}))
    monkeypatch.setattr(loader, "_REGISTERS_PATH", path)

    with pytest.raises(ValueError):
        loader._load_registers_from_file(path, file_hash="")


def test_missing_register_file_raises_runtime_error(tmp_path) -> None:
    """Missing register definition file should raise RuntimeError."""

    from custom_components.thessla_green_modbus.registers import loader

    path = tmp_path / "regs.json"
    with pytest.raises(RuntimeError) as exc:
        loader._load_registers_from_file(path, file_hash="")
    assert str(path) in str(exc.value)


def test_invalid_register_file_raises_runtime_error(tmp_path) -> None:
    """Invalid register definition file should raise RuntimeError."""

    from custom_components.thessla_green_modbus.registers import loader

    path = tmp_path / "regs.json"
    path.write_text("not json", encoding="utf-8")
    with pytest.raises(RuntimeError) as exc:
        loader._load_registers_from_file(path, file_hash="")
    assert str(path) in str(exc.value)


def test_register_file_sorted() -> None:
    """Ensure register JSON is sorted and loader preserves ordering."""

    from custom_components.thessla_green_modbus.registers import loader

    data = json.loads(loader._REGISTERS_PATH.read_text(encoding="utf-8"))
    regs = data["registers"]
    keys = [(str(r["function"]), int(r["address_dec"])) for r in regs]
    assert keys == sorted(keys)

    loaded_keys = [(r.function, r.address) for r in loader.get_all_registers()]
    assert loaded_keys == sorted(loaded_keys)


def test_get_all_registers_sorted(monkeypatch, tmp_path) -> None:
    """get_all_registers should order registers by function then address."""

    from custom_components.thessla_green_modbus.registers import loader

    regs = [
        {
            "function": "03",
            "address_dec": 2,
            "address_hex": "0x0002",
            "name": "reg_c",
            "access": "R",
        },
        {
            "function": "01",
            "address_dec": 1,
            "address_hex": "0x0001",
            "name": "reg_a",
            "access": "R",
        },
        {
            "function": "03",
            "address_dec": 1,
            "address_hex": "0x0001",
            "name": "reg_b",
            "access": "R",
        },
    ]

    path = tmp_path / "regs.json"
    path.write_text(json.dumps({"registers": regs}))
    monkeypatch.setattr(loader, "_REGISTERS_PATH", path)

    loader.clear_cache()
    ordered = loader.get_all_registers()
    keys = [(r.function, r.address) for r in ordered]
    assert keys == sorted(keys)
