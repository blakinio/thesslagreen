"""Test configuration for ThesslaGreen Modbus integration."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import os
import sys
import types

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

try:
    from homeassistant.core import HomeAssistant
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
    from homeassistant.exceptions import ConfigEntryNotReady
except ModuleNotFoundError:  # pragma: no cover - simplify test environment
    ha = types.ModuleType("homeassistant")
    core = types.ModuleType("homeassistant.core")
    config_entries = types.ModuleType("homeassistant.config_entries")
    helpers = types.ModuleType("homeassistant.helpers.update_coordinator")
    exceptions = types.ModuleType("homeassistant.exceptions")
    const = types.ModuleType("homeassistant.const")

    class HomeAssistant:  # type: ignore[override]
        async def async_add_executor_job(self, func, *args):  # minimal stub
            return func(*args)

    class ConfigEntry:  # type: ignore[override]
        pass

    class DataUpdateCoordinator:  # type: ignore[override]
        def __init__(self, hass, logger, name=None, update_interval=None):
            self.hass = hass
            self.logger = logger
            self.name = name
            self.update_interval = update_interval

    class UpdateFailed(Exception):
        pass

    class ConfigEntryNotReady(Exception):
        pass

    core.HomeAssistant = HomeAssistant
    config_entries.ConfigEntry = ConfigEntry
    helpers.DataUpdateCoordinator = DataUpdateCoordinator
    helpers.UpdateFailed = UpdateFailed
    exceptions.ConfigEntryNotReady = ConfigEntryNotReady
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

    sys.modules["homeassistant"] = ha
    sys.modules["homeassistant.core"] = core
    sys.modules["homeassistant.config_entries"] = config_entries
    sys.modules["homeassistant.helpers.update_coordinator"] = helpers
    sys.modules["homeassistant.exceptions"] = exceptions
    sys.modules["homeassistant.const"] = const

DOMAIN = "thessla_green_modbus"


@pytest.fixture
def hass():
    """Return a mock Home Assistant instance."""
    return MagicMock(spec=HomeAssistant)


@pytest.fixture
def mock_config_entry():
    """Return a mock config entry."""
    config_entry = MagicMock(spec=ConfigEntry)
    config_entry.domain = DOMAIN
    config_entry.entry_id = "test_entry_id"
    config_entry.data = {
        "host": "192.168.1.100",
        "port": 502,
        "slave_id": 10,
    }
    config_entry.options = {
        "scan_interval": 30,
        "timeout": 10,
        "retry": 3,
    }
    return config_entry


@pytest.fixture
def mock_coordinator():
    """Return a mock coordinator."""
    coordinator = MagicMock()
    coordinator.host = "192.168.1.100"
    coordinator.port = 502
    coordinator.slave_id = 10
    coordinator.last_update_success = True
    coordinator.data = {
        "outside_temperature": 15.5,
        "supply_temperature": 20.0,
        "exhaust_temperature": 18.0,
        "mode": 0,
        "on_off_panel_mode": 1,
        "supply_percentage": 50,
    }
    coordinator.device_info = {
        "device_name": "ThesslaGreen AirPack",
        "firmware": "4.85.0",
        "serial_number": "S/N: 1234 5678 9abc",
    }
    coordinator.capabilities = {
        "constant_flow": True,
        "gwc_system": True,
        "bypass_system": True,
    }
    coordinator.available_registers = {
        "input_registers": {"outside_temperature", "supply_temperature", "exhaust_temperature"},
        "holding_registers": {"mode", "on_off_panel_mode", "air_flow_rate_manual"},
        "coil_registers": {"power_supply_fans", "bypass"},
        "discrete_inputs": {"expansion", "contamination_sensor"},
    }
    coordinator.async_write_register = AsyncMock(return_value=True)
    coordinator.async_request_refresh = AsyncMock()
    return coordinator


