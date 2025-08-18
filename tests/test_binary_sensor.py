"""Tests for ThesslaGreenBinarySensor entity."""

import sys
import types
from typing import Any, cast
from unittest.mock import MagicMock

import pytest

# ---------------------------------------------------------------------------
# Minimal Home Assistant stubs
# ---------------------------------------------------------------------------

const = sys.modules.setdefault(
    "homeassistant.const", types.ModuleType("homeassistant.const")
)

binary_sensor_mod = cast(
    Any, types.ModuleType("homeassistant.components.binary_sensor")
)


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

entity_platform = cast(
    Any, types.ModuleType("homeassistant.helpers.entity_platform")
)


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


def test_binary_sensor_creation_and_state(mock_coordinator: MagicMock) -> None:
    """Test creation and state changes of binary sensor."""
    # Prepare coordinator data
    mock_coordinator.data["bypass"] = 0

    sensor = ThesslaGreenBinarySensor(
        mock_coordinator, "bypass", BINARY_SENSOR_DEFINITIONS["bypass"]
    )
    assert sensor.is_on is False  # nosec B101

    # Update coordinator data to trigger state change
    mock_coordinator.data["bypass"] = 1
    assert sensor.is_on is True  # nosec B101


def test_binary_sensor_icons(mock_coordinator: MagicMock) -> None:
    """Icon should switch to valid alternatives when sensor is off."""

    # Heating cable uses a heating icon when on
    mock_coordinator.data["heating_cable"] = 1
    heating = ThesslaGreenBinarySensor(
        mock_coordinator,
        "heating_cable",
        BINARY_SENSOR_DEFINITIONS["heating_cable"],
    )
    assert heating.icon == "mdi:heating-coil"  # nosec B101

    # When off, it should fall back to a valid icon
    mock_coordinator.data["heating_cable"] = 0
    assert heating.icon == "mdi:radiator-off"  # nosec B101

    # Bypass uses pipe leak icon when active
    mock_coordinator.data["bypass"] = 1
    bypass_sensor = ThesslaGreenBinarySensor(
        mock_coordinator, "bypass", BINARY_SENSOR_DEFINITIONS["bypass"]
    )
    assert bypass_sensor.icon == "mdi:pipe-leak"  # nosec B101

    # When inactive, generic pipe icon should be used
    mock_coordinator.data["bypass"] = 0
    assert bypass_sensor.icon == "mdi:pipe"  # nosec B101


def test_binary_sensor_icon_fallback(mock_coordinator: MagicMock) -> None:
    """Sensors without icons should return a sensible default."""
    mock_coordinator.data["bypass"] = 1
    sensor_def = BINARY_SENSOR_DEFINITIONS["bypass"].copy()
    sensor_def.pop("icon", None)
    sensor_without_icon = ThesslaGreenBinarySensor(
        mock_coordinator, "bypass", sensor_def
    )
    assert sensor_without_icon.icon == "mdi:fan-off"  # nosec B101


@pytest.mark.asyncio
async def test_async_setup_creates_all_binary_sensors(
    mock_coordinator: MagicMock, mock_config_entry: MagicMock
) -> None:
    """Ensure entities are created for all available binary sensor registers."""
    hass: MagicMock = MagicMock()
    hass.data = {DOMAIN: {mock_config_entry.entry_id: mock_coordinator}}

    # Build available register sets from definitions
    available: dict[str, set[str]] = {
        "coil_registers": set(),
        "discrete_inputs": set(),
        "input_registers": set(),
        "holding_registers": set(),
    }
    for name, definition in BINARY_SENSOR_DEFINITIONS.items():
        available[definition["register_type"]].add(name)
    mock_coordinator.available_registers = available

    add_entities: MagicMock = MagicMock()
    await async_setup_entry(hass, mock_config_entry, add_entities)

    entities = add_entities.call_args[0][0]
    assert len(entities) == len(BINARY_SENSOR_DEFINITIONS)  # nosec B101
