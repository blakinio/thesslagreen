"""Tests for ThesslaGreenSwitch entity."""

import asyncio
import sys
import types
from unittest.mock import AsyncMock, patch

import pytest

from custom_components.thessla_green_modbus.modbus_exceptions import ConnectionException

# ---------------------------------------------------------------------------
# Minimal Home Assistant stubs
# ---------------------------------------------------------------------------

const = sys.modules.setdefault("homeassistant.const", types.ModuleType("homeassistant.const"))
const.PERCENTAGE = "%"


class UnitOfElectricPotential:  # pragma: no cover - enum stub
    VOLT = "V"


class UnitOfTemperature:  # pragma: no cover - enum stub
    CELSIUS = "°C"


class UnitOfTime:  # pragma: no cover - enum stub
    SECONDS = "s"
    MINUTES = "min"
    HOURS = "h"
    DAYS = "d"


class UnitOfVolumeFlowRate:  # pragma: no cover - enum stub
    CUBIC_METERS_PER_HOUR = "m³/h"


const.UnitOfElectricPotential = UnitOfElectricPotential
const.UnitOfTemperature = UnitOfTemperature
const.UnitOfTime = UnitOfTime
const.UnitOfVolumeFlowRate = UnitOfVolumeFlowRate

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


class DataUpdateCoordinator:  # pragma: no cover - simple stub
    def __init__(self, *args, **kwargs):
        pass

    @classmethod
    def __class_getitem__(cls, item):  # pragma: no cover - allow subscripting
        return cls


helpers_uc.CoordinatorEntity = CoordinatorEntity
helpers_uc.DataUpdateCoordinator = DataUpdateCoordinator

binary_sensor_mod = types.ModuleType("homeassistant.components.binary_sensor")


class _BinarySensorDeviceClass:  # pragma: no cover - enum stub
    def __getattr__(self, name):  # pragma: no cover - allow any attribute
        return name.lower()


BinarySensorDeviceClass = _BinarySensorDeviceClass()


binary_sensor_mod.BinarySensorDeviceClass = BinarySensorDeviceClass
sys.modules["homeassistant.components.binary_sensor"] = binary_sensor_mod

sensor_mod = types.ModuleType("homeassistant.components.sensor")


class SensorDeviceClass:  # pragma: no cover - enum stub
    TEMPERATURE = "temperature"
    VOLTAGE = "voltage"
    POWER = "power"
    ENERGY = "energy"


class SensorStateClass:  # pragma: no cover - enum stub
    MEASUREMENT = "measurement"
    TOTAL_INCREASING = "total_increasing"


sensor_mod.SensorDeviceClass = SensorDeviceClass
sensor_mod.SensorStateClass = SensorStateClass
sys.modules["homeassistant.components.sensor"] = sensor_mod

# ---------------------------------------------------------------------------
# Actual tests
# ---------------------------------------------------------------------------

from custom_components.thessla_green_modbus import switch  # noqa: E402
from custom_components.thessla_green_modbus.const import DOMAIN  # noqa: E402
from custom_components.thessla_green_modbus.entity_mappings import ENTITY_MAPPINGS  # noqa: E402
from custom_components.thessla_green_modbus.switch import ThesslaGreenSwitch  # noqa: E402

# Ensure required test mapping is present when dynamic generation is unavailable
ENTITY_MAPPINGS.setdefault("switch", {})
ENTITY_MAPPINGS["switch"].setdefault(
    "bypass",
    {
        "register": "bypass",
        "register_type": "coil_registers",
        "translation_key": "bypass",
        "icon": "mdi:pipe-leak",
    },
)


def test_switch_creation_and_state(mock_coordinator):
    """Test creation and state changes of coil switch."""
    mock_coordinator.data["bypass"] = 1
    address = 9
    switch_entity = ThesslaGreenSwitch(
        mock_coordinator, "bypass", address, ENTITY_MAPPINGS["switch"]["bypass"]
    )
    assert switch_entity.is_on is True  # nosec B101

    mock_coordinator.data["bypass"] = 0
    assert switch_entity.is_on is False  # nosec B101


def test_switch_turn_on_off(mock_coordinator):
    mock_coordinator.data["bypass"] = 0
    address = 9
    switch_entity = ThesslaGreenSwitch(
        mock_coordinator, "bypass", address, ENTITY_MAPPINGS["switch"]["bypass"]
    )
    asyncio.run(switch_entity.async_turn_on())
    mock_coordinator.async_write_register.assert_awaited_with("bypass", 1, refresh=False, offset=0)
    mock_coordinator.async_request_refresh.assert_awaited_once()
    mock_coordinator.async_write_register.reset_mock()
    mock_coordinator.async_request_refresh.reset_mock()

    mock_coordinator.data["bypass"] = 1
    asyncio.run(switch_entity.async_turn_off())
    mock_coordinator.async_write_register.assert_awaited_with("bypass", 0, refresh=False, offset=0)
    mock_coordinator.async_request_refresh.assert_awaited_once()


def test_switch_turn_on_modbus_failure(mock_coordinator):
    """Ensure Modbus errors are surfaced when turning on the switch."""
    address = 9
    switch_entity = ThesslaGreenSwitch(
        mock_coordinator, "bypass", address, ENTITY_MAPPINGS["switch"]["bypass"]
    )
    mock_coordinator.async_write_register = AsyncMock(side_effect=ConnectionException("fail"))
    with pytest.raises(ConnectionException):
        asyncio.run(switch_entity.async_turn_on())


def test_switch_definitions_single_source():
    """Ensure switch definitions come from central ENTITY_MAPPINGS."""
    assert not hasattr(switch, "SWITCH_ENTITIES")
    assert "bypass" in ENTITY_MAPPINGS["switch"]


def test_switch_icon_fallback(hass, mock_config_entry, mock_coordinator):
    """Switch setups without an explicit icon use the default icon."""
    config = {
        "register": "mock_register",
        "register_type": "coil_registers",
        "translation_key": "mock_switch_no_icon",
    }
    mock_coordinator.data["mock_register"] = 0
    mock_coordinator.available_registers = {"coil_registers": {"mock_register"}}
    mock_coordinator.force_full_register_list = False
    hass.data = {DOMAIN: {mock_config_entry.entry_id: mock_coordinator}}
    added = []

    def async_add_entities(entities, update=False):  # pragma: no cover - test helper
        added.extend(entities)

    with patch.dict(ENTITY_MAPPINGS["switch"], {"mock_switch_no_icon": config}):
        asyncio.run(switch.async_setup_entry(hass, mock_config_entry, async_add_entities))

    assert len(added) == 1
    assert added[0]._attr_icon == "mdi:toggle-switch"
