"""Tests for ThesslaGreenBinarySensor entity."""

import sys
import types
from unittest.mock import MagicMock

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

from custom_components.thessla_green_modbus.binary_sensor import (  # noqa: E402
    BINARY_SENSOR_DEFINITIONS,
    ThesslaGreenBinarySensor,
    async_setup_entry,
)
from custom_components.thessla_green_modbus.const import DOMAIN  # noqa: E402


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


@pytest.mark.asyncio
async def test_async_setup_creates_all_binary_sensors(mock_coordinator, mock_config_entry):
    """Ensure entities are created for all available binary sensor registers."""
    hass = MagicMock()
    hass.data = {DOMAIN: {mock_config_entry.entry_id: mock_coordinator}}

    # Build available register sets from definitions
    available = {
        "coil_registers": set(),
        "discrete_inputs": set(),
        "input_registers": set(),
        "holding_registers": set(),
    }
    for name, definition in BINARY_SENSOR_DEFINITIONS.items():
        available[definition["register_type"]].add(name)
    mock_coordinator.available_registers = available

    add_entities = MagicMock()
    await async_setup_entry(hass, mock_config_entry, add_entities)

    entities = add_entities.call_args[0][0]
    assert len(entities) == len(BINARY_SENSOR_DEFINITIONS)
