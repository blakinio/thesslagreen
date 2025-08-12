"""Tests for ThesslaGreenSwitch entity."""
import sys
import types
import asyncio
import pytest

# ---------------------------------------------------------------------------
# Minimal Home Assistant stubs
# ---------------------------------------------------------------------------

const = sys.modules.setdefault("homeassistant.const", types.ModuleType("homeassistant.const"))

switch_mod = types.ModuleType("homeassistant.components.switch")


class SwitchEntity:  # pragma: no cover - simple stub
    pass


switch_mod.SwitchEntity = SwitchEntity
sys.modules["homeassistant.components.switch"] = switch_mod

entity_platform = types.ModuleType("homeassistant.helpers.entity_platform")


class AddEntitiesCallback:  # pragma: no cover - simple stub
    pass


entity_platform.AddEntitiesCallback = AddEntitiesCallback
sys.modules["homeassistant.helpers.entity_platform"] = entity_platform

# ---------------------------------------------------------------------------
# Actual tests
# ---------------------------------------------------------------------------

from custom_components.thessla_green_modbus.switch import (
    SWITCH_ENTITIES,
    ThesslaGreenSwitch,
)


def test_switch_creation_and_state(mock_coordinator):
    """Test creation and state changes of switch entity."""
    mock_coordinator.data["on_off_panel_mode"] = 1
    switch = ThesslaGreenSwitch(
        mock_coordinator, "on_off_panel_mode", SWITCH_ENTITIES["on_off_panel_mode"]
    )
    assert switch.is_on is True

    mock_coordinator.data["on_off_panel_mode"] = 0
    assert switch.is_on is False


def test_switch_turn_on_off(mock_coordinator):
    mock_coordinator.data["on_off_panel_mode"] = 0
    switch = ThesslaGreenSwitch(
        mock_coordinator, "on_off_panel_mode", SWITCH_ENTITIES["on_off_panel_mode"]
    )
    asyncio.run(switch.async_turn_on())
    mock_coordinator.async_write_register.assert_awaited_with(
        "on_off_panel_mode", 1, refresh=False
    )
    mock_coordinator.async_request_refresh.assert_awaited_once()
    mock_coordinator.async_write_register.reset_mock()
    mock_coordinator.async_request_refresh.reset_mock()

    asyncio.run(switch.async_turn_off())
    mock_coordinator.async_write_register.assert_awaited_with(
        "on_off_panel_mode", 0, refresh=False
    )
    mock_coordinator.async_request_refresh.assert_awaited_once()
