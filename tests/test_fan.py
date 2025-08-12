"""Tests for ThesslaGreenFan entity."""
import sys
import types
import pytest

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
