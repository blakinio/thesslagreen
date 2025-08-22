"""Tests for automatic register cache invalidation when the JSON file changes."""

from __future__ import annotations

import json
from pathlib import Path

from custom_components.thessla_green_modbus.data import modbus_registers as mr
from custom_components.thessla_green_modbus.data.modbus_registers import (
    get_register_info,
)
from custom_components.thessla_green_modbus.registers import get_all_registers
from custom_components.thessla_green_modbus.registers.loader import _load_registers


def test_register_cache_invalidation() -> None:
    """Modifying the register JSON should trigger cache rebuilds."""

    registers_path = (
        Path(__file__).resolve().parent.parent
        / "registers"
        / "thessla_green_registers_full.json"
    )

    original_content = registers_path.read_text()

    try:
        # Ensure caches start from a known state
        _load_registers.cache_clear()
        mr._REGISTER_CACHE = None
        mr._REGISTER_HASH = None

        # Prime caches
        first_reg = get_all_registers()[0]
        register_name = first_reg.name
        assert get_register_info(register_name)["description"] == first_reg.description

        # Modify the JSON file
        data = json.loads(original_content)
        data["registers"][0]["description"] = "changed description"
        registers_path.write_text(json.dumps(data))

        # Re-fetch without clearing caches; both loaders should detect the change
        updated_reg = get_all_registers()[0]
        assert updated_reg.name == register_name
        assert updated_reg.description == "changed description"
        assert get_register_info(register_name)["description"] == "changed description"
    finally:
        # Restore original file and clear caches for other tests
        registers_path.write_text(original_content)
        _load_registers.cache_clear()
        mr._REGISTER_CACHE = None
        mr._REGISTER_HASH = None

