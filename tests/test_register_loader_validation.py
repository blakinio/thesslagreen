"""Validation tests for the register loader."""

import json
from pathlib import Path

import pytest

from custom_components.thessla_green_modbus.registers.loader import _load_registers


def test_invalid_register_schema(monkeypatch, tmp_path) -> None:
    """Loader should raise when JSON schema is invalid."""

    bad_data = {"registers": [{"function": "03", "address_dec": 1}]}
    bad_file = tmp_path / "bad.json"
    bad_file.write_text(json.dumps(bad_data), encoding="utf-8")

    # Point loader to our invalid file and ensure cache is cleared
    monkeypatch.setattr(
        "custom_components.thessla_green_modbus.registers.loader._REGISTERS_PATH",
        bad_file,
    )
    _load_registers.cache_clear()

    with pytest.raises(ValueError):
        _load_registers()

