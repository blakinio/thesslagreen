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
from custom_components.thessla_green_modbus.select import ThesslaGreenSelect  # noqa: E402
from custom_components.thessla_green_modbus.modbus_exceptions import (  # noqa: E402
    ConnectionException,
)
from custom_components.thessla_green_modbus.entity_mappings import (  # noqa: E402
    ENTITY_MAPPINGS,
)
from custom_components.thessla_green_modbus.select import (  # noqa: E402
    ThesslaGreenSelect,
)


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
    mock_coordinator.async_write_register.assert_awaited_with("mode", 1, offset=0)
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


def test_select_modbus_error_creates_issue(mock_coordinator):
    """Modbus failures should be surfaced through issues helper."""

    mock_coordinator.data["mode"] = 0
    address = 4208
    select_entity = ThesslaGreenSelect(
        mock_coordinator, "mode", address, ENTITY_MAPPINGS["select"]["mode"]
    )
    mock_coordinator.async_write_register = AsyncMock(
        side_effect=ConnectionException("write failed")
    )
    select_entity.hass = MagicMock(
        helpers=types.SimpleNamespace(
            issue=types.SimpleNamespace(async_create_issue=AsyncMock())
        )
    )

    asyncio.run(select_entity.async_select_option("manual"))

    select_entity.hass.helpers.issue.async_create_issue.assert_called_once()
    mock_coordinator.async_request_refresh.assert_not_awaited()


def test_select_definitions_single_source():
    """Ensure select definitions come from central ENTITY_MAPPINGS."""
    assert not hasattr(select, "SELECT_DEFINITIONS")
    assert "mode" in ENTITY_MAPPINGS["select"]
