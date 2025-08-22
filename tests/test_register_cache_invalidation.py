"""Tests for automatic register cache invalidation when the JSON file changes."""

from __future__ import annotations

import json
from importlib import resources
from pathlib import Path

from custom_components.thessla_green_modbus.registers import get_all_registers
from custom_components.thessla_green_modbus.registers.loader import _load_registers


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
