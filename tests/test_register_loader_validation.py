"""Validation tests for the register loader."""

import json

import pytest

from custom_components.thessla_green_modbus.registers import loader


def test_invalid_register_schema(monkeypatch, tmp_path) -> None:
    """Loader should raise when JSON schema is invalid."""

    bad_data = {"registers": [{"function": "03", "address_dec": 1}]}
    bad_file = tmp_path / "bad.json"
    bad_file.write_text(json.dumps(bad_data), encoding="utf-8")

    # Point loader to our invalid file and ensure cache is cleared
    monkeypatch.setattr(loader, "_REGISTERS_PATH", bad_file)
    loader._load_registers.cache_clear()

    with pytest.raises(ValueError):
        loader._load_registers()


def test_register_auto_reload(monkeypatch, tmp_path) -> None:
    """Loader should reload registers when the JSON file changes."""

    data = {
        "registers": [
            {"function": "03", "address_dec": 1, "name": "first"}
        ]
    }
    reg_file = tmp_path / "regs.json"
    reg_file.write_text(json.dumps(data), encoding="utf-8")

    # Point the loader to our temporary file and prime the cache
    monkeypatch.setattr(loader, "_REGISTERS_PATH", reg_file)
    loader._load_registers.cache_clear()
    assert len(loader._load_registers()) == 1
    original_hash = loader.get_registers_hash()

    # Add a new register to the JSON definition
    data["registers"].append({"function": "03", "address_dec": 2, "name": "second"})
    reg_file.write_text(json.dumps(data), encoding="utf-8")

    # A subsequent call should detect the change and reload definitions
    assert len(loader._load_registers()) == 2
    assert loader.get_registers_hash() != original_hash

    # Reset cache for other tests
    loader._load_registers.cache_clear()

