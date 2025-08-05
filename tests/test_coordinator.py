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
helpers = types.ModuleType("homeassistant.helpers.update_coordinator")
exceptions = types.ModuleType("homeassistant.exceptions")
config_entries = types.ModuleType("homeassistant.config_entries")
pymodbus = types.ModuleType("pymodbus")
pymodbus_client = types.ModuleType("pymodbus.client")

const.CONF_HOST = "host"
const.CONF_PORT = "port"


class HomeAssistant:
    pass


core.HomeAssistant = HomeAssistant


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

modules = {
    "homeassistant": ha,
    "homeassistant.const": const,
    "homeassistant.core": core,
    "homeassistant.helpers.update_coordinator": helpers,
    "homeassistant.exceptions": exceptions,
    "homeassistant.config_entries": config_entries,
    "pymodbus": pymodbus,
    "pymodbus.client": pymodbus_client,
}

sys.modules.update(modules)

# Ensure repository root is on path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from custom_components.thessla_green_modbus.coordinator import ThesslaGreenCoordinator


@pytest.mark.asyncio
async def test_async_write_invalid_register():
    """Return False on unknown register and avoid executor call."""
    hass = MagicMock()
    hass.async_add_executor_job = AsyncMock(return_value=False)
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
    result = await coordinator.async_write_register("invalid", 1)
    assert result is False
    hass.async_add_executor_job.assert_not_awaited()


@pytest.mark.asyncio
async def test_async_write_success_triggers_executor():
    """Successful write should call executor job."""
    hass = MagicMock()
    hass.async_add_executor_job = AsyncMock(return_value=True)
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
    with patch("custom_components.thessla_green_modbus.coordinator.ModbusTcpClient") as mock_client_cls:
        client = MagicMock()
        mock_client_cls.return_value = client
        client.connect.return_value = True
        response = MagicMock()
        response.isError.return_value = False
        client.write_register.return_value = response
        result = await coordinator.async_write_register("mode", 1)

    assert result is True
    hass.async_add_executor_job.assert_awaited()
