"""Tests for ThesslaGreenBinarySensor entity."""
import sys
import types
import pytest

# ---------------------------------------------------------------------------
# Minimal Home Assistant stubs
# ---------------------------------------------------------------------------

const = sys.modules.setdefault("homeassistant.const", types.ModuleType("homeassistant.const"))

binary_sensor_mod = types.ModuleType("homeassistant.components.binary_sensor")


class BinarySensorEntity:  # pragma: no cover - simple stub
    pass


class BinarySensorDeviceClass:  # pragma: no cover - enum stubs
    RUNNING = "running"
    OPENING = "opening"
    POWER = "power"
    HEAT = "heat"
    CONNECTIVITY = "connectivity"
    PROBLEM = "problem"
    SAFETY = "safety"
    COLD = "cold"
    MOISTURE = "moisture"


binary_sensor_mod.BinarySensorEntity = BinarySensorEntity
binary_sensor_mod.BinarySensorDeviceClass = BinarySensorDeviceClass
sys.modules["homeassistant.components.binary_sensor"] = binary_sensor_mod

entity_platform = types.ModuleType("homeassistant.helpers.entity_platform")


class AddEntitiesCallback:  # pragma: no cover - simple stub
    pass


entity_platform.AddEntitiesCallback = AddEntitiesCallback
sys.modules["homeassistant.helpers.entity_platform"] = entity_platform

# ---------------------------------------------------------------------------
# Actual tests
# ---------------------------------------------------------------------------

from custom_components.thessla_green_modbus.binary_sensor import (
    BINARY_SENSOR_DEFINITIONS,
    ThesslaGreenBinarySensor,
)


def test_binary_sensor_creation_and_state(mock_coordinator):
    """Test creation and state changes of binary sensor."""
    # Prepare coordinator data
    mock_coordinator.data["bypass"] = 0

    sensor = ThesslaGreenBinarySensor(
        mock_coordinator, "bypass", BINARY_SENSOR_DEFINITIONS["bypass"]
    )
    assert sensor.is_on is False

    # Update coordinator data to trigger state change
    mock_coordinator.data["bypass"] = 1
    assert sensor.is_on is True
