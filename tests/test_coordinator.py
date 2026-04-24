"""Tests for ThesslaGreenModbusCoordinator - HA 2025.7.1+ & pymodbus 3.5+ Compatible."""

import asyncio
import logging
import sys
import types
from datetime import datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from custom_components.thessla_green_modbus.const import (
    CONF_MAX_REGISTERS_PER_REQUEST,
    DEFAULT_BACKOFF_JITTER,
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
)

try:
    from homeassistant.const import CONF_HOST, CONF_NAME, CONF_PORT
    from homeassistant.helpers.update_coordinator import UpdateFailed
except ImportError:
    CONF_HOST = "host"
    CONF_NAME = "name"
    CONF_PORT = "port"

    class UpdateFailed(Exception):  # type: ignore[no-redef]
        pass


def _make_config_entry(data: dict, options: dict | None = None) -> MagicMock:
    """Create a minimal config entry mock."""
    entry = MagicMock()
    entry.data = data
    entry.entry_id = "test"
    entry.options = options or {}
    return entry


INPUT_REGISTERS = {r.name: r.address for r in get_registers_by_function("04")}
HOLDING_REGISTERS = {r.name: r.address for r in get_registers_by_function("03")}

# ✅ FIXED: Import correct coordinator class name
from custom_components.thessla_green_modbus.coordinator import (
    ThesslaGreenModbusCoordinator,
    _PermanentModbusError,
)
from custom_components.thessla_green_modbus.coordinator import (
    dt_util as coordinator_dt_util,
)


def test_dt_util_timezone_awareness():
    """Ensure coordinator dt util keeps expected callables available."""
    assert callable(coordinator_dt_util.now)
    assert callable(coordinator_dt_util.utcnow)


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
    coordinator = ThesslaGreenModbusCoordinator.from_params(
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


def test_coordinator_clamps_effective_batch():
    """Coordinator clamps batch size to ``MAX_BATCH_REGISTERS``."""
    hass = MagicMock()
    entry = _make_config_entry(
        data={},
        options={CONF_MAX_REGISTERS_PER_REQUEST: MAX_BATCH_REGISTERS + 8},
    )
    coord = ThesslaGreenModbusCoordinator.from_params(
        hass=hass,
        host="localhost",
        port=502,
        slave_id=1,
        name="test",
        entry=entry,
    )
    assert coord.effective_batch == MAX_BATCH_REGISTERS
    assert coord.max_registers_per_request == MAX_BATCH_REGISTERS


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
        lock_state_during_refresh = coordinator._write_lock.locked()

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
    coordinator._register_groups = {"holding_registers": [(0, 1)]}

    with caplog.at_level(logging.DEBUG):
        result = await coordinator._read_holding_registers_optimized()

    assert result == {}
    assert "Modbus client is not connected" in caplog.text


@pytest.mark.asyncio
async def test_read_holding_registers_cancelled_error(coordinator, caplog):
    """Propagate cancellation without logging noise."""
    coordinator.client = MagicMock()
    coordinator._register_groups = {"holding_registers": [(0, 1)]}
    coordinator._call_modbus = AsyncMock(side_effect=asyncio.CancelledError)

    with caplog.at_level(logging.ERROR), pytest.raises(asyncio.CancelledError):
        await coordinator._read_holding_registers_optimized()
    assert caplog.text == ""


@pytest.mark.asyncio
async def test_read_input_registers_reconnect_on_error(coordinator):
    """Ensure disconnect is triggered after Modbus errors."""
    coordinator.client = MagicMock()
    coordinator.client.connected = True
    coordinator._register_groups = {"input_registers": [(0, 1)]}
    coordinator._call_modbus = AsyncMock(side_effect=ConnectionException("boom"))
    coordinator._disconnect = AsyncMock()

    await coordinator._read_input_registers_optimized()

    coordinator._disconnect.assert_called()


@pytest.mark.asyncio
async def test_disconnect_retry_transportless_restores_client(coordinator):
    """Transport-less retry restores client when disconnect clears it."""
    client = MagicMock()
    coordinator.client = client
    coordinator._transport = None
    coordinator._disconnect = _disconnect_clear_client(coordinator)
    coordinator._ensure_connection = AsyncMock()

    reconnect_error = await coordinator._disconnect_and_reconnect_for_retry(
        register_type="input",
        start_address=0,
        attempt=1,
    )

    assert reconnect_error is None
    assert coordinator.client is client
    coordinator._ensure_connection.assert_not_awaited()


@pytest.mark.asyncio
async def test_disconnect_retry_transportless_returns_disconnect_error(coordinator):
    """Transport-less retry returns disconnect error and skips reconnect."""
    client = MagicMock()
    coordinator.client = client
    coordinator._transport = None
    coordinator._disconnect = _disconnect_raise_oserror()
    coordinator._ensure_connection = AsyncMock()

    reconnect_error = await coordinator._disconnect_and_reconnect_for_retry(
        register_type="input",
        start_address=0,
        attempt=1,
    )

    assert isinstance(reconnect_error, OSError)
    coordinator._ensure_connection.assert_not_awaited()


def _disconnect_clear_client(coordinator):
    async def _disconnect() -> None:
        coordinator.client = None

    return _disconnect


def _disconnect_raise_oserror():
    async def _disconnect() -> None:
        raise OSError("disconnect failed")

    return _disconnect


@pytest.mark.asyncio
async def test_async_write_multi_register_start(coordinator, monkeypatch):
    """Writing multi-register from start address succeeds."""
    coordinator.async_request_refresh = AsyncMock()
    coordinator._ensure_connection = AsyncMock()
    client = MagicMock()
    response = MagicMock()
    response.isError.return_value = False
    client.write_registers = AsyncMock(return_value=response)
    coordinator.client = client

    import custom_components.thessla_green_modbus.coordinator as coordinator_mod

    fake_def = RegisterDef(function=3, address=0, name="date_time_1", access="rw", length=4)
    monkeypatch.setattr(coordinator_mod, "get_register_definition", lambda _n: fake_def)
    HOLDING_REGISTERS["date_time_1"] = 0

    result = await coordinator.async_write_register("date_time_1", [1, 2, 3, 4])

    assert result is True
    client.write_registers.assert_awaited_once_with(
        address=HOLDING_REGISTERS["date_time_1"], values=[1, 2, 3, 4]
    )
    coordinator.async_request_refresh.assert_called_once()


@pytest.mark.asyncio
async def test_async_write_multi_register_with_offset(coordinator, monkeypatch):
    """Writing a subset of a multi-register with an offset succeeds."""
    coordinator.async_request_refresh = AsyncMock()
    coordinator._ensure_connection = AsyncMock()
    client = MagicMock()
    response = MagicMock()
    response.isError.return_value = False
    client.write_registers = AsyncMock(return_value=response)
    coordinator.client = client

    import custom_components.thessla_green_modbus.coordinator as coordinator_mod

    fake_def = RegisterDef(function=3, address=0, name="date_time_1", access="rw", length=4)
    monkeypatch.setattr(coordinator_mod, "get_register_definition", lambda _n: fake_def)
    HOLDING_REGISTERS["date_time_1"] = 0

    result = await coordinator.async_write_register("date_time_1", [3, 4], offset=2)

    assert result is True
    client.write_registers.assert_awaited_once_with(
        address=HOLDING_REGISTERS["date_time_1"] + 2,
        values=[3, 4],
    )
    coordinator.async_request_refresh.assert_called_once()


@pytest.mark.asyncio
async def test_async_write_multi_register_non_start(coordinator, monkeypatch):
    """Multi-register writes from non-start addresses are rejected."""
    coordinator.async_request_refresh = AsyncMock()
    coordinator._ensure_connection = AsyncMock()
    client = MagicMock()
    client.write_registers = AsyncMock()
    client.write_register = AsyncMock()
    coordinator.client = client

    import custom_components.thessla_green_modbus.coordinator as coordinator_mod

    fake_def = RegisterDef(function=3, address=1, name="date_time_2", access="rw", length=1)
    monkeypatch.setattr(coordinator_mod, "get_register_definition", lambda _n: fake_def)
    HOLDING_REGISTERS["date_time_2"] = 1

    result = await coordinator.async_write_register("date_time_2", [1, 2, 3])

    assert result is False
    client.write_registers.assert_not_awaited()
    client.write_register.assert_not_awaited()
    coordinator.async_request_refresh.assert_not_called()


@pytest.mark.asyncio
async def test_async_write_multi_register_wrong_length(coordinator, monkeypatch):
    """Reject writes with incorrect number of values."""
    coordinator.async_request_refresh = AsyncMock()
    coordinator._ensure_connection = AsyncMock()
    client = MagicMock()
    client.write_registers = AsyncMock()
    coordinator.client = client

    import custom_components.thessla_green_modbus.coordinator as coordinator_mod

    fake_def = RegisterDef(function=3, address=0, name="date_time_1", access="rw", length=4)
    monkeypatch.setattr(coordinator_mod, "get_register_definition", lambda _n: fake_def)
    HOLDING_REGISTERS["date_time_1"] = 0

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


@pytest.mark.asyncio
async def test_read_holding_registers_chunking_and_retries(coordinator):
    """Read path retries on errors and honours chunk sizes."""

    coordinator.client = MagicMock()
    coordinator.client.connected = True
    coordinator.retry = 2

    coordinator._register_groups = {
        "holding_registers": [
            (0, MAX_BATCH_REGISTERS),
            (MAX_BATCH_REGISTERS, 4),
            (MAX_BATCH_REGISTERS + 4, 1),
        ]
    }
    names = {f"reg{i}" for i in range(MAX_BATCH_REGISTERS + 5)}
    coordinator.available_registers["holding_registers"] = names
    coordinator._find_register_name = lambda _kind, addr: f"reg{addr}"
    coordinator._process_register_value = lambda _name, value: value
    coordinator._clear_register_failure = lambda _name: None
    coordinator._mark_registers_failed = lambda _names: None

    response1 = SimpleNamespace(registers=[1] * MAX_BATCH_REGISTERS, isError=lambda: False)
    response2 = SimpleNamespace(registers=[2] * 4, isError=lambda: False)
    response3 = SimpleNamespace(registers=[3], isError=lambda: False)

    coordinator.client.read_holding_registers = AsyncMock(
        side_effect=[
            TimeoutError(),
            response1,
            ModbusException("boom"),
            response2,
            response3,
        ]
    )

    data = await coordinator._read_holding_registers_optimized()

    assert coordinator.client.read_holding_registers.await_count == 5
    counts = [c.kwargs["count"] for c in coordinator.client.read_holding_registers.await_args_list]
    assert counts == [MAX_BATCH_REGISTERS, MAX_BATCH_REGISTERS, 4, 4, 1]
    assert data["reg0"] == 1
    assert data[f"reg{MAX_BATCH_REGISTERS}"] == 2
    assert data[f"reg{MAX_BATCH_REGISTERS + 4}"] == 3


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


def test_get_device_info_fallback(monkeypatch):
    """get_device_info should work without HA DeviceInfo."""
    import importlib

    import custom_components.thessla_green_modbus as _thg_pkg

    # Track the coordinator package attribute so monkeypatch restores it after the test.
    # Without this, importlib.import_module below sets thg_pkg.coordinator = M_new and
    # subsequent tests that use string-path monkeypatching would patch the wrong module.
    if hasattr(_thg_pkg, "coordinator"):
        monkeypatch.setattr(_thg_pkg, "coordinator", _thg_pkg.coordinator)

    # Simulate missing device_registry module
    monkeypatch.delitem(sys.modules, "homeassistant.helpers.device_registry", raising=False)
    monkeypatch.delitem(
        sys.modules, "custom_components.thessla_green_modbus.coordinator", raising=False
    )
    coordinator_module = importlib.import_module(
        "custom_components.thessla_green_modbus.coordinator"
    )
    hass = MagicMock()
    coord = coordinator_module.ThesslaGreenModbusCoordinator.from_params(
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
    device_info = coord.get_device_info()
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
    iterations = 1000

    start = time.perf_counter()
    for _ in range(iterations):
        for addr in addresses:
            coordinator._input_registers_rev.get(addr)
    dict_time = time.perf_counter() - start

    def linear_search(register_map, address):
        for name, addr in register_map.items():
            if addr == address:
                return name
        return None

    start = time.perf_counter()
    for _ in range(iterations):
        for addr in addresses:
            linear_search(INPUT_REGISTERS, addr)
    linear_time = time.perf_counter() - start

    assert dict_time < linear_time


def test_coordinator_initialization():
    """Test coordinator initialization."""
    hass = MagicMock()
    available_registers = {"holding_registers": set(), "input_registers": set()}

    coordinator = ThesslaGreenModbusCoordinator.from_params(
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

    invalid_temp = coordinator._process_register_value("outside_temperature", 32768)
    assert invalid_temp is None

    percentage_result = coordinator._process_register_value("supply_percentage", 75)
    assert percentage_result == 75

    mode_result = coordinator._process_register_value("mode", 1)
    assert mode_result == 1

    time_result = coordinator._process_register_value("schedule_summer_mon_1", 2069)
    assert time_result == "08:15"


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
    result = coordinator._process_register_value(register_name, SENSOR_UNAVAILABLE)
    if "temperature" in register_name:
        assert result is None
    else:
        assert result == SENSOR_UNAVAILABLE


@pytest.mark.parametrize(
    ("register_name", "value", "expected"),
    [
        ("supply_flow_rate", 65531, -5),
        ("outside_temperature", 32768, None),
    ],
)
def test_process_register_value_extremes(coordinator, register_name, value, expected):
    """Handle extreme raw register values correctly."""
    result = coordinator._process_register_value(register_name, value)
    assert result == expected


def test_process_register_value_no_magic_number_in_source():
    """Regression guard against reintroducing literal 32768 in coordinator logic."""
    import inspect

    src = inspect.getsource(ThesslaGreenModbusCoordinator._process_register_value)
    assert "32768" not in src


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

    with caplog.at_level(
        logging.DEBUG, logger="custom_components.thessla_green_modbus.coordinator"
    ):
        caplog.clear()
        coordinator._process_register_value("outside_temperature", 250)
        assert "raw=250" in caplog.text
        assert "value=25.0" in caplog.text

    with caplog.at_level(
        logging.WARNING, logger="custom_components.thessla_green_modbus.coordinator"
    ):
        caplog.clear()
        coordinator._process_register_value("outside_temperature", SENSOR_UNAVAILABLE)
        assert not caplog.records


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
    assert isinstance(efficiency, int | float)
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

    # New derived sensors must be present
    assert "heat_recovery_efficiency" in processed_data
    assert processed_data["heat_recovery_efficiency"] == processed_data["calculated_efficiency"]
    assert "heat_recovery_power" in processed_data
    assert processed_data["heat_recovery_power"] >= 0
    assert "electrical_power" in processed_data
    assert processed_data["electrical_power"] == processed_data["estimated_power"]


def test_lookup_model_power_exact(coordinator):
    """Known nominal flows return the correct specs."""
    assert coordinator._lookup_model_power(300) == (105.0, 1150.0)
    assert coordinator._lookup_model_power(400) == (170.0, 1500.0)
    assert coordinator._lookup_model_power(420) == (94.0, 1449.0)
    assert coordinator._lookup_model_power(500) == (255.0, 1850.0)
    assert coordinator._lookup_model_power(550) == (345.0, 1950.0)


def test_lookup_model_power_within_tolerance(coordinator):
    """Flows within ±15 m³/h of a known entry should match."""
    # 410 is within 15 of 420 (AirPack Home 400h) and within 15 of 400 (AirPack4 400V).
    # Closest match is 420 (diff=10) over 400 (diff=10)... let's check 430 which is closest to 420.
    result = coordinator._lookup_model_power(430)
    assert result == (94.0, 1449.0)  # closest to 420


def test_lookup_model_power_unknown(coordinator):
    """Flows far from any known entry return None."""
    assert coordinator._lookup_model_power(200) is None
    assert coordinator._lookup_model_power(700) is None


def test_calculate_power_model_aware(coordinator):
    """Flow-based calculation uses fan affinity law + standby power."""
    data = {
        "nominal_supply_air_flow": 420,
        "supply_flow_rate": 420,  # 100% flow
        "exhaust_flow_rate": 420,
        "dac_heater": 0.0,
    }
    power = coordinator.calculate_power_consumption(data)
    # At 100% flow: fans = 94 W, heater = 0, standby = 10 W → 104 W
    assert power == pytest.approx(104.0, abs=0.5)


def test_calculate_power_partial_flow(coordinator):
    """Fan affinity law: at 50% flow power is (0.5)³ = 12.5% of max per fan."""
    data = {
        "nominal_supply_air_flow": 420,
        "supply_flow_rate": 210,  # 50%
        "exhaust_flow_rate": 210,
        "dac_heater": 0.0,
    }
    power = coordinator.calculate_power_consumption(data)
    # Each fan: 47 × 0.125 = 5.875 W × 2 = 11.75 W, + 10 W standby = 21.75 W
    assert power == pytest.approx(21.75, abs=0.5)


def test_calculate_power_with_heater(coordinator):
    """Heater contributes linearly: 50% DAC → 50% of heater_max."""
    data = {
        "nominal_supply_air_flow": 420,
        "supply_flow_rate": 420,
        "exhaust_flow_rate": 420,
        "dac_heater": 5.0,  # 50%
    }
    power = coordinator.calculate_power_consumption(data)
    # fans=94 W, heater=1449×0.5=724.5 W, standby=10 W → 828.5 W
    assert power == pytest.approx(828.5, abs=1.0)


def test_calculate_power_standby_always_included(coordinator):
    """Standby power is always added regardless of fans or heater."""
    data = {
        "nominal_supply_air_flow": 420,
        "supply_flow_rate": 0,
        "exhaust_flow_rate": 0,
        "dac_heater": 0.0,
    }
    power = coordinator.calculate_power_consumption(data)
    assert power == pytest.approx(10.0, abs=0.1)


def test_calculate_power_fallback_dac(coordinator):
    """Falls back to DAC estimate when nominal flow is absent."""
    data = {
        "dac_supply": 10.0,
        "dac_exhaust": 10.0,
    }
    power = coordinator.calculate_power_consumption(data)
    # DAC fallback: 2 fans × (10/10)³ × 80 W = 160 W
    assert power == pytest.approx(160.0, abs=1.0)


def test_calculate_power_fallback_missing_dac(coordinator):
    """Returns None when neither flow data nor DAC values are available."""
    assert coordinator.calculate_power_consumption({}) is None


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
        "input_registers": [(0, 1)],
        "holding_registers": [(0, 1)],
        "coil_registers": [(0, 1)],
        "discrete_inputs": [(0, 1)],
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
    entry = _make_config_entry(
        {
            CONF_HOST: "localhost",
            CONF_PORT: 502,
            "slave_id": 1,
            CONF_NAME: "test",
            "capabilities": caps,
        }
    )

    coordinator = ThesslaGreenModbusCoordinator.from_params(
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


def test_apply_scan_cache_normalises_legacy_error_status_names(coordinator):
    """Legacy cached names like e108/s28 should be normalised to e_108/s_28."""

    cache = {
        "available_registers": {
            "holding_registers": ["e108", "s28", "mode"],
            "input_registers": ["outside_temperature"],
            "coil_registers": [],
            "discrete_inputs": [],
        },
        "device_info": {},
        "capabilities": {},
    }

    assert coordinator._apply_scan_cache(cache) is True
    assert "e_108" in coordinator.available_registers["holding_registers"]
    assert "s_28" in coordinator.available_registers["holding_registers"]
    assert "e108" not in coordinator.available_registers["holding_registers"]
    assert "s28" not in coordinator.available_registers["holding_registers"]


@pytest.mark.asyncio
async def test_async_setup_invalid_capabilities(coordinator):
    """Invalid capabilities format should raise CannotConnect."""
    from custom_components.thessla_green_modbus.config_flow import CannotConnect

    scan_result = {
        "device_info": {},
        "available_registers": {},
        "capabilities": [],  # invalid type
    }

    scanner_instance = types.SimpleNamespace(
        scan_device=AsyncMock(return_value=scan_result),
        close=AsyncMock(),
    )

    with (
        patch(
            "custom_components.thessla_green_modbus.coordinator.ThesslaGreenDeviceScanner.create",
            AsyncMock(return_value=scanner_instance),
        ),
        pytest.raises(CannotConnect) as err,
    ):
        await coordinator.async_setup()

    assert str(err.value) == "invalid_capabilities"
    scanner_instance.close.assert_awaited_once()


@pytest.mark.asyncio
async def test_coordinator_tracks_offline_and_recovers(monkeypatch) -> None:
    """Transient failures increment counters and successful reads reset them."""

    coordinator = ThesslaGreenModbusCoordinator.from_params(
        MagicMock(),
        "host",
        502,
        1,
        "name",
        scan_interval=5,
        retry=1,
    )
    coordinator.client = MagicMock(connected=True)
    coordinator._disconnect = AsyncMock()
    coordinator._ensure_connection = AsyncMock()
    coordinator._read_input_registers_optimized = AsyncMock(
        side_effect=[ConnectionException("fail"), {"reg": 1}]
    )
    coordinator._read_holding_registers_optimized = AsyncMock(return_value={})
    coordinator._read_coil_registers_optimized = AsyncMock(return_value={})
    coordinator._read_discrete_inputs_optimized = AsyncMock(return_value={})

    with pytest.raises(UpdateFailed):
        await coordinator._async_update_data()

    assert coordinator._consecutive_failures == 1  # nosec: explicit state check
    coordinator._read_input_registers_optimized.reset_mock(side_effect=True)
    coordinator._read_input_registers_optimized.side_effect = None
    coordinator._read_input_registers_optimized.return_value = {"reg": 1}

    data = await coordinator._async_update_data()

    assert data["reg"] == 1  # nosec: explicit state check
    assert coordinator._consecutive_failures == 0  # nosec: explicit state check
    assert coordinator.statistics["last_successful_update"] is not None  # nosec


@pytest.mark.asyncio
async def test_coordinator_disconnects_after_retries(monkeypatch) -> None:
    """Persistent failures force a disconnect and surface an error."""

    coordinator = ThesslaGreenModbusCoordinator.from_params(
        MagicMock(),
        "host",
        502,
        1,
        "name",
        scan_interval=5,
        retry=1,
    )
    coordinator._max_failures = 1
    coordinator.client = MagicMock(connected=True)
    coordinator._disconnect = AsyncMock()
    coordinator._ensure_connection = AsyncMock()
    coordinator._read_input_registers_optimized = AsyncMock(side_effect=TimeoutError("boom"))
    coordinator._read_holding_registers_optimized = AsyncMock(return_value={})
    coordinator._read_coil_registers_optimized = AsyncMock(return_value={})
    coordinator._read_discrete_inputs_optimized = AsyncMock(return_value={})

    with pytest.raises(UpdateFailed):
        await coordinator._async_update_data()

    coordinator._disconnect.assert_awaited_once()
    assert coordinator.client.connected  # nosec: explicit state check


@pytest.mark.asyncio
async def test_read_with_retry_retries_transient_errors():
    """Coordinator retries transient read errors before succeeding."""

    coordinator = ThesslaGreenModbusCoordinator.from_params(
        MagicMock(),
        "host",
        502,
        1,
        "name",
        retry=2,
    )
    coordinator._disconnect = AsyncMock()
    response = MagicMock()
    response.isError.return_value = False
    coordinator._call_modbus = AsyncMock(side_effect=[TimeoutError("boom"), response])

    result = await coordinator._read_with_retry(
        lambda *_args, **_kwargs: None,  # pragma: no cover - not invoked directly
        10,
        1,
        register_type="input",
    )

    assert result is response  # nosec: explicit state check
    assert coordinator._call_modbus.await_count == 2
    # _disconnect is not called on TimeoutError without an active transport (production behaviour)


@pytest.mark.asyncio
async def test_read_with_retry_skips_illegal_data_address():
    """Illegal data address errors should not be retried."""

    coordinator = ThesslaGreenModbusCoordinator.from_params(
        MagicMock(),
        "host",
        502,
        1,
        "name",
        retry=3,
    )
    coordinator._disconnect = AsyncMock()

    response = MagicMock()
    response.isError.return_value = True
    response.exception_code = 2
    coordinator._call_modbus = AsyncMock(return_value=response)

    with pytest.raises(_PermanentModbusError):
        await coordinator._read_with_retry(
            lambda *_args, **_kwargs: None,  # pragma: no cover - not invoked directly
            10,
            1,
            register_type="input",
        )

    assert coordinator._call_modbus.await_count == 1
    coordinator._disconnect.assert_not_awaited()


class TestParseBackoffJitter:
    """Direct tests for the _parse_backoff_jitter parser."""

    def test_numeric_inputs(self) -> None:
        parse = ThesslaGreenModbusCoordinator._parse_backoff_jitter

        assert parse(0) == 0.0
        assert parse(0.0) == 0.0
        assert parse(1) == 1.0
        assert parse(1.5) == 1.5

    def test_string_inputs(self) -> None:
        parse = ThesslaGreenModbusCoordinator._parse_backoff_jitter

        assert parse("1.5") == 1.5
        assert parse("0") == 0.0
        assert parse("not-a-number") is None
        assert parse("") is None

    def test_tuple_list_inputs(self) -> None:
        parse = ThesslaGreenModbusCoordinator._parse_backoff_jitter

        assert parse((1.0, 2.0)) == (1.0, 2.0)
        assert parse([1, 2]) == (1.0, 2.0)
        assert parse((1.0, 2.0, 3.0)) == (1.0, 2.0)

    def test_invalid_sequence_returns_none(self) -> None:
        parse = ThesslaGreenModbusCoordinator._parse_backoff_jitter

        assert parse(["a", "b"]) is None
        assert parse((None, None)) is None

    def test_none_and_sentinel_defaults(self) -> None:
        parse = ThesslaGreenModbusCoordinator._parse_backoff_jitter

        assert parse(None) is None
        assert parse({"key": "value"}) == DEFAULT_BACKOFF_JITTER  # type: ignore[arg-type]


@pytest.mark.asyncio
async def test_async_update_data_handles_cancellation(coordinator) -> None:
    """Cancellation must close transport but not increment failure counters."""
    coordinator._ensure_connection = AsyncMock()
    coordinator._disconnect = AsyncMock()
    coordinator.client = MagicMock(connected=True)
    coordinator._read_input_registers_optimized = AsyncMock(side_effect=asyncio.CancelledError())

    failed_before = coordinator.statistics["failed_reads"]

    with pytest.raises(asyncio.CancelledError):
        await coordinator._async_update_data()

    assert coordinator.statistics["failed_reads"] == failed_before
    coordinator._disconnect.assert_awaited_once()
