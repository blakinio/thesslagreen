"""Regression tests for entity_mappings compatibility alias behavior."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from custom_components.thessla_green_modbus import entity_mappings as em
from custom_components.thessla_green_modbus import mappings as mappings_pkg


def test_entity_mappings_module_is_alias_of_mappings_package() -> None:
    """Legacy import path should resolve to the same module object."""
    assert em is mappings_pkg


def test_entity_mappings_file_points_to_compat_module_path() -> None:
    """Compatibility alias should keep __file__ at entity_mappings.py path."""
    assert em.__file__ is not None
    assert Path(em.__file__).name == "entity_mappings.py"


def test_monkeypatch_on_entity_mappings_affects_runtime_helpers(monkeypatch) -> None:
    """Monkeypatching legacy module should still affect helper behavior."""
    reg = SimpleNamespace(
        name="alias_test_register",
        multiplier=1,
        resolution=1,
        access="RW",
        min=0,
        max=10,
        unit="%",
        information="test",
    )

    monkeypatch.setattr(em, "get_all_registers", lambda *args, **kwargs: [reg])
    monkeypatch.setattr(em, "_REGISTER_INFO_CACHE", None)

    info = em._get_register_info("alias_test_register")
    assert info is not None
    assert info["access"] == "RW"
    assert info["unit"] == "%"


def test_exported_mappings_are_shared_objects_with_package_module() -> None:
    """Static mapping dictionaries should be shared, not copied."""
    assert em.SENSOR_ENTITY_MAPPINGS is mappings_pkg.SENSOR_ENTITY_MAPPINGS
    assert em.NUMBER_ENTITY_MAPPINGS is mappings_pkg.NUMBER_ENTITY_MAPPINGS
    assert em.SELECT_ENTITY_MAPPINGS is mappings_pkg.SELECT_ENTITY_MAPPINGS
    assert em.BINARY_SENSOR_ENTITY_MAPPINGS is mappings_pkg.BINARY_SENSOR_ENTITY_MAPPINGS


def test_alias_exposes_expected_public_api_names() -> None:
    """Legacy alias should expose the same public API names as mappings."""
    expected = {
        "ENTITY_MAPPINGS",
        "SENSOR_ENTITY_MAPPINGS",
        "NUMBER_ENTITY_MAPPINGS",
        "SELECT_ENTITY_MAPPINGS",
        "BINARY_SENSOR_ENTITY_MAPPINGS",
        "SWITCH_ENTITY_MAPPINGS",
        "map_legacy_entity_id",
        "async_setup_entity_mappings",
    }
    assert expected.issubset(set(em.__all__))
