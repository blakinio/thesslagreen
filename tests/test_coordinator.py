"""Tests for ThesslaGreenCoordinator."""

import os
import sys
import types
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Stub minimal Home Assistant and pymodbus modules before importing the coordinator
ha = types.ModuleType("homeassistant")
const = types.ModuleType("homeassistant.const")
core = types.ModuleType("homeassistant.core")
helpers_pkg = types.ModuleType("homeassistant.helpers")
helpers = types.ModuleType("homeassistant.helpers.update_coordinator")
helpers_cv = types.ModuleType("homeassistant.helpers.config_validation")
helpers_dr = types.ModuleType("homeassistant.helpers.device_registry")
helpers_pkg.update_coordinator = helpers
helpers_pkg.config_validation = helpers_cv
helpers_pkg.device_registry = helpers_dr
exceptions = types.ModuleType("homeassistant.exceptions")
config_entries = types.ModuleType("homeassistant.config_entries")
pymodbus = types.ModuleType("pymodbus")
pymodbus_client = types.ModuleType("pymodbus.client")
pymodbus_exceptions = types.ModuleType("pymodbus.exceptions")
pymodbus_exceptions = types.ModuleType("pymodbus.exceptions")

const.CONF_HOST = "host"
const.CONF_PORT = "port"
const.CONF_SCAN_INTERVAL = "scan_interval"


class Platform:
    SENSOR = "sensor"
    BINARY_SENSOR = "binary_sensor"
    SELECT = "select"
    NUMBER = "number"
    SWITCH = "switch"
    CLIMATE = "climate"
    FAN = "fan"


const.Platform = Platform


class HomeAssistant:
    pass


core.HomeAssistant = HomeAssistant


class ServiceCall:
    pass


core.ServiceCall = ServiceCall


class ConfigEntry:
    def __init__(self, data):
        self.data = data


config_entries.ConfigEntry = ConfigEntry


class DataUpdateCoordinator:
    def __init__(self, hass, logger, name=None, update_interval=None):
        self.hass = hass
        self.logger = logger
        self.name = name
        self.update_interval = update_interval

    async def async_request_refresh(self):
        pass

    @classmethod
    def __class_getitem__(cls, item):
        return cls


helpers.DataUpdateCoordinator = DataUpdateCoordinator


class UpdateFailed(Exception):
    pass


helpers.UpdateFailed = UpdateFailed


class ConfigEntryNotReady(Exception):
    pass


exceptions.ConfigEntryNotReady = ConfigEntryNotReady


class ModbusTcpClient:
    def __init__(self, *args, **kwargs):
        pass


pymodbus_client.ModbusTcpClient = ModbusTcpClient


class ModbusException(Exception):
    pass


pymodbus_exceptions.ModbusException = ModbusException

modules = {
    "homeassistant": ha,
    "homeassistant.const": const,
    "homeassistant.core": core,
    "homeassistant.helpers": helpers_pkg,
    "homeassistant.helpers.update_coordinator": helpers,
    "homeassistant.helpers.config_validation": helpers_cv,
    "homeassistant.helpers.device_registry": helpers_dr,
    "homeassistant.exceptions": exceptions,
    "homeassistant.config_entries": config_entries,
    "pymodbus": pymodbus,
    "pymodbus.client": pymodbus_client,
    "pymodbus.exceptions": pymodbus_exceptions,
}

sys.modules.update(modules)

# Ensure repository root is on path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from custom_components.thessla_green_modbus.coordinator import ThesslaGreenCoordinator


@pytest.mark.asyncio
async def test_async_write_invalid_register():
    """Return False on unknown register and avoid client calls."""
    hass = MagicMock()
    coordinator = ThesslaGreenCoordinator(
        hass=hass,
        host="localhost",
        port=502,
        slave_id=1,
        scan_interval=30,
        timeout=10,
        retry=3,
        available_registers={
            "input_registers": set(),
            "holding_registers": set(),
            "coil_registers": set(),
            "discrete_inputs": set(),
        },
    )
    coordinator._client.write_register = AsyncMock(return_value=True)
    coordinator._client.write_coil = AsyncMock(return_value=True)
    result = await coordinator.async_write_register("invalid", 1)
    assert result is False
    coordinator._client.write_register.assert_not_awaited()
    coordinator._client.write_coil.assert_not_awaited()


@pytest.mark.asyncio
async def test_async_write_success_triggers_refresh():
    """Successful write should refresh coordinator."""
    hass = MagicMock()
    coordinator = ThesslaGreenCoordinator(
        hass=hass,
        host="localhost",
        port=502,
        slave_id=1,
        scan_interval=30,
        timeout=10,
        retry=3,
        available_registers={
            "input_registers": set(),
            "holding_registers": {"mode"},
            "coil_registers": set(),
            "discrete_inputs": set(),
        },
    )
    coordinator._client.write_register = AsyncMock(return_value=True)
    with patch.object(coordinator, "async_request_refresh", AsyncMock()) as mock_refresh:
        result = await coordinator.async_write_register("mode", 1)

    assert result is True
    mock_refresh.assert_awaited_once()
