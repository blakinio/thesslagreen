"""Test configuration for ThesslaGreen Modbus integration."""
import sys
import types
import os
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

# Provide minimal Home Assistant stubs if the real package is not installed
try:  # pragma: no cover - we only execute the fallback when HA isn't available
    from homeassistant.core import HomeAssistant
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.helpers.update_coordinator import (
        DataUpdateCoordinator,
        UpdateFailed,
    )
except ModuleNotFoundError:  # pragma: no cover - executed in CI tests
    ha = types.ModuleType("homeassistant")
    core = types.ModuleType("homeassistant.core")
    config_entries = types.ModuleType("homeassistant.config_entries")
    helpers = types.ModuleType("homeassistant.helpers.update_coordinator")
    const = types.ModuleType("homeassistant.const")
    exceptions = types.ModuleType("homeassistant.exceptions")

    class HomeAssistant:  # type: ignore
        pass

    class ConfigEntry:  # type: ignore
        pass

    class DataUpdateCoordinator:  # type: ignore
        def __init__(self, hass, logger, name=None, update_interval=None):
            self.hass = hass
            self.logger = logger
            self.name = name
            self.update_interval = update_interval

        async def async_request_refresh(self) -> None:  # pragma: no cover - stub
            pass

        def __class_getitem__(cls, item):  # pragma: no cover - stub
            return cls

    class UpdateFailed(Exception):  # type: ignore
        pass

    core.HomeAssistant = HomeAssistant
    config_entries.ConfigEntry = ConfigEntry
    helpers.DataUpdateCoordinator = DataUpdateCoordinator
    helpers.UpdateFailed = UpdateFailed

    # Minimal constants required by the integration
    const.CONF_HOST = "host"
    const.CONF_PORT = "port"
    const.CONF_SCAN_INTERVAL = "scan_interval"

    class Platform(str):  # type: ignore
        SENSOR = "sensor"
        BINARY_SENSOR = "binary_sensor"
        SELECT = "select"
        NUMBER = "number"
        SWITCH = "switch"
        CLIMATE = "climate"

    const.Platform = Platform

    class ConfigEntryNotReady(Exception):  # type: ignore
        pass

    exceptions.ConfigEntryNotReady = ConfigEntryNotReady

    sys.modules.setdefault("homeassistant", ha)
    sys.modules.setdefault("homeassistant.core", core)
    sys.modules.setdefault("homeassistant.config_entries", config_entries)
    sys.modules.setdefault("homeassistant.helpers", types.ModuleType("homeassistant.helpers"))
    sys.modules.setdefault(
        "homeassistant.helpers.update_coordinator", helpers
    )
    sys.modules.setdefault("homeassistant.const", const)
    sys.modules.setdefault("homeassistant.exceptions", exceptions)

    from homeassistant.core import HomeAssistant  # type: ignore
    from homeassistant.config_entries import ConfigEntry  # type: ignore
    from homeassistant.helpers.update_coordinator import (  # type: ignore
        DataUpdateCoordinator,
        UpdateFailed,
    )

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from custom_components.thessla_green_modbus.const import DOMAIN
from custom_components.thessla_green_modbus.coordinator import ThesslaGreenCoordinator


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
    coordinator = MagicMock(spec=ThesslaGreenCoordinator)
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


@pytest.fixture
def mock_modbus_client():
    """Return a mock Modbus client."""
    with patch("custom_components.thessla_green_modbus.coordinator.ModbusTcpClient") as mock:
        client = MagicMock()
        client.connect.return_value = True
        client.connected = True
        mock.return_value = client
        yield client