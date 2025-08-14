"""Tests for ThesslaGreenSwitch entity."""

import asyncio
import sys
import types
from unittest.mock import AsyncMock

import pytest

from custom_components.thessla_green_modbus.modbus_exceptions import ConnectionException

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

from custom_components.thessla_green_modbus.switch import (  # noqa: E402
    SWITCH_ENTITIES,
    ThesslaGreenSwitch,
)


def test_switch_creation_and_state(mock_coordinator):
    """Test creation and state changes of coil switch."""
    mock_coordinator.data["bypass"] = 1
    switch = ThesslaGreenSwitch(mock_coordinator, "bypass", SWITCH_ENTITIES["bypass"])
    assert switch.is_on is True  # nosec B101

    mock_coordinator.data["bypass"] = 0
    assert switch.is_on is False  # nosec B101


def test_switch_turn_on_off(mock_coordinator):
    mock_coordinator.data["bypass"] = 0
    switch = ThesslaGreenSwitch(mock_coordinator, "bypass", SWITCH_ENTITIES["bypass"])
    asyncio.run(switch.async_turn_on())
    mock_coordinator.async_write_register.assert_awaited_with("bypass", 1, refresh=False)
    mock_coordinator.async_request_refresh.assert_awaited_once()
    mock_coordinator.async_write_register.reset_mock()
    mock_coordinator.async_request_refresh.reset_mock()

    mock_coordinator.data["bypass"] = 1
    asyncio.run(switch.async_turn_off())
    mock_coordinator.async_write_register.assert_awaited_with("bypass", 0, refresh=False)
    mock_coordinator.async_request_refresh.assert_awaited_once()


def test_switch_turn_on_modbus_failure(mock_coordinator):
    """Ensure Modbus errors are surfaced when turning on the switch."""
    switch = ThesslaGreenSwitch(mock_coordinator, "bypass", SWITCH_ENTITIES["bypass"])
    mock_coordinator.async_write_register = AsyncMock(side_effect=ConnectionException("fail"))
    with pytest.raises(ConnectionException):
        asyncio.run(switch.async_turn_on())
