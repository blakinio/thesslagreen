"""Tests for ThesslaGreenModbusCoordinator - HA 2025.7.1+ & pymodbus 3.5+ Compatible."""

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
const.CONF_NAME = "name"


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
    ThesslaGreenModbusCoordinator,
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
    coordinator = ThesslaGreenModbusCoordinator(
        hass=hass,
        host="localhost",
        port=502,
        slave_id=1,
        name="test",
        scan_interval=30,
        timeout=10,
        retry=3,
    )
    coordinator.available_registers = available_registers
    return coordinator


@pytest.mark.asyncio
async def test_async_write_invalid_register(coordinator):
    """Return False and do not refresh on unknown register."""
    coordinator._ensure_connection = AsyncMock()
    result = await coordinator.async_write_register("invalid", 1)
    assert result is False


@pytest.mark.asyncio
async def test_async_write_valid_register(coordinator):
    """Test successful register write."""
    coordinator.async_request_refresh = AsyncMock()
    coordinator._ensure_connection = AsyncMock()
    client = MagicMock()
    response = MagicMock()
    response.isError.return_value = False
    client.write_register = AsyncMock(return_value=response)
    coordinator.client = client

    result = await coordinator.async_write_register("mode", 1)

    assert result is True
    coordinator.async_request_refresh.assert_called_once()


def test_performance_stats(coordinator):
    """Test performance statistics."""
    stats = coordinator.performance_stats
    assert "status" in stats or "total_reads" in stats


def test_device_info(coordinator):
    """Test device info property."""
    coordinator.device_info = {"model": "AirPack Home"}
    device_info = coordinator.get_device_info()
    assert device_info["manufacturer"] == "ThesslaGreen"
    assert device_info["model"] == "AirPack Home"


def test_reverse_lookup_maps(coordinator):
    """Ensure reverse register maps resolve addresses to names."""
    from custom_components.thessla_green_modbus.const import (
        INPUT_REGISTERS,
        HOLDING_REGISTERS,
    )

    addr = INPUT_REGISTERS["outside_temperature"]
    assert coordinator._input_registers_rev[addr] == "outside_temperature"

    h_addr = HOLDING_REGISTERS["mode"]
    assert coordinator._holding_registers_rev[h_addr] == "mode"


def test_reverse_lookup_performance(coordinator):
    """Dictionary lookups should outperform linear search."""
    from custom_components.thessla_green_modbus.const import INPUT_REGISTERS
    import time

    addresses = list(INPUT_REGISTERS.values())

    start = time.perf_counter()
    for addr in addresses:
        coordinator._input_registers_rev.get(addr)
    dict_time = time.perf_counter() - start

    def linear_search(register_map, address):
        for name, addr in register_map.items():
            if addr == address:
                return name
        return None

    start = time.perf_counter()
    for addr in addresses:
        linear_search(INPUT_REGISTERS, addr)
    linear_time = time.perf_counter() - start

    assert dict_time < linear_time


def test_coordinator_initialization():
    """Test coordinator initialization."""
    hass = MagicMock()
    available_registers = {"holding_registers": set(), "input_registers": set()}

    coordinator = ThesslaGreenModbusCoordinator(
        hass=hass,
        host="192.168.1.100",
        port=502,
        slave_id=10,
        name="init",
        scan_interval=30,
        timeout=10,
        retry=3,
    )
    coordinator.available_registers = available_registers

    assert coordinator.host == "192.168.1.100"
    assert coordinator.port == 502
    assert coordinator.slave_id == 10
    assert coordinator.timeout == 10


def test_register_value_processing(coordinator):
    """Test register value processing."""
    temp_result = coordinator._process_register_value("outside_temperature", 250)
    assert temp_result == 25.0

    invalid_temp = coordinator._process_register_value("outside_temperature", 0x8000)
    assert invalid_temp is None

    percentage_result = coordinator._process_register_value("supply_percentage", 75)
    assert percentage_result == 75

    mode_result = coordinator._process_register_value("mode", 1)
    assert mode_result == 1


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
async def test_reconfigure_does_not_leak_connections(coordinator):
    """Ensure repeated reconnections do not increase open connections."""

    class FakeClient:
        """Simple Modbus client tracking open connections."""

        open_connections = 0

        def __init__(self, *args, **kwargs):
            type(self).open_connections += 1
            self.connected = False

        async def connect(self):
            self.connected = True
            return True

        async def close(self):
            type(self).open_connections -= 1
            self.connected = False

    with patch("pymodbus.client.AsyncModbusTcpClient", FakeClient, create=True):
        for _ in range(3):
            await coordinator._ensure_connection()
            assert FakeClient.open_connections == 1
            coordinator.client.connected = False

        await coordinator._disconnect()
        assert FakeClient.open_connections == 0


def cleanup_modules():
    """Clean up injected modules."""
    for name in modules:
        sys.modules.pop(name, None)


# Register cleanup
import atexit
atexit.register(cleanup_modules)
