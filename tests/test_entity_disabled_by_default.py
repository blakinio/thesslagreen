"""Tests for entity_registry_enabled_default=False on DIAGNOSTIC entities.

Silver quality-scale requirement: diagnostic entities must be disabled by
default so they don't clutter the user's entity list.  Both ThesslaGreenSensor
and ThesslaGreenBinarySensor set ``_attr_entity_registry_enabled_default =
False`` when the definition carries ``entity_category == DIAGNOSTIC``.
"""

from __future__ import annotations

from unittest.mock import MagicMock

from custom_components.thessla_green_modbus.binary_sensor import (
    BINARY_SENSOR_DEFINITIONS,
    ThesslaGreenBinarySensor,
)
from custom_components.thessla_green_modbus.sensor import (
    SENSOR_DEFINITIONS,
    ThesslaGreenSensor,
)
from homeassistant.helpers.entity import EntityCategory


def _make_coordinator() -> MagicMock:
    coordinator = MagicMock()
    coordinator.host = "192.168.1.1"
    coordinator.port = 502
    coordinator.device_client.slave_id = 10
    coordinator.last_update_success = True
    coordinator.data = {}
    coordinator.device_client.device_info = {}
    coordinator.get_device_info = MagicMock(return_value={})
    return coordinator


# ---------------------------------------------------------------------------
# ThesslaGreenSensor – disabled_by_default
# ---------------------------------------------------------------------------


def test_diagnostic_sensor_disabled_by_default() -> None:
    """A sensor with entity_category=DIAGNOSTIC must be disabled by default."""
    diag_key = next(
        k
        for k, v in SENSOR_DEFINITIONS.items()
        if v.get("entity_category") == EntityCategory.DIAGNOSTIC
    )
    definition = SENSOR_DEFINITIONS[diag_key]
    coordinator = _make_coordinator()

    sensor = ThesslaGreenSensor(coordinator, diag_key, 1000, definition)

    assert sensor._attr_entity_registry_enabled_default is False
    assert sensor._attr_entity_category is EntityCategory.DIAGNOSTIC


def test_non_diagnostic_sensor_enabled_by_default() -> None:
    """A sensor without entity_category must not set disabled_by_default."""
    normal_key = next(k for k, v in SENSOR_DEFINITIONS.items() if not v.get("entity_category"))
    definition = SENSOR_DEFINITIONS[normal_key]
    coordinator = _make_coordinator()

    sensor = ThesslaGreenSensor(coordinator, normal_key, 1001, definition)

    # The attribute must not have been set to False; either True or unset (truthy).
    assert getattr(sensor, "_attr_entity_registry_enabled_default", True) is not False


def test_all_diagnostic_sensors_disabled_by_default() -> None:
    """Every DIAGNOSTIC sensor definition produces a disabled-by-default entity."""
    coordinator = _make_coordinator()
    diag_defs = {
        k: v
        for k, v in SENSOR_DEFINITIONS.items()
        if v.get("entity_category") == EntityCategory.DIAGNOSTIC
    }
    assert diag_defs, "Expected at least one DIAGNOSTIC sensor"
    for key, definition in diag_defs.items():
        sensor = ThesslaGreenSensor(coordinator, key, 1000, definition)
        assert sensor._attr_entity_registry_enabled_default is False, (
            f"Sensor '{key}' should be disabled by default"
        )


# ---------------------------------------------------------------------------
# ThesslaGreenBinarySensor – disabled_by_default
# ---------------------------------------------------------------------------


def test_diagnostic_binary_sensor_disabled_by_default() -> None:
    """A binary sensor with entity_category=DIAGNOSTIC must be disabled by default."""
    diag_key = next(
        k
        for k, v in BINARY_SENSOR_DEFINITIONS.items()
        if v.get("entity_category") == EntityCategory.DIAGNOSTIC
    )
    definition = BINARY_SENSOR_DEFINITIONS[diag_key]
    coordinator = _make_coordinator()

    bsensor = ThesslaGreenBinarySensor(coordinator, diag_key, 2000, definition)

    assert bsensor._attr_entity_registry_enabled_default is False
    assert bsensor._attr_entity_category is EntityCategory.DIAGNOSTIC


def test_non_diagnostic_binary_sensor_enabled_by_default() -> None:
    """A binary sensor without entity_category must not be disabled by default."""
    normal_key = next(
        k for k, v in BINARY_SENSOR_DEFINITIONS.items() if not v.get("entity_category")
    )
    definition = BINARY_SENSOR_DEFINITIONS[normal_key]
    coordinator = _make_coordinator()

    bsensor = ThesslaGreenBinarySensor(coordinator, normal_key, 2001, definition)

    assert getattr(bsensor, "_attr_entity_registry_enabled_default", True) is not False


def test_all_diagnostic_binary_sensors_disabled_by_default() -> None:
    """Every DIAGNOSTIC binary sensor definition produces a disabled-by-default entity."""
    coordinator = _make_coordinator()
    diag_defs = {
        k: v
        for k, v in BINARY_SENSOR_DEFINITIONS.items()
        if v.get("entity_category") == EntityCategory.DIAGNOSTIC
    }
    assert diag_defs, "Expected at least one DIAGNOSTIC binary sensor"
    for key, definition in diag_defs.items():
        bsensor = ThesslaGreenBinarySensor(coordinator, key, 2000, definition)
        assert bsensor._attr_entity_registry_enabled_default is False, (
            f"Binary sensor '{key}' should be disabled by default"
        )
