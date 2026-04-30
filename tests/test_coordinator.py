"""Tests for ThesslaGreenModbusCoordinator - HA 2025.7.1+ & pymodbus 3.5+ Compatible."""

import asyncio
import logging
import types
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from custom_components.thessla_green_modbus.const import (
    CONF_MAX_REGISTERS_PER_REQUEST,
    DEFAULT_BACKOFF_JITTER,
    MAX_BATCH_REGISTERS,
)
from custom_components.thessla_green_modbus.modbus_exceptions import (
    ConnectionException,
    ModbusException,
)
from custom_components.thessla_green_modbus.registers.loader import (
    RegisterDef,
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
)
from custom_components.thessla_green_modbus.coordinator.coordinator import (
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
async def test_async_write_multi_register_start(coordinator, monkeypatch):
    """Writing multi-register from start address succeeds."""
    coordinator.async_request_refresh = AsyncMock()
    coordinator._ensure_connection = AsyncMock()
    client = MagicMock()
    response = MagicMock()
    response.isError.return_value = False
    client.write_registers = AsyncMock(return_value=response)
    coordinator.client = client

    import custom_components.thessla_green_modbus.coordinator.coordinator as coordinator_mod

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

    import custom_components.thessla_green_modbus.coordinator.coordinator as coordinator_mod

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

    import custom_components.thessla_green_modbus.coordinator.coordinator as coordinator_mod

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

    import custom_components.thessla_green_modbus.coordinator.coordinator as coordinator_mod

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

    import custom_components.thessla_green_modbus.coordinator.coordinator as coordinator_mod

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

    import custom_components.thessla_green_modbus.coordinator.coordinator as coordinator_mod

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
        "custom_components.thessla_green_modbus.coordinator.coordinator.AsyncModbusTcpClient",
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
            "custom_components.thessla_green_modbus.coordinator.coordinator.ThesslaGreenDeviceScanner.create",
            AsyncMock(return_value=scanner_instance),
        ),
        pytest.raises(CannotConnect) as err,
    ):
        await coordinator.async_setup()

    assert str(err.value) == "invalid_capabilities"
    scanner_instance.close.assert_awaited_once()


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
