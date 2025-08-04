import importlib
import os
import sys
import types
import asyncio
from unittest.mock import AsyncMock, MagicMock

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
    module = importlib.import_module("custom_components.thessla_green_modbus.coordinator")
    hass = MagicMock()
    coord = module.ThesslaGreenCoordinator(
        hass=hass,
        host="127.0.0.1",
        port=502,
        slave_id=1,
    )
    return coord


def test_async_write_invalid_register(coordinator):
    coordinator.hass.async_add_executor_job = AsyncMock()
    result = asyncio.run(coordinator.async_write_register("invalid", 1))
    assert result is False
    coordinator.hass.async_add_executor_job.assert_not_called()


def test_success_triggers_refresh(coordinator):
    coordinator.hass.async_add_executor_job = AsyncMock(return_value=True)

    result = asyncio.run(coordinator.async_write_register("mode", 1))
    assert result is True
    coordinator.hass.async_add_executor_job.assert_awaited_once()
