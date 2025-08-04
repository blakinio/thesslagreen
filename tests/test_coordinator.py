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
    """Provide minimal stubs for Home Assistant and pymodbus modules."""
    ha = types.ModuleType("homeassistant")
    const = types.ModuleType("homeassistant.const")
    core = types.ModuleType("homeassistant.core")
    helpers = types.ModuleType("homeassistant.helpers.update_coordinator")
    exceptions = types.ModuleType("homeassistant.exceptions")
    pymodbus = types.ModuleType("pymodbus")
    pymodbus_client = types.ModuleType("pymodbus.client")

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

    class ConfigEntryNotReady(Exception):
        pass
    exceptions.ConfigEntryNotReady = ConfigEntryNotReady

    class ModbusTcpClient:
        pass
    pymodbus_client.ModbusTcpClient = ModbusTcpClient

    modules = {
        "homeassistant": ha,
        "homeassistant.const": const,
        "homeassistant.core": core,
        "homeassistant.helpers.update_coordinator": helpers,
        "homeassistant.exceptions": exceptions,
        "pymodbus": pymodbus,
        "pymodbus.client": pymodbus_client,
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
    Coordinator = getattr(module, "ThesslaGreenCoordinator", None)
    if Coordinator is None:
        Coordinator = getattr(module, "ThesslaGreenDataCoordinator")

    hass = MagicMock()
    kwargs = {
        "hass": hass,
        "host": "127.0.0.1",
        "port": 502,
        "slave_id": 1,
        "scan_interval": 30,
        "timeout": 10,
        "retry": 3,
    }
    import inspect
    params = inspect.signature(Coordinator.__init__).parameters
    accepted = {k: v for k, v in kwargs.items() if k in params}
    coord = Coordinator(**accepted)
    return coord


def test_async_write_invalid_register(coordinator):
    with patch("custom_components.thessla_green_modbus.coordinator.ModbusTcpClient") as mock_client:
        result = asyncio.run(coordinator.async_write_register("invalid", 1))
        assert result is False
        mock_client.assert_not_called()


def test_success_triggers_refresh(coordinator):
    coordinator.async_request_refresh = AsyncMock()
    with patch("custom_components.thessla_green_modbus.coordinator.ModbusTcpClient") as mock_client_cls:
        client = MagicMock()
        mock_client_cls.return_value = client
        client.connect.return_value = True
        response = MagicMock()
        response.isError.return_value = False
        client.write_register.return_value = response

        result = asyncio.run(coordinator.async_write_register("mode", 1))

    assert result is True
    coordinator.async_request_refresh.assert_awaited_once()
