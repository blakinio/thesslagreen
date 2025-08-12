"""Tests for ThesslaGreenFan entity."""
import sys
import types
import asyncio
import pytest
from unittest.mock import AsyncMock
from pymodbus.exceptions import ConnectionException

# ---------------------------------------------------------------------------
# Minimal Home Assistant stubs
# ---------------------------------------------------------------------------

const = sys.modules.setdefault("homeassistant.const", types.ModuleType("homeassistant.const"))

fan_mod = types.ModuleType("homeassistant.components.fan")


class FanEntity:  # pragma: no cover - simple stub
    pass


class FanEntityFeature:  # pragma: no cover - simple stub
    SET_SPEED = 1


fan_mod.FanEntity = FanEntity
fan_mod.FanEntityFeature = FanEntityFeature
sys.modules["homeassistant.components.fan"] = fan_mod

entity_platform = types.ModuleType("homeassistant.helpers.entity_platform")


class AddEntitiesCallback:  # pragma: no cover - simple stub
    pass


entity_platform.AddEntitiesCallback = AddEntitiesCallback
sys.modules["homeassistant.helpers.entity_platform"] = entity_platform

helpers_uc = sys.modules.setdefault(
    "homeassistant.helpers.update_coordinator",
    types.ModuleType("homeassistant.helpers.update_coordinator"),
)


class CoordinatorEntity:  # pragma: no cover - simple stub
    def __init__(self, coordinator=None):
        self.coordinator = coordinator

    @classmethod
    def __class_getitem__(cls, item):  # pragma: no cover - allow subscripting
        return cls


helpers_uc.CoordinatorEntity = CoordinatorEntity

# ---------------------------------------------------------------------------
# Actual tests
# ---------------------------------------------------------------------------

from custom_components.thessla_green_modbus.fan import ThesslaGreenFan


def test_fan_creation_and_state(mock_coordinator):
    """Test creation and basic state reporting of fan entity."""
    mock_coordinator.data["supply_percentage"] = 50
    mock_coordinator.data["on_off_panel_mode"] = 1
    fan = ThesslaGreenFan(mock_coordinator)
    assert fan.is_on is True
    assert fan.percentage == 50

    mock_coordinator.data["supply_percentage"] = 0
    assert fan.is_on is False
    assert fan.percentage == 0


def test_fan_turn_on_modbus_failure(mock_coordinator):
    """Ensure connection errors during turn on are raised."""
    fan = ThesslaGreenFan(mock_coordinator)
    mock_coordinator.async_write_register = AsyncMock(
        side_effect=ConnectionException("fail")
    )
    with pytest.raises(ConnectionException):
        asyncio.run(fan.async_turn_on(percentage=40))


def test_fan_set_percentage_failure(mock_coordinator):
    """Ensure write failures surface as runtime errors."""
    mock_coordinator.data["mode"] = 1  # manual mode to force write
    fan = ThesslaGreenFan(mock_coordinator)
    mock_coordinator.async_write_register = AsyncMock(return_value=False)
    with pytest.raises(RuntimeError):
        asyncio.run(fan.async_set_percentage(60))
