"""Tests for automatic register cache invalidation when the JSON file changes."""

from __future__ import annotations

import json
from importlib import resources
from pathlib import Path

from custom_components.thessla_green_modbus.registers.loader import (
    _cache_clear,
    _load_registers,
    _REGISTERS_PATH,
)


def test_register_cache_invalidation(tmp_path: Path, monkeypatch) -> None:
    """Modifying the register JSON should trigger cache rebuilds."""

    # Work on a temporary copy of the registers file
    tmp_json = tmp_path / "registers.json"
    tmp_json.write_text(_REGISTERS_PATH.read_text())
    monkeypatch.setattr(
        "custom_components.thessla_green_modbus.registers.loader._REGISTERS_PATH",
        tmp_json,
    )

    _cache_clear()
    first = _load_registers()[0]
    assert first.description

    # Change description in the JSON and ensure cache reload after clearing
    data = json.loads(tmp_json.read_text())
    data["registers"][0]["description"] = "changed description"
    tmp_json.write_text(json.dumps(data))

    _cache_clear()
    updated = _load_registers()[0]
    assert updated.description == "changed description"

    _cache_clear()
def test_register_cache_invalidation() -> None:
    """Modifying the register JSON should trigger cache rebuilds."""

    with resources.as_file(
        resources.files("custom_components.thessla_green_modbus.registers")
        / "thessla_green_registers_full.json"
    ) as registers_path:
        original = registers_path.read_text()
        try:
            _load_registers.cache_clear()

            first = get_all_registers()[0]
            assert first.description

            data = json.loads(original)
            data["registers"][0]["description"] = "changed description"
            registers_path.write_text(json.dumps(data))

            updated = get_all_registers()[0]
            assert updated.description == "changed description"
        finally:
            registers_path.write_text(original)
            _load_registers.cache_clear()
