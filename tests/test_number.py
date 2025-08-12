"""Tests for ThesslaGreenNumber entity."""
import sys
import types
import asyncio
import pytest

# ---------------------------------------------------------------------------
# Minimal Home Assistant stubs
# ---------------------------------------------------------------------------

const = sys.modules.setdefault("homeassistant.const", types.ModuleType("homeassistant.const"))

# Units and constants
class UnitOfTemperature:  # pragma: no cover - simple stub
    CELSIUS = "°C"


class UnitOfTime:  # pragma: no cover - simple stub
    MINUTES = "min"
    HOURS = "h"


const.UnitOfTemperature = UnitOfTemperature
const.UnitOfTime = UnitOfTime
const.PERCENTAGE = "%"

number_mod = types.ModuleType("homeassistant.components.number")


class NumberEntity:  # pragma: no cover - simple stub
    pass


class NumberMode:  # pragma: no cover - simple stub
    SLIDER = "slider"
    BOX = "box"


number_mod.NumberEntity = NumberEntity
number_mod.NumberMode = NumberMode
sys.modules["homeassistant.components.number"] = number_mod

entity_platform = types.ModuleType("homeassistant.helpers.entity_platform")


class AddEntitiesCallback:  # pragma: no cover - simple stub
    pass


entity_platform.AddEntitiesCallback = AddEntitiesCallback
sys.modules["homeassistant.helpers.entity_platform"] = entity_platform

# ---------------------------------------------------------------------------
# Actual tests
# ---------------------------------------------------------------------------

from custom_components.thessla_green_modbus.number import (
    ENTITY_MAPPINGS,
    ThesslaGreenNumber,
)


def test_number_creation_and_state(mock_coordinator):
    """Test creation and state changes of number entity."""
    mock_coordinator.data["required_temperature"] = 20
    entity_config = ENTITY_MAPPINGS["number"]["required_temperature"]
    number = ThesslaGreenNumber(mock_coordinator, "required_temperature", entity_config)
    assert number.native_value == 20

    mock_coordinator.data["required_temperature"] = 21.5
    assert number.native_value == 21.5


def test_number_set_value(mock_coordinator):
    """Test setting a new value on the number entity."""
    mock_coordinator.data["required_temperature"] = 20
    entity_config = ENTITY_MAPPINGS["number"]["required_temperature"]
    number = ThesslaGreenNumber(mock_coordinator, "required_temperature", entity_config)

    asyncio.run(number.async_set_native_value(22))
    mock_coordinator.async_write_register.assert_awaited_with(
        "required_temperature", 22, refresh=False
    )
    mock_coordinator.async_request_refresh.assert_awaited_once()
