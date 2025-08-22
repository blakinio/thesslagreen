"""Tests for automatic register cache invalidation when the JSON file changes."""

from __future__ import annotations

import json
from importlib import resources

from custom_components.thessla_green_modbus.registers import get_all_registers
from custom_components.thessla_green_modbus.registers.loader import _load_registers


def test_register_cache_invalidation(monkeypatch) -> None:
    """Modifying the register JSON should trigger cache rebuilds."""

    with resources.as_file(
        resources.files("custom_components.thessla_green_modbus.registers")
        / "thessla_green_registers_full.json"
    ) as registers_path:
        original_content = registers_path.read_text()

        try:
            # Ensure caches start from a known state
            _load_registers.cache_clear()
            mr._REGISTER_CACHE = None
            mr._REGISTER_HASH = None

            # Prime caches
            first_reg = get_all_registers()[0]
            register_name = first_reg.name
            assert (
                get_register_info(register_name)["description"]
                == first_reg.description
            )

            # Modify the JSON file
            data = json.loads(original_content)
            data["registers"][0]["description"] = "changed description"
            registers_path.write_text(json.dumps(data))

            # Re-fetch without clearing caches; both loaders should detect the change
            updated_reg = get_all_registers()[0]
            assert updated_reg.name == register_name
            assert updated_reg.description == "changed description"
            assert (
                get_register_info(register_name)["description"]
                == "changed description"
            )
        finally:
            # Restore original file and clear caches for other tests
            registers_path.write_text(original_content)
            _load_registers.cache_clear()
            mr._REGISTER_CACHE = None
            mr._REGISTER_HASH = None
    )

    original_content = registers_path.read_text()

    try:
        # Ensure caches start from a known state
        _load_registers.cache_clear()

        csv_read = False
        real_read_text = Path.read_text

        def spy(self, *args, **kwargs):
            nonlocal csv_read
            if self.suffix == ".csv":
                csv_read = True
            return real_read_text(self, *args, **kwargs)

        # Monitor file reads to ensure CSV is never accessed
        monkeypatch.setattr(Path, "read_text", spy)

        first_reg = get_all_registers()[0]
        register_name = first_reg.name
        assert first_reg.description

        # Modify the JSON file
        data = json.loads(original_content)
        data["registers"][0]["description"] = "changed description"
        registers_path.write_text(json.dumps(data))

        # Re-fetch without clearing caches; both loaders should detect the change
        updated_reg = get_all_registers()[0]
        assert updated_reg.name == register_name
        assert updated_reg.description == "changed description"
        assert not csv_read
    finally:
        # Restore original file and clear caches for other tests
        registers_path.write_text(original_content)
        _load_registers.cache_clear()

