"""Tests for mappings package re-exports from static submodules."""

from __future__ import annotations

from custom_components.thessla_green_modbus import mappings
from custom_components.thessla_green_modbus.mappings import (
    _static_discrete as static_discrete,
)
from custom_components.thessla_green_modbus.mappings import (
    _static_numbers as static_numbers,
)
from custom_components.thessla_green_modbus.mappings import (
    _static_sensors as static_sensors,
)


def test_mappings_reexports_static_discrete_objects_by_identity() -> None:
    assert mappings.SELECT_ENTITY_MAPPINGS is static_discrete.SELECT_ENTITY_MAPPINGS
    assert mappings.BINARY_SENSOR_ENTITY_MAPPINGS is static_discrete.BINARY_SENSOR_ENTITY_MAPPINGS
    assert mappings.SWITCH_ENTITY_MAPPINGS is static_discrete.SWITCH_ENTITY_MAPPINGS


def test_mappings_reexports_static_numbers_objects_by_identity() -> None:
    assert mappings.NUMBER_OVERRIDES is static_numbers.NUMBER_OVERRIDES
    assert mappings.NUMBER_ENTITY_MAPPINGS is static_numbers.NUMBER_ENTITY_MAPPINGS


def test_mappings_reexports_static_sensors_objects_by_identity() -> None:
    assert mappings.SENSOR_ENTITY_MAPPINGS is static_sensors.SENSOR_ENTITY_MAPPINGS


def test_mappings_public_api_contains_static_mapping_names() -> None:
    expected = {
        "SELECT_ENTITY_MAPPINGS",
        "BINARY_SENSOR_ENTITY_MAPPINGS",
        "SWITCH_ENTITY_MAPPINGS",
        "NUMBER_OVERRIDES",
        "NUMBER_ENTITY_MAPPINGS",
        "SENSOR_ENTITY_MAPPINGS",
    }
    assert expected.issubset(set(mappings.__all__))


def test_build_entity_mappings_keeps_number_mapping_object_identity() -> None:
    """Rebuild should mutate NUMBER_ENTITY_MAPPINGS in-place, not replace object."""
    original = mappings.NUMBER_ENTITY_MAPPINGS

    mappings._build_entity_mappings()

    assert mappings.NUMBER_ENTITY_MAPPINGS is original
    assert mappings.ENTITY_MAPPINGS["number"] is original
