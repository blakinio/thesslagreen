"""Tests for ThesslaGreenModbusCoordinator - HA 2025.7.1+ & pymodbus 3.5+ Compatible."""

import os
import sys
import types
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from custom_components.thessla_green_modbus.modbus_exceptions import (
    ConnectionException,
    ModbusException,
)
from custom_components.thessla_green_modbus.registers import HOLDING_REGISTERS

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


pymodbus_exceptions.ModbusException = ModbusException

pymodbus_exceptions.ConnectionException = ConnectionException

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
from custom_components.thessla_green_modbus.coordinator import (  # noqa: E402
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
    """Test successful register write and refresh outside lock."""
    coordinator._ensure_connection = AsyncMock()
    client = MagicMock()
    response = MagicMock()
    response.isError.return_value = False
    client.write_register = AsyncMock(return_value=response)
    coordinator.client = client

    lock_state_during_refresh = None

    async def refresh_side_effect():
        nonlocal lock_state_during_refresh
        lock_state_during_refresh = coordinator._connection_lock.locked()

    coordinator.async_request_refresh = AsyncMock(side_effect=refresh_side_effect)

    result = await coordinator.async_write_register("mode", 1)

    assert result is True
    coordinator.async_request_refresh.assert_called_once()
    assert lock_state_during_refresh is False


@pytest.mark.asyncio
async def test_async_write_multi_register_start(coordinator):
    """Writing multi-register from start address succeeds."""
    coordinator.async_request_refresh = AsyncMock()
    coordinator._ensure_connection = AsyncMock()
    client = MagicMock()
    response = MagicMock()
    response.isError.return_value = False
    client.write_registers = AsyncMock(return_value=response)
    coordinator.client = client

    result = await coordinator.async_write_register("date_time_1", [1, 2, 3, 4])

    assert result is True
    client.write_registers.assert_awaited_once_with(
        address=HOLDING_REGISTERS["date_time_1"], values=[1, 2, 3, 4], slave=1
    )
    coordinator.async_request_refresh.assert_called_once()


@pytest.mark.asyncio
async def test_async_write_multi_register_non_start(coordinator):
    """Multi-register writes from non-start addresses are rejected."""
    coordinator.async_request_refresh = AsyncMock()
    coordinator._ensure_connection = AsyncMock()
    client = MagicMock()
    client.write_registers = AsyncMock()
    client.write_register = AsyncMock()
    coordinator.client = client

    result = await coordinator.async_write_register("date_time_2", [1, 2, 3])

    assert result is False
    client.write_registers.assert_not_awaited()
    client.write_register.assert_not_awaited()
    coordinator.async_request_refresh.assert_not_called()


@pytest.mark.asyncio
async def test_async_write_multi_register_wrong_length(coordinator):
    """Reject writes with incorrect number of values."""
    coordinator.async_request_refresh = AsyncMock()
    coordinator._ensure_connection = AsyncMock()
    client = MagicMock()
    client.write_registers = AsyncMock()
    coordinator.client = client

    result = await coordinator.async_write_register("date_time_1", [1, 2, 3])

    assert result is False
    client.write_registers.assert_not_awaited()
    coordinator.async_request_refresh.assert_not_called()


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


def test_device_info_dict_fallback(monkeypatch):
    """device_info_dict should work without HA DeviceInfo."""
    import importlib
    import sys

    # Simulate missing device_registry module
    monkeypatch.delitem(sys.modules, "homeassistant.helpers.device_registry", raising=False)
    monkeypatch.delattr(helpers_pkg, "device_registry", raising=False)
    monkeypatch.delitem(
        sys.modules, "custom_components.thessla_green_modbus.coordinator", raising=False
    )
    coordinator_module = importlib.import_module(
        "custom_components.thessla_green_modbus.coordinator"
    )
    hass = MagicMock()
    coord = coordinator_module.ThesslaGreenModbusCoordinator(
        hass=hass,
        host="localhost",
        port=502,
        slave_id=1,
        name="test",
        scan_interval=30,
        timeout=10,
        retry=3,
    )
    coord.device_info = {"model": "AirPack Home"}
    device_info = coord.device_info_dict
    assert device_info["manufacturer"] == "ThesslaGreen"
    assert device_info["model"] == "AirPack Home"


def test_reverse_lookup_maps(coordinator):
    """Ensure reverse register maps resolve addresses to names."""
    from custom_components.thessla_green_modbus.registers import HOLDING_REGISTERS, INPUT_REGISTERS

    addr = INPUT_REGISTERS["outside_temperature"]
    assert coordinator._input_registers_rev[addr] == "outside_temperature"

    h_addr = HOLDING_REGISTERS["mode"]
    assert coordinator._holding_registers_rev[h_addr] == "mode"


def test_reverse_lookup_performance(coordinator):
    """Dictionary lookups should outperform linear search."""
    import time

    from custom_components.thessla_green_modbus.registers import INPUT_REGISTERS

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

    heating_result = coordinator._process_register_value("heating_temperature", 250)
    assert heating_result == 25.0

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
        "supply_temperature": 200,  # 20.0°C
        "exhaust_temperature": 250,  # 25.0°C
        "supply_flow_rate": 150,
        "exhaust_flow_rate": 140,
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
import atexit  # noqa: E402

atexit.register(cleanup_modules)
