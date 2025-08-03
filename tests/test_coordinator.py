import importlib
import os
import sys
import types
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Ensure repository root is on path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))


@pytest.fixture(autouse=True)
def stub_homeassistant():
    """Provide minimal stubs for Home Assistant modules used by coordinator."""
    ha = types.ModuleType("homeassistant")
    config_entries = types.ModuleType("homeassistant.config_entries")
    const = types.ModuleType("homeassistant.const")
    core = types.ModuleType("homeassistant.core")
    helpers = types.ModuleType("homeassistant.helpers.update_coordinator")

    class ConfigEntry:
        def __init__(self, data):
            self.data = data
    config_entries.ConfigEntry = ConfigEntry

    const.CONF_HOST = "host"
    const.CONF_PORT = "port"

    class HomeAssistant:
        pass
    core.HomeAssistant = HomeAssistant

    class DataUpdateCoordinator:
        def __init__(self, hass, logger, name=None, update_interval=None):
            self.hass = hass
            self.logger = logger
            self.name = name
            self.update_interval = update_interval
        def __class_getitem__(cls, item):
            return cls
        async def async_request_refresh(self):
            pass
    class UpdateFailed(Exception):
        pass
    helpers.DataUpdateCoordinator = DataUpdateCoordinator
    helpers.UpdateFailed = UpdateFailed

    modules = {
        "homeassistant": ha,
        "homeassistant.config_entries": config_entries,
        "homeassistant.const": const,
        "homeassistant.core": core,
        "homeassistant.helpers.update_coordinator": helpers,
    }
    for name, module in modules.items():
        sys.modules[name] = module
    try:
        yield
    finally:
        for name in modules:
            sys.modules.pop(name, None)


@pytest.fixture
def coordinator():
    const_module = importlib.import_module("custom_components.thessla_green_modbus.const")
    module = importlib.import_module("custom_components.thessla_green_modbus.coordinator")
    ConfigEntry = sys.modules["homeassistant.config_entries"].ConfigEntry

    entry = ConfigEntry({
        const_module.CONF_HOST: "127.0.0.1",
        const_module.CONF_PORT: 502,
        const_module.CONF_SLAVE_ID: 1,
    })
    hass = MagicMock()
    coord = module.ThesslaGreenCoordinator(
        hass,
        entry.data[const_module.CONF_HOST],
        entry.data[const_module.CONF_PORT],
        entry.data[const_module.CONF_SLAVE_ID],
        const_module.DEFAULT_SCAN_INTERVAL,
        const_module.DEFAULT_TIMEOUT,
        const_module.DEFAULT_RETRY,
    )
    coord._client = MagicMock()
    return coord


def test_async_write_invalid_register(coordinator):
    result = asyncio.run(coordinator.async_write_register("invalid", 1))
    assert result is False
    coordinator._client.write_register.assert_not_called()


def test_success_triggers_refresh(coordinator):
    with patch("custom_components.thessla_green_modbus.coordinator.ModbusTcpClient") as mock_client_class:
        mock_client = MagicMock()
        mock_client.connect.return_value = True
        response = MagicMock()
        response.isError.return_value = False
        mock_client.write_register.return_value = response
        mock_client_class.return_value = mock_client

        result = asyncio.run(
            coordinator.async_write_register("supply_air_temperature_manual", 20)
        )

    assert result is True
