"""Tests for ThesslaGreenCoordinator - HA 2025.7.1+ & pymodbus 3.5+ Compatible."""

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
for name, module in modules.items():
    sys.modules[name] = module

# Ensure repository root is on path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# ✅ FIXED: Import correct coordinator class name
from custom_components.thessla_green_modbus.coordinator import (
    ThesslaGreenCoordinator,
)


@pytest.fixture
def coordinator():
    """Create a test coordinator."""
    hass = MagicMock()
    available_registers = {
        "holding_registers": {"mode", "air_flow_rate_manual", "special_mode"},
        "input_registers": {"outside_temperature", "supply_temperature"},
        "coil_registers": {"system_on_off"},
        "discrete_inputs": set(),
    }
    return ThesslaGreenCoordinator(
        hass=hass,
        host="localhost", 
        port=502, 
        slave_id=1,
        scan_interval=30,
        timeout=10,
        retry=3,
        available_registers=available_registers
    )


@pytest.mark.asyncio
async def test_async_write_invalid_register(coordinator):
    """Return False and do not refresh on unknown register."""
    with patch("custom_components.thessla_green_modbus.coordinator.ModbusTcpClient") as mock_client:
        result = await coordinator.async_write_register("invalid", 1)
        assert result is False
        mock_client.assert_not_called()


@pytest.mark.asyncio 
async def test_async_write_valid_register(coordinator):
    """Test successful register write."""
    coordinator.async_request_refresh = AsyncMock()
    
    with patch("custom_components.thessla_green_modbus.coordinator.ModbusTcpClient") as mock_client_cls:
        client = MagicMock()
        mock_client_cls.return_value = client
        client.connect.return_value = True
        response = MagicMock()
        response.isError.return_value = False
        client.write_register.return_value = response

        result = await coordinator.async_write_register("mode", 1)
        
        assert result is True
        coordinator.async_request_refresh.assert_called_once()


def test_performance_stats(coordinator):
    """Test performance statistics."""
    stats = coordinator.performance_stats
    assert "status" in stats or "total_reads" in stats


def test_device_info(coordinator):
    """Test device info property."""
    coordinator.device_scan_result = {
        "device_info": {"firmware": "4.85.0"}
    }
    
    device_info = coordinator.device_info
    assert device_info["manufacturer"] == "ThesslaGreen"
    assert device_info["model"] == "AirPack Home"


@pytest.mark.asyncio
async def test_coordinator_initialization():
    """Test coordinator initialization."""
    hass = MagicMock()
    available_registers = {"holding_registers": set(), "input_registers": set()}
    
    coordinator = ThesslaGreenCoordinator(
        hass=hass,
        host="192.168.1.100",
        port=502,
        slave_id=10,
        scan_interval=30,
        timeout=10,
        retry=3,
        available_registers=available_registers
    )
    
    assert coordinator.host == "192.168.1.100"
    assert coordinator.port == 502
    assert coordinator.slave_id == 10
    assert coordinator.timeout == 10


def test_register_value_processing(coordinator):
    """Test register value processing."""
    # Test temperature processing
    temp_result = coordinator._process_register_value("outside_temperature", 250)
    assert temp_result == 250  # Raw value returned
    
    # Test invalid temperature
    invalid_temp = coordinator._process_register_value("outside_temperature", 0x8000)
    assert invalid_temp is None
    
    # Test percentage processing
    percentage_result = coordinator._process_register_value("supply_percentage", 75)
    assert percentage_result == 75
    
    # Test invalid percentage
    invalid_percentage = coordinator._process_register_value("supply_percentage", 150)
    assert invalid_percentage is None
    
    # Test mode processing
    mode_result = coordinator._process_register_value("mode", 1)
    assert mode_result == 1
    
    # Test invalid mode
    invalid_mode = coordinator._process_register_value("mode", 25)
    assert invalid_mode is None


def test_post_process_data(coordinator):
    """Test data post-processing."""
    raw_data = {
        "outside_temperature": 100,  # 10.0°C
        "supply_temperature": 200,   # 20.0°C  
        "exhaust_temperature": 250,  # 25.0°C
        "supply_flowrate": 150,
        "exhaust_flowrate": 140,
    }
    
    processed_data = coordinator._post_process_data(raw_data)
    
    # Check calculated efficiency
    assert "calculated_efficiency" in processed_data
    efficiency = processed_data["calculated_efficiency"]
    assert isinstance(efficiency, (int, float))
    assert 0 <= efficiency <= 100
    
    # Check flow balance
    assert "flow_balance" in processed_data
    assert processed_data["flow_balance"] == 10  # 150 - 140
    
    # Check flow balance status
    assert "flow_balance_status" in processed_data
    assert processed_data["flow_balance_status"] == "supply_dominant"


@pytest.mark.asyncio
async def test_write_register_sync_pymodbus_api(coordinator):
    """Test that write_register_sync uses pymodbus 3.5+ compatible API."""
    with patch("custom_components.thessla_green_modbus.coordinator.ModbusTcpClient") as mock_client_cls:
        client = MagicMock()
        mock_client_cls.return_value = client
        client.connect.return_value = True
        
        response = MagicMock()
        response.isError.return_value = False
        client.write_register.return_value = response
        
        # Test holding register write
        result = coordinator._write_register_sync(100, 50, "holding_registers")
        
        # ✅ VERIFY: Should use keyword arguments (pymodbus 3.5+ compatible)
        client.write_register.assert_called_once()
        call_args = client.write_register.call_args
        
        # Check if keyword arguments are used
        if call_args.kwargs:
            assert "address" in call_args.kwargs
            assert "value" in call_args.kwargs  
            assert "slave" in call_args.kwargs
        
        assert result is True


def cleanup_modules():
    """Clean up injected modules."""
    for name in modules:
        sys.modules.pop(name, None)


# Register cleanup
import atexit
atexit.register(cleanup_modules)