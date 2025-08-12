"""Tests for ThesslaGreenNumber entity."""

import asyncio
import sys
import types
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from custom_components.thessla_green_modbus.modbus_exceptions import ConnectionException
from custom_components.thessla_green_modbus.multipliers import REGISTER_MULTIPLIERS
from custom_components.thessla_green_modbus.registers import HOLDING_REGISTERS

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

helpers = sys.modules.setdefault("homeassistant.helpers", types.ModuleType("homeassistant.helpers"))
helpers.__path__ = []  # mark as package
entity_helper = types.ModuleType("homeassistant.helpers.entity")


class EntityCategory:  # pragma: no cover - simple stub
    CONFIG = "config"


entity_helper.EntityCategory = EntityCategory
sys.modules["homeassistant.helpers.entity"] = entity_helper

coordinator_module = types.ModuleType("custom_components.thessla_green_modbus.coordinator")


class ThesslaGreenModbusCoordinator:  # pragma: no cover - simple stub
    def __init__(self, *args, **kwargs):
        self.available_registers = {"holding_registers": set()}
        self.capabilities = SimpleNamespace(basic_control=False)
        self.client = None
        self.slave_id = args[3] if len(args) > 3 else kwargs.get("slave_id", 0)

    async def _ensure_connection(self):
        return None

    async def async_request_refresh(self):
        return None

    def get_device_info(self):
        return {}

    async def async_write_register(self, *args, **kwargs):
        register, value = args[0], args[1]
        address = HOLDING_REGISTERS[register]
        multiplier = REGISTER_MULTIPLIERS.get(register, 1)
        raw = int(round(value / multiplier))
        await self.client.write_register(address, raw, slave=self.slave_id)
        return True


coordinator_module.ThesslaGreenModbusCoordinator = ThesslaGreenModbusCoordinator
sys.modules["custom_components.thessla_green_modbus.coordinator"] = coordinator_module

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

from custom_components.thessla_green_modbus.number import ENTITY_MAPPINGS, ThesslaGreenNumber


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


def test_number_set_value_modbus_failure(mock_coordinator):
    """Ensure Modbus errors are surfaced when setting the number."""
    mock_coordinator.data["required_temperature"] = 20
    entity_config = ENTITY_MAPPINGS["number"]["required_temperature"]
    number = ThesslaGreenNumber(mock_coordinator, "required_temperature", entity_config)

    mock_coordinator.async_write_register = AsyncMock(side_effect=ConnectionException("fail"))
    with pytest.raises(ConnectionException):
        asyncio.run(number.async_set_native_value(22))
    mock_coordinator.async_request_refresh.assert_not_awaited()


def test_number_set_value_write_failure(mock_coordinator):
    """Ensure failures to write registers raise RuntimeError."""
    mock_coordinator.data["required_temperature"] = 20
    entity_config = ENTITY_MAPPINGS["number"]["required_temperature"]
    number = ThesslaGreenNumber(mock_coordinator, "required_temperature", entity_config)

    mock_coordinator.async_write_register = AsyncMock(return_value=False)
    with pytest.raises(RuntimeError):
        asyncio.run(number.async_set_native_value(22))
    mock_coordinator.async_request_refresh.assert_not_awaited()


@pytest.mark.parametrize("exc_cls", [ValueError, OSError])
def test_number_set_value_other_errors(mock_coordinator, exc_cls):
    """Ensure ValueError and OSError propagate when setting the number."""
    mock_coordinator.data["required_temperature"] = 20
    entity_config = ENTITY_MAPPINGS["number"]["required_temperature"]
    number = ThesslaGreenNumber(mock_coordinator, "required_temperature", entity_config)

    mock_coordinator.async_write_register = AsyncMock(side_effect=exc_cls("fail"))
    with pytest.raises(exc_cls):
        asyncio.run(number.async_set_native_value(22))
    mock_coordinator.async_request_refresh.assert_not_awaited()
