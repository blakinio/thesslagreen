"""Tests for static mapping submodule exports."""

from __future__ import annotations

from custom_components.thessla_green_modbus.mappings import (
    _static_discrete as static_discrete,
)
from custom_components.thessla_green_modbus.mappings import (
    _static_numbers as static_numbers,
)
from custom_components.thessla_green_modbus.mappings import (
    _static_sensors as static_sensors,
)


def test_static_discrete_module_has_explicit_public_exports() -> None:
    assert set(static_discrete.__all__) == {
        "BINARY_SENSOR_ENTITY_MAPPINGS",
        "SELECT_ENTITY_MAPPINGS",
        "SWITCH_ENTITY_MAPPINGS",
    }


def test_static_numbers_module_has_explicit_public_exports() -> None:
    assert set(static_numbers.__all__) == {
        "NUMBER_ENTITY_MAPPINGS",
        "NUMBER_OVERRIDES",
    }


def test_static_sensors_module_has_explicit_public_exports() -> None:
    assert static_sensors.__all__ == ["SENSOR_ENTITY_MAPPINGS"]
