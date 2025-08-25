"""Tests for ThesslaGreenModbusCoordinator - HA 2025.7.1+ & pymodbus 3.5+ Compatible."""

import asyncio
import logging
import os
import sys
import types
from datetime import datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from custom_components.thessla_green_modbus.const import (
    MAX_BATCH_REGISTERS,
    SENSOR_UNAVAILABLE,
    SENSOR_UNAVAILABLE_REGISTERS,
)
from custom_components.thessla_green_modbus.modbus_exceptions import (
    ConnectionException,
    ModbusException,
)
from custom_components.thessla_green_modbus.registers.loader import (
    RegisterDef,
    get_register_definition,
    get_registers_by_function,
)  # noqa: E402,F811,E501

# Stub minimal Home Assistant and pymodbus modules before importing the coordinator
ha = types.ModuleType("homeassistant")
ha.__path__ = []
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
util = types.ModuleType("homeassistant.util")
util.__path__ = []
network_module = types.ModuleType("homeassistant.util.network")
network_module.is_host_valid = lambda host: True
util.network = network_module

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
    def __init__(self, data, entry_id="1", options=None):
        self.data = data
        self.entry_id = entry_id
        self.options = options or {}


config_entries.ConfigEntry = ConfigEntry


class _ConfigFlow:
    def __init_subclass__(cls, **kwargs):
        return super().__init_subclass__()


config_entries.ConfigFlow = _ConfigFlow
config_entries.OptionsFlow = type("OptionsFlow", (), {})


class DataUpdateCoordinator:
    def __init__(self, hass, logger, name=None, update_interval=None):
        self.hass = hass
        self.logger = logger
        self.name = name
        self.update_interval = update_interval

    async def async_request_refresh(self):
        pass

    async def async_shutdown(self):  # pragma: no cover - stub
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


class HomeAssistantError(Exception):
    pass

exceptions.HomeAssistantError = HomeAssistantError
exceptions.ConfigEntryNotReady = ConfigEntryNotReady


class ModbusTcpClient:
    pass


class AsyncModbusTcpClient(ModbusTcpClient):
    pass


pymodbus_client.ModbusTcpClient = ModbusTcpClient
pymodbus_client.AsyncModbusTcpClient = AsyncModbusTcpClient


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
    "homeassistant.util": util,
    "homeassistant.util.network": network_module,
    "pymodbus": pymodbus,
    "pymodbus.client": pymodbus_client,
    "pymodbus.exceptions": pymodbus_exceptions,
}
for name, module in modules.items():
    sys.modules[name] = module

# Remove any pre-existing stub of ``homeassistant.util.dt`` to trigger the
# fallback ``_DTUtil`` implementation in the coordinator during import.
if hasattr(util, "dt"):
    delattr(util, "dt")
sys.modules.pop("homeassistant.util.dt", None)

# Ensure repository root is on path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))


INPUT_REGISTERS = {r.name: r.address for r in get_registers_by_function("04")}
HOLDING_REGISTERS = {r.name: r.address for r in get_registers_by_function("03")}

# ✅ FIXED: Import correct coordinator class name
from custom_components.thessla_green_modbus.coordinator import (  # noqa: E402
    ThesslaGreenModbusCoordinator,
)
from custom_components.thessla_green_modbus.coordinator import (
    dt_util as coordinator_dt_util,
)


def test_dt_util_timezone_awareness():
    """Ensure fallback dt_util provides timezone-aware datetimes."""
    now = coordinator_dt_util.now()
    utcnow = coordinator_dt_util.utcnow()
    assert now.tzinfo is not None and now.tzinfo.utcoffset(now) is not None
    assert utcnow.tzinfo is not None and utcnow.tzinfo.utcoffset(utcnow) is not None


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
async def test_async_write_register_numeric_out_of_range(coordinator, monkeypatch):
    """Numeric values outside defined range should raise."""
    coordinator._ensure_connection = AsyncMock()
    coordinator.client = MagicMock()

    import custom_components.thessla_green_modbus.coordinator as coordinator_mod

    reg = RegisterDef(function="03", address=0, name="num", access="rw", min=0, max=10)
    monkeypatch.setattr(coordinator_mod, "get_register_definition", lambda _n: reg)

    with pytest.raises(ValueError):
        await coordinator.async_write_register("num", 11)


@pytest.mark.asyncio
async def test_async_write_register_enum_invalid(coordinator, monkeypatch):
    """Invalid enum values should raise and be propagated."""
    coordinator._ensure_connection = AsyncMock()
    coordinator.client = MagicMock()

    import custom_components.thessla_green_modbus.coordinator as coordinator_mod

    reg = RegisterDef(function="03", address=0, name="mode", access="rw", enum={0: "off", 1: "on"})
    monkeypatch.setattr(coordinator_mod, "get_register_definition", lambda _n: reg)

    with pytest.raises(ValueError):
        await coordinator.async_write_register("mode", "invalid")


@pytest.mark.asyncio
async def test_read_holding_registers_none_client(coordinator, caplog):
    """Return empty data when no Modbus client is present."""
    coordinator.client = None
    coordinator._register_groups = {"holding_registers": [(0x0000, 1)]}

    with caplog.at_level(logging.DEBUG):
        result = await coordinator._read_holding_registers_optimized()

    assert result == {}
    assert "Modbus client is not connected" in caplog.text


@pytest.mark.asyncio
async def test_read_holding_registers_cancelled_error(coordinator, caplog):
    """Propagate cancellation without logging noise."""
    coordinator.client = MagicMock()
    coordinator._register_groups = {"holding_registers": [(0x0000, 1)]}
    coordinator._call_modbus = AsyncMock(side_effect=asyncio.CancelledError)

    with caplog.at_level(logging.ERROR):
        with pytest.raises(asyncio.CancelledError):
            await coordinator._read_holding_registers_optimized()
    assert caplog.text == ""


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


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "batch,expected_calls",
    [
        (1, 4),
        (8, 1),
        (MAX_BATCH_REGISTERS, 1),
        (32, 1),
    ],
)
async def test_async_write_register_chunks(coordinator, batch, expected_calls, monkeypatch):
    """Writes are chunked according to configured batch size."""
    coordinator.max_registers_per_request = batch
    coordinator.effective_batch = min(batch, MAX_BATCH_REGISTERS)
    coordinator._ensure_connection = AsyncMock()
    client = MagicMock()
    response = MagicMock()
    response.isError.return_value = False
    client.write_registers = AsyncMock(return_value=response)
    coordinator.client = client
    coordinator.async_request_refresh = AsyncMock()

    import custom_components.thessla_green_modbus.coordinator as coordinator_mod

    fake_def = SimpleNamespace(length=4, address=0, function=3, encode=lambda v: v)
    monkeypatch.setattr(coordinator_mod, "get_register_definition", lambda _n: fake_def)

    result = await coordinator.async_write_register("date_time_1", [1, 2, 3, 4])

    assert result is True
    assert client.write_registers.await_count == expected_calls
    for call in client.write_registers.await_args_list:
        assert len(call.kwargs["values"]) <= coordinator.effective_batch
    coordinator.async_request_refresh.assert_called_once()


@pytest.mark.asyncio
async def test_async_write_register_truncates_over_limit(coordinator, monkeypatch):
    """Batch sizes over the limit are truncated to the maximum when writing."""
    coordinator.max_registers_per_request = 100
    coordinator.effective_batch = MAX_BATCH_REGISTERS
    coordinator._ensure_connection = AsyncMock()
    client = MagicMock()
    response = MagicMock()
    response.isError.return_value = False
    client.write_registers = AsyncMock(return_value=response)
    coordinator.client = client
    coordinator.async_request_refresh = AsyncMock()

    import custom_components.thessla_green_modbus.coordinator as coordinator_mod

    fake_def = SimpleNamespace(length=20, address=0, function=3, encode=lambda v: v)
    monkeypatch.setattr(coordinator_mod, "get_register_definition", lambda _n: fake_def)

    result = await coordinator.async_write_register("large", list(range(20)))

    assert result is True
    assert client.write_registers.await_count == 2
    assert [len(call.kwargs["values"]) for call in client.write_registers.await_args_list] == [
        MAX_BATCH_REGISTERS,
        4,
    ]
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

    addr = INPUT_REGISTERS["outside_temperature"]
    assert coordinator._input_registers_rev[addr] == "outside_temperature"

    h_addr = HOLDING_REGISTERS["mode"]
    assert coordinator._holding_registers_rev[h_addr] == "mode"


def test_reverse_lookup_performance(coordinator):
    """Dictionary lookups should outperform linear search."""
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

    heating_result = coordinator._process_register_value("heating_temperature", 250)
    assert heating_result == 25.0

    invalid_temp = coordinator._process_register_value("outside_temperature", 0x8000)
    assert invalid_temp is None

    percentage_result = coordinator._process_register_value("supply_percentage", 75)
    assert percentage_result == 75

    mode_result = coordinator._process_register_value("mode", 1)
    assert mode_result == 1

    time_result = coordinator._process_register_value("schedule_summer_mon_1", 0x0815)
    assert time_result == 8 * 60 + 15


def test_dac_value_processing(coordinator, caplog):
    """Test DAC register value processing and validation."""
    # Valid mid-range value converts to approximately 5V
    result = coordinator._process_register_value("dac_supply", 2048)
    assert result == pytest.approx(5.0, abs=0.01)

    # Zero value stays zero
    result = coordinator._process_register_value("dac_supply", 0)
    assert result == 0

    # Invalid values outside 0-4095 are rejected
    with caplog.at_level(logging.WARNING):
        assert coordinator._process_register_value("dac_supply", 5000) is None
        assert coordinator._process_register_value("dac_supply", -1) is None
        assert "out of range" in caplog.text


@pytest.mark.parametrize(
    "register_name",
    sorted(SENSOR_UNAVAILABLE_REGISTERS),
    ids=sorted(SENSOR_UNAVAILABLE_REGISTERS),
)
def test_process_register_value_sensor_unavailable(coordinator, register_name):
    """Return sentinel when sensors report unavailable for known sensor registers."""
    assert (
        coordinator._process_register_value(register_name, SENSOR_UNAVAILABLE) == SENSOR_UNAVAILABLE
    )


@pytest.mark.parametrize(
    ("register_name", "value", "expected"),
    [
        ("supply_flow_rate", 0xFFFB, -5),
        ("outside_temperature", 0x8000, SENSOR_UNAVAILABLE),
    ],
)
def test_process_register_value_extremes(coordinator, register_name, value, expected):
    """Handle extreme raw register values correctly."""
    result = coordinator._process_register_value(register_name, value)
    assert result == expected


@pytest.mark.parametrize(
    "register_name",
    ["dac_supply", "dac_exhaust", "dac_heater", "dac_cooler"],
    ids=["supply", "exhaust", "heater", "cooler"],
)
@pytest.mark.parametrize(
    "value",
    [0, 4095, -1, 5000],
    ids=["min", "max", "below_min", "above_max"],
)
def test_process_register_value_dac_boundaries(coordinator, register_name, value):
    """Process DAC registers across boundary and out-of-range values."""
    expected = get_register_definition(register_name).decode(value)
    result = coordinator._process_register_value(register_name, value)
    assert result == pytest.approx(expected)


def test_register_value_logging(coordinator, caplog):
    """Test debug and warning logging for register processing."""

    with caplog.at_level(logging.DEBUG):
        caplog.clear()
        coordinator._process_register_value("outside_temperature", 250)
        assert "raw=250" in caplog.text
        assert "value=25.0" in caplog.text

    with caplog.at_level(logging.WARNING):
        caplog.clear()
        coordinator._process_register_value("outside_temperature", SENSOR_UNAVAILABLE)
        assert "SENSOR_UNAVAILABLE" in caplog.text

        caplog.clear()
        coordinator._process_register_value("supply_percentage", 150)
        assert "Out-of-range value for supply_percentage" in caplog.text


def test_post_process_data(coordinator):
    """Test data post-processing."""
    raw_data = {
        "outside_temperature": 100,  # 10.0°C
        "supply_temperature": 200,  # 20.0°C
        "exhaust_temperature": 250,  # 25.0°C
        "supply_flow_rate": 150,
        "exhaust_flow_rate": 140,
        "dac_supply": 5.0,
        "dac_exhaust": 4.0,
    }

    fake_now = datetime(2024, 1, 1, 12, 0, 0)
    coordinator._last_power_timestamp = fake_now - timedelta(hours=1)

    with patch(
        "custom_components.thessla_green_modbus.coordinator.dt_util.utcnow",
        return_value=fake_now,
    ):
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

    # Power estimation
    assert "estimated_power" in processed_data
    assert processed_data["estimated_power"] > 0
    assert "total_energy" in processed_data
    assert processed_data["total_energy"] > 0


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

    with patch(
        "custom_components.thessla_green_modbus.coordinator.AsyncModbusTcpClient",
        FakeClient,
    ):
        for _ in range(3):
            async with coordinator._connection_lock:
                await coordinator._ensure_connection()
            assert FakeClient.open_connections == 1
            coordinator.client.connected = False

        await coordinator._disconnect()
        assert FakeClient.open_connections == 0


@pytest.mark.asyncio
async def test_missing_client_raises_connection_exception(coordinator):
    """Missing client should raise ConnectionException instead of AttributeError."""
    coordinator.client = None
    coordinator._register_groups = {
        "input_registers": [(0x0000, 1)],
        "holding_registers": [(0x0000, 1)],
        "coil_registers": [(0x0000, 1)],
        "discrete_inputs": [(0x0000, 1)],
    }

    with pytest.raises(ConnectionException):
        await coordinator._read_input_registers_optimized()
    with pytest.raises(ConnectionException):
        await coordinator._read_coil_registers_optimized()
    with pytest.raises(ConnectionException):
        await coordinator._read_discrete_inputs_optimized()


@pytest.mark.asyncio
async def test_async_update_data_missing_client(coordinator):
    """_async_update_data should raise UpdateFailed when client cannot be established."""
    coordinator.client = None
    coordinator._ensure_connection = AsyncMock()

    with pytest.raises(UpdateFailed):
        await coordinator._async_update_data()


@pytest.mark.asyncio
async def test_setup_and_refresh_no_cancelled_error(coordinator):
    """Successful setup and refresh should not raise CancelledError."""
    coordinator._ensure_connection = AsyncMock()
    coordinator.client = MagicMock()
    coordinator.client.connected = True

    result = await coordinator._async_setup_client()
    assert result is True

    coordinator._read_input_registers_optimized = AsyncMock(return_value={})
    coordinator._read_holding_registers_optimized = AsyncMock(return_value={})
    coordinator._read_coil_registers_optimized = AsyncMock(return_value={})
    coordinator._read_discrete_inputs_optimized = AsyncMock(return_value={})

    data = await coordinator._async_update_data()
    assert data == {}


@pytest.mark.asyncio
async def test_capabilities_loaded_from_config_entry():
    """Coordinator should hydrate capabilities from stored entry data."""
    caps = {"expansion_module": True}
    entry = config_entries.ConfigEntry(
        {
            const.CONF_HOST: "localhost",
            const.CONF_PORT: 502,
            "slave_id": 1,
            const.CONF_NAME: "test",
            "capabilities": caps,
        }
    )

    coordinator = ThesslaGreenModbusCoordinator(
        hass=MagicMock(),
        host="localhost",
        port=502,
        slave_id=1,
        name="test",
        scan_interval=30,
        timeout=10,
        retry=3,
        force_full_register_list=True,
        entry=entry,
    )

    # async_setup will skip scanning due to force_full_register_list
    coordinator._test_connection = AsyncMock()
    await coordinator.async_setup()

    assert coordinator.capabilities.expansion_module is True


@pytest.mark.asyncio
async def test_async_setup_invalid_capabilities(coordinator):
    """Invalid capabilities format should raise CannotConnect."""
    from custom_components.thessla_green_modbus.config_flow import (
        CannotConnect,
    )

    scan_result = {
        "device_info": {},
        "available_registers": {},
        "capabilities": [],  # invalid type
    }

    scanner_instance = types.SimpleNamespace(
        scan_device=AsyncMock(return_value=scan_result),
        close=AsyncMock(),
    )

    with patch(
        "custom_components.thessla_green_modbus.coordinator.ThesslaGreenDeviceScanner.create",
        AsyncMock(return_value=scanner_instance),
    ):
        with pytest.raises(CannotConnect) as err:
            await coordinator.async_setup()

    assert str(err.value) == "invalid_capabilities"
    scanner_instance.close.assert_awaited_once()


def cleanup_modules():
    """Clean up injected modules."""
    for name in modules:
        sys.modules.pop(name, None)


# Register cleanup
import atexit  # noqa: E402

atexit.register(cleanup_modules)
