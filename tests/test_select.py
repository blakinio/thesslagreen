"""Tests for ThesslaGreenSelect entity."""

import asyncio
import sys
import types
from unittest.mock import AsyncMock, MagicMock

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

select_mod = types.ModuleType("homeassistant.components.select")


class SelectEntity:  # pragma: no cover - simple stub
    pass


select_mod.SelectEntity = SelectEntity
sys.modules["homeassistant.components.select"] = select_mod

entity_platform = types.ModuleType("homeassistant.helpers.entity_platform")


class AddEntitiesCallback:  # pragma: no cover - simple stub
    pass


entity_platform.AddEntitiesCallback = AddEntitiesCallback
sys.modules["homeassistant.helpers.entity_platform"] = entity_platform

helpers_uc = sys.modules.setdefault(
    "homeassistant.helpers.update_coordinator",
    types.ModuleType("homeassistant.helpers.update_coordinator"),
)


class DataUpdateCoordinator:  # pragma: no cover - simple stub
    def __init__(self, *args, **kwargs):
        pass

    @classmethod
    def __class_getitem__(cls, item):  # pragma: no cover - allow subscripting
        return cls


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

from custom_components.thessla_green_modbus import select  # noqa: E402
from custom_components.thessla_green_modbus.entity_mappings import ENTITY_MAPPINGS  # noqa: E402
from custom_components.thessla_green_modbus.modbus_exceptions import (  # noqa: E402
    ConnectionException,
)
from custom_components.thessla_green_modbus.select import ThesslaGreenSelect  # noqa: E402


def test_select_creation_and_state(mock_coordinator):
    """Test creation and state changes of select entity."""
    mock_coordinator.data["mode"] = 0
    address = 4208
    select_entity = ThesslaGreenSelect(
        mock_coordinator, "mode", address, ENTITY_MAPPINGS["select"]["mode"]
    )
    assert select_entity.current_option == "auto"

    mock_coordinator.data["mode"] = 1
    assert select_entity.current_option == "manual"


def test_select_option_change(mock_coordinator):
    mock_coordinator.data["mode"] = 0
    address = 4208
    select_entity = ThesslaGreenSelect(
        mock_coordinator, "mode", address, ENTITY_MAPPINGS["select"]["mode"]
    )
    asyncio.run(select_entity.async_select_option("manual"))
    mock_coordinator.async_write_register.assert_awaited_with("mode", 1, refresh=False)
    mock_coordinator.async_request_refresh.assert_awaited_once()


def test_select_invalid_option(mock_coordinator):
    """Invalid options should not trigger Modbus writes."""

    mock_coordinator.data["mode"] = 0
    address = 4208
    select_entity = ThesslaGreenSelect(
        mock_coordinator, "mode", address, ENTITY_MAPPINGS["select"]["mode"]
    )
    mock_coordinator.async_write_register = AsyncMock()

    asyncio.run(select_entity.async_select_option("unsupported"))

    mock_coordinator.async_write_register.assert_not_awaited()
    mock_coordinator.async_request_refresh.assert_not_awaited()


def test_select_modbus_error_logs_and_returns(mock_coordinator):
    """Modbus failures should be logged and not raise."""

    mock_coordinator.data["mode"] = 0
    address = 4208
    select_entity = ThesslaGreenSelect(
        mock_coordinator, "mode", address, ENTITY_MAPPINGS["select"]["mode"]
    )
    mock_coordinator.async_write_register = AsyncMock(
        side_effect=ConnectionException("write failed")
    )
    select_entity.hass = MagicMock()

    asyncio.run(select_entity.async_select_option("manual"))

    mock_coordinator.async_request_refresh.assert_not_awaited()


def test_select_definitions_single_source():
    """Ensure select definitions come from central ENTITY_MAPPINGS."""
    assert not hasattr(select, "SELECT_DEFINITIONS")
    assert "mode" in ENTITY_MAPPINGS["select"]


def test_schedule_time_select_current_option(mock_coordinator):
    """Schedule select entities decode stored 'HH:MM' strings as current option."""
    from custom_components.thessla_green_modbus.schedule_helpers import TIME_SELECT_STATES

    defn = {
        "translation_key": "schedule_summer_mon_1",
        "icon": "mdi:clock-outline",
        "register_type": "holding_registers",
        "states": TIME_SELECT_STATES,
    }
    mock_coordinator.data["schedule_summer_mon_1"] = "04:00"
    entity = ThesslaGreenSelect(mock_coordinator, "schedule_summer_mon_1", 16, defn)
    assert entity.current_option == "04:00"
    assert "04:00" in entity._attr_options
    assert "23:30" in entity._attr_options


def test_schedule_time_select_write(mock_coordinator):
    """Selecting a time slot writes the decoded HH:MM string to the register."""
    from custom_components.thessla_green_modbus.schedule_helpers import TIME_SELECT_STATES

    defn = {
        "translation_key": "schedule_summer_mon_1",
        "icon": "mdi:clock-outline",
        "register_type": "holding_registers",
        "states": TIME_SELECT_STATES,
    }
    mock_coordinator.data["schedule_summer_mon_1"] = "04:00"
    entity = ThesslaGreenSelect(mock_coordinator, "schedule_summer_mon_1", 16, defn)
    asyncio.run(entity.async_select_option("06:30"))
    mock_coordinator.async_write_register.assert_awaited_with(
        "schedule_summer_mon_1", "06:30", refresh=False
    )


def test_schedule_time_select_unknown_for_disabled_slot(mock_coordinator):
    """A disabled slot (raw int 65535) that is not in options returns None."""
    from custom_components.thessla_green_modbus.schedule_helpers import TIME_SELECT_STATES

    defn = {
        "translation_key": "schedule_summer_mon_1",
        "icon": "mdi:clock-outline",
        "register_type": "holding_registers",
        "states": TIME_SELECT_STATES,
    }
    mock_coordinator.data["schedule_summer_mon_1"] = 65535
    entity = ThesslaGreenSelect(mock_coordinator, "schedule_summer_mon_1", 16, defn)
    assert entity.current_option is None


def test_schedule_registers_in_entity_mappings_time():
    """Real schedule registers resolved from JSON should land in ENTITY_MAPPINGS time."""
    time_keys = ENTITY_MAPPINGS.get("time", {})
    assert "schedule_summer_mon_1" in time_keys, (
        "schedule_summer_mon_1 should be a time entity (RW BCD time register)"
    )
    assert "schedule_summer_mon_1" not in ENTITY_MAPPINGS.get("sensor", {}), (
        "schedule_summer_mon_1 must not also be a sensor"
    )
    assert "schedule_summer_mon_1" not in ENTITY_MAPPINGS.get("select", {}), (
        "schedule_summer_mon_1 must not also be a select"
    )
