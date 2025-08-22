"""Tests for automatic register cache invalidation when the JSON file changes."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from custom_components.thessla_green_modbus.registers import get_all_registers
from custom_components.thessla_green_modbus.registers import loader as mr
from custom_components.thessla_green_modbus.registers.loader import _load_registers


@pytest.mark.usefixtures("monkeypatch")
def test_register_cache_invalidation(monkeypatch, tmp_path) -> None:
    """Modifying the register JSON should trigger cache rebuilds."""

    # Copy bundled registers to a temporary file and patch loader to use it
    temp = tmp_path / "registers.json"
    temp.write_text(mr._REGISTERS_PATH.read_text(), encoding="utf-8")
    monkeypatch.setattr(mr, "_REGISTERS_PATH", temp)
    monkeypatch.setattr(
        "custom_components.thessla_green_modbus.registers.loader._REGISTERS_PATH",
        temp,
    )

    # Ensure caches start from a known state
    _load_registers.cache_clear()
    mr._REGISTER_CACHE = []
    mr._REGISTERS_HASH = None

    real_read_text = Path.read_text

    def spy(self: Path, *args, **kwargs):
        assert self.suffix != ".csv"
        return real_read_text(self, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", spy)

    first_reg = get_all_registers()[0]
    register_name = first_reg.name
    assert first_reg.description

    # Modify the JSON file
    data = json.loads(temp.read_text())
    data["registers"][0]["description"] = "changed description"
    temp.write_text(json.dumps(data), encoding="utf-8")

    # Re-fetch without clearing caches; loader should detect the change
    updated_reg = get_all_registers()[0]
    assert updated_reg.name == register_name
    assert updated_reg.description == "changed description"
