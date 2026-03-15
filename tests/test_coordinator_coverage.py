"""Targeted coverage tests for coordinator.py uncovered lines."""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from custom_components.thessla_green_modbus.coordinator import (
    ThesslaGreenModbusCoordinator,
    _SafeDTUtil,
    _PermanentModbusError,
    _utcnow,
    dt_util as coordinator_dt_util,
)
from custom_components.thessla_green_modbus.modbus_exceptions import (
    ConnectionException,
    ModbusException,
    ModbusIOException,
)

pytestmark = pytest.mark.asyncio


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_coordinator(**kwargs) -> ThesslaGreenModbusCoordinator:
    hass = MagicMock()
    hass.async_add_executor_job = None
    return ThesslaGreenModbusCoordinator(
        hass=hass,
        host="192.168.1.1",
        port=502,
        slave_id=1,
        name="test",
        scan_interval=30,
        timeout=3,
        retry=2,
        **kwargs,
    )


# ---------------------------------------------------------------------------
# Group A — _SafeDTUtil & _utcnow fallback paths (lines 47-79)
# ---------------------------------------------------------------------------


def test_safe_dt_util_coerce_non_datetime_returns_now():
    """_SafeDTUtil._coerce returns now() when given non-datetime (covers line 50)."""
    result = _SafeDTUtil._coerce(None)
    assert isinstance(result, datetime)
    assert result.tzinfo is not None


def test_safe_dt_util_coerce_naive_datetime_adds_utc():
    """_SafeDTUtil._coerce adds tzinfo to naive datetime."""
    naive = datetime(2024, 1, 1, 12, 0, 0)
    result = _SafeDTUtil._coerce(naive)
    assert result.tzinfo is not None


def test_safe_dt_util_now_no_callable_base():
    """_SafeDTUtil.now falls back to datetime.now when base has no callable `now` (line 56)."""
    stub = _SafeDTUtil(object())  # object() has no `now` attribute
    result = stub.now()
    assert isinstance(result, datetime)
    assert result.tzinfo is not None


def test_safe_dt_util_utcnow_no_callable_base():
    """_SafeDTUtil.utcnow falls back to datetime.now when base has no callable `utcnow` (line 62)."""
    stub = _SafeDTUtil(object())
    result = stub.utcnow()
    assert isinstance(result, datetime)
    assert result.tzinfo is not None


def test_safe_dt_util_now_returns_none_from_base():
    """_SafeDTUtil.now coerces None result to timezone-aware datetime."""
    from types import SimpleNamespace
    base = SimpleNamespace(now=lambda: None)
    stub = _SafeDTUtil(base)
    result = stub.now()
    assert isinstance(result, datetime)
    assert result.tzinfo is not None


def test_utcnow_fallback_when_utcnow_returns_non_datetime():
    """_utcnow returns datetime.now(UTC) when utcnow callable returns non-datetime (line 79)."""
    with patch.object(coordinator_dt_util, "utcnow", return_value=None):
        result = _utcnow()
    assert isinstance(result, datetime)
    assert result.tzinfo is not None


# ---------------------------------------------------------------------------
# Group B — __init__ invalid parameter values (lines 310-376)
# ---------------------------------------------------------------------------


def test_coordinator_init_bad_backoff_falls_back():
    """ValueError in float(backoff) is caught; self.backoff = DEFAULT_BACKOFF (lines 310-313)."""
    coord = _make_coordinator(backoff="not_a_float")
    from custom_components.thessla_green_modbus.const import DEFAULT_BACKOFF
    assert coord.backoff == DEFAULT_BACKOFF


def test_coordinator_init_bad_baud_rate_falls_back():
    """ValueError in int(baud_rate) is caught; self.baud_rate = DEFAULT_BAUD_RATE (lines 348-351)."""
    coord = _make_coordinator(baud_rate="not_an_int")
    from custom_components.thessla_green_modbus.const import DEFAULT_BAUD_RATE
    assert coord.baud_rate == DEFAULT_BAUD_RATE


def test_coordinator_init_jitter_list_two_floats():
    """backoff_jitter as list with 2 elements creates tuple jitter (lines 323-327)."""
    coord = _make_coordinator(backoff_jitter=[0.1, 0.5])
    assert coord.backoff_jitter == (0.1, 0.5)


def test_coordinator_init_jitter_string_float():
    """backoff_jitter as string float is parsed to float (lines 318-322)."""
    coord = _make_coordinator(backoff_jitter="0.3")
    assert coord.backoff_jitter == 0.3


def test_coordinator_init_jitter_bad_string():
    """backoff_jitter as bad string falls back to None (lines 319-322)."""
    coord = _make_coordinator(backoff_jitter="bad")
    assert coord.backoff_jitter is None


def test_coordinator_init_jitter_zero():
    """backoff_jitter = 0 is stored as 0.0 (line 331-332)."""
    coord = _make_coordinator(backoff_jitter=0)
    assert coord.backoff_jitter == 0.0


# ---------------------------------------------------------------------------
# Group C — _get_client_method fallback no-op (lines 509-527)
# ---------------------------------------------------------------------------


async def test_get_client_method_fallback_noop():
    """_get_client_method returns callable no-op when method not found (lines 523-527)."""
    coord = _make_coordinator()
    coord._client = None
    coord._transport = None
    method = coord._get_client_method("nonexistent_method_xyz")
    assert callable(method)
    result = await method()
    assert result is None


async def test_get_client_method_from_client():
    """_get_client_method returns method from client when transport not found."""
    coord = _make_coordinator()
    coord._transport = None
    client = MagicMock()
    expected = AsyncMock(return_value="ok")
    client.read_holding_registers = expected
    coord._client = client
    method = coord._get_client_method("read_holding_registers")
    assert method is expected


# ---------------------------------------------------------------------------
# Group D — _apply_scan_cache (lines 974-997)
# ---------------------------------------------------------------------------


def test_apply_scan_cache_no_available_returns_false():
    """cache without available_registers dict returns False (lines 977-979)."""
    coord = _make_coordinator()
    assert coord._apply_scan_cache({}) is False


def test_apply_scan_cache_non_dict_available_returns_false():
    """available_registers that's a string returns False."""
    coord = _make_coordinator()
    assert coord._apply_scan_cache({"available_registers": "bad"}) is False


def test_apply_scan_cache_valid_data_applies():
    """Valid cache with list registers succeeds and returns True."""
    coord = _make_coordinator()
    cache = {
        "available_registers": {
            "input_registers": ["outside_temperature"],
            "holding_registers": ["mode"],
        },
        "device_info": {"firmware": "4.8"},
        "capabilities": {},
    }
    result = coord._apply_scan_cache(cache)
    assert result is True
    assert coord.device_info == {"firmware": "4.8"}


def test_apply_scan_cache_non_list_values_filtered():
    """Non-list register values are filtered out in _normalise_available_registers."""
    coord = _make_coordinator()
    cache = {
        "available_registers": {
            "input_registers": "not_a_list",
            "holding_registers": ["mode"],
        }
    }
    result = coord._apply_scan_cache(cache)
    assert result is True
    assert "holding_registers" in coord.available_registers


# ---------------------------------------------------------------------------
# Group H — _compute_register_groups safe_scan=True (lines 1026-1047)
# ---------------------------------------------------------------------------


def test_compute_register_groups_safe_scan():
    """safe_scan=True produces per-register (addr, length) tuples (lines 1026-1047)."""
    coord = _make_coordinator(safe_scan=True)
    coord.available_registers = {
        "input_registers": {"outside_temperature"},
        "holding_registers": set(),
        "coil_registers": set(),
        "discrete_inputs": set(),
    }
    coord._compute_register_groups()
    groups = coord._register_groups.get("input_registers", [])
    assert isinstance(groups, list)
    assert len(groups) >= 1
    addr, length = groups[0]
    assert isinstance(addr, int)
    assert isinstance(length, int)


def test_compute_register_groups_safe_scan_unknown_register():
    """Unknown register in safe_scan mode is skipped gracefully."""
    coord = _make_coordinator(safe_scan=True)
    coord.available_registers = {
        "input_registers": {"__unknown_reg_xyz__"},
        "holding_registers": set(),
        "coil_registers": set(),
        "discrete_inputs": set(),
    }
    coord._compute_register_groups()
    # No exception should be raised; groups for input_registers is empty since reg not in map
    groups = coord._register_groups.get("input_registers", [])
    assert isinstance(groups, list)


# ---------------------------------------------------------------------------
# Group I — _test_connection exception handlers (lines 1125-1141)
# ---------------------------------------------------------------------------


async def test_test_connection_modbus_io_cancelled_skips():
    """ModbusIOException with 'cancelled' message is swallowed (lines 1125-1130)."""
    coord = _make_coordinator()
    coord._ensure_connection = AsyncMock()

    transport = MagicMock()
    transport.is_connected.return_value = True
    transport.read_input_registers = AsyncMock(
        side_effect=ModbusIOException("request cancelled")
    )
    coord._transport = transport

    # Should not raise
    await coord._test_connection()


async def test_test_connection_timeout_raises():
    """TimeoutError in _test_connection is re-raised (lines 1136-1138)."""
    coord = _make_coordinator()
    coord._ensure_connection = AsyncMock(side_effect=TimeoutError("timed out"))

    with pytest.raises(TimeoutError):
        await coord._test_connection()


async def test_test_connection_oserror_raises():
    """OSError in _test_connection is re-raised (lines 1139-1141)."""
    coord = _make_coordinator()
    coord._ensure_connection = AsyncMock(side_effect=OSError("conn refused"))

    with pytest.raises(OSError):
        await coord._test_connection()


async def test_test_connection_modbus_io_non_cancelled_raises():
    """Non-cancelled ModbusIOException is re-raised (lines 1131-1132)."""
    coord = _make_coordinator()
    coord._ensure_connection = AsyncMock()

    transport = MagicMock()
    transport.is_connected.return_value = True
    transport.read_input_registers = AsyncMock(
        side_effect=ModbusIOException("register error")
    )
    coord._transport = transport

    with pytest.raises(ModbusIOException):
        await coord._test_connection()


# ---------------------------------------------------------------------------
# Group N — calculate_power_consumption (lines 1856-1881)
# ---------------------------------------------------------------------------


def test_calculate_power_consumption_basic():
    """calculate_power_consumption returns float when dac_supply/exhaust provided."""
    coord = _make_coordinator()
    data = {"dac_supply": 5.0, "dac_exhaust": 5.0}
    result = coord.calculate_power_consumption(data)
    assert result is not None
    assert isinstance(result, float)
    assert result > 0


def test_calculate_power_consumption_with_heater_and_cooler():
    """Heater and cooler voltages contribute to power (lines 1876-1879)."""
    coord = _make_coordinator()
    data = {"dac_supply": 8.0, "dac_exhaust": 7.0, "dac_heater": 5.0, "dac_cooler": 3.0}
    result = coord.calculate_power_consumption(data)
    assert result is not None
    assert result > 0


def test_calculate_power_consumption_missing_keys_returns_none():
    """KeyError on missing dac_supply/exhaust returns None (lines 1861-1862)."""
    coord = _make_coordinator()
    result = coord.calculate_power_consumption({})
    assert result is None


def test_calculate_power_consumption_invalid_type_returns_none():
    """TypeError on non-numeric values returns None."""
    coord = _make_coordinator()
    result = coord.calculate_power_consumption({"dac_supply": "bad", "dac_exhaust": 5.0})
    assert result is None


# ---------------------------------------------------------------------------
# Group O — _post_process_data branches (lines 1883-1925)
# ---------------------------------------------------------------------------


def test_post_process_data_zero_division_error():
    """ZeroDivisionError when exhaust == outside is caught silently (lines 1894-1898)."""
    coord = _make_coordinator()
    data = {
        "outside_temperature": 20.0,
        "supply_temperature": 22.0,
        "exhaust_temperature": 20.0,  # Same as outside → ZeroDivisionError
    }
    result = coord._post_process_data(data)
    # Should not raise; calculated_efficiency is absent
    assert "calculated_efficiency" not in result


def test_post_process_data_efficiency_calculated():
    """Heat recovery efficiency is calculated when temperatures differ."""
    coord = _make_coordinator()
    data = {
        "outside_temperature": 0.0,
        "supply_temperature": 18.0,
        "exhaust_temperature": 20.0,
    }
    result = coord._post_process_data(data)
    assert "calculated_efficiency" in result
    assert 0 <= result["calculated_efficiency"] <= 100


def test_post_process_data_flow_balance():
    """Flow balance is calculated from supply and exhaust flow rates."""
    coord = _make_coordinator()
    data = {"supply_flow_rate": 100, "exhaust_flow_rate": 75}
    result = coord._post_process_data(data)
    assert result["flow_balance"] == 25
    assert result["flow_balance_status"] == "supply_dominant"


def test_post_process_data_flow_balance_exhaust_dominant():
    """Flow balance status is exhaust_dominant when exhaust > supply."""
    coord = _make_coordinator()
    data = {"supply_flow_rate": 80, "exhaust_flow_rate": 100}
    result = coord._post_process_data(data)
    assert result["flow_balance_status"] == "exhaust_dominant"


def test_post_process_data_flow_balance_balanced():
    """Flow balance status is balanced when diff < 10."""
    coord = _make_coordinator()
    data = {"supply_flow_rate": 100, "exhaust_flow_rate": 98}
    result = coord._post_process_data(data)
    assert result["flow_balance_status"] == "balanced"


def test_post_process_data_power_calculation():
    """Power is estimated and energy accumulated when DAC values provided."""
    coord = _make_coordinator()
    data = {"dac_supply": 5.0, "dac_exhaust": 5.0}
    result = coord._post_process_data(data)
    assert "estimated_power" in result
    assert "total_energy" in result


def test_post_process_data_timezone_aware_timestamp():
    """Timezone-aware last timestamp is handled correctly (lines 1916-1919)."""
    coord = _make_coordinator()
    # Set a timezone-aware last timestamp
    coord._last_power_timestamp = datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
    data = {"dac_supply": 3.0, "dac_exhaust": 3.0}
    result = coord._post_process_data(data)
    assert "estimated_power" in result


# ---------------------------------------------------------------------------
# Group R — async_write_temporary_* (lines 2320-2366)
# ---------------------------------------------------------------------------


async def test_async_write_temporary_airflow():
    """async_write_temporary_airflow calls async_write_registers when registers exist."""
    coord = _make_coordinator()
    coord.async_write_registers = AsyncMock(return_value=True)
    from custom_components.thessla_green_modbus.coordinator import get_register_definition
    mock_def = MagicMock()
    mock_def.encode = MagicMock(return_value=1)
    with patch(
        "custom_components.thessla_green_modbus.coordinator.get_register_definition",
        return_value=mock_def,
    ):
        result = await coord.async_write_temporary_airflow(50.0)
    assert result is True
    coord.async_write_registers.assert_called_once()


async def test_async_write_temporary_airflow_missing_register():
    """async_write_temporary_airflow returns False when registers unavailable (lines 2327-2329)."""
    coord = _make_coordinator()
    with patch(
        "custom_components.thessla_green_modbus.coordinator.get_register_definition",
        side_effect=KeyError("cfg_mode1"),
    ):
        result = await coord.async_write_temporary_airflow(50.0)
    assert result is False


async def test_async_write_temporary_temperature():
    """async_write_temporary_temperature calls async_write_registers when registers exist."""
    coord = _make_coordinator()
    coord.async_write_registers = AsyncMock(return_value=True)
    mock_def = MagicMock()
    mock_def.encode = MagicMock(return_value=1)
    with patch(
        "custom_components.thessla_green_modbus.coordinator.get_register_definition",
        return_value=mock_def,
    ):
        result = await coord.async_write_temporary_temperature(22.0)
    assert result is True
    coord.async_write_registers.assert_called_once()


async def test_async_write_temporary_temperature_missing_register():
    """async_write_temporary_temperature returns False when registers unavailable (lines 2352-2354)."""
    coord = _make_coordinator()
    with patch(
        "custom_components.thessla_green_modbus.coordinator.get_register_definition",
        side_effect=KeyError("cfg_mode2"),
    ):
        result = await coord.async_write_temporary_temperature(22.0)
    assert result is False


# ---------------------------------------------------------------------------
# Group S — _disconnect_locked / _disconnect / async_shutdown (lines 2368-2416)
# ---------------------------------------------------------------------------


async def test_disconnect_locked_with_transport_oserror():
    """OSError on transport.close() is caught silently (lines 2376-2377)."""
    coord = _make_coordinator()
    transport = MagicMock()
    transport.close = AsyncMock(side_effect=OSError("io error"))
    coord._transport = transport

    # Should not raise
    await coord._disconnect_locked()
    assert coord._client is None


async def test_disconnect_locked_with_client_oserror():
    """OSError on client.close() is caught silently (lines 2388-2391)."""
    coord = _make_coordinator()
    coord._transport = None
    client = MagicMock()
    client.close = AsyncMock(side_effect=OSError("io error"))
    coord._client = client

    await coord._disconnect_locked()
    assert coord._client is None


async def test_disconnect_locked_with_client_sync_close_awaitable():
    """Sync client.close() result that is awaitable is awaited (lines 2385-2387)."""
    coord = _make_coordinator()
    coord._transport = None
    client = MagicMock()

    async def _close_coro():
        return None

    # close is not a coroutinefunction itself, but returns an awaitable
    client.close = MagicMock(return_value=_close_coro())
    coord._client = client

    await coord._disconnect_locked()
    assert coord._client is None


async def test_disconnect_acquires_lock():
    """_disconnect acquires _client_lock and calls _disconnect_locked."""
    coord = _make_coordinator()
    coord._disconnect_locked = AsyncMock()
    await coord._disconnect()
    coord._disconnect_locked.assert_called_once()


async def test_async_shutdown_calls_disconnect():
    """async_shutdown calls stop_listener and disconnects (lines 2407-2416)."""
    coord = _make_coordinator()
    coord._disconnect = AsyncMock()
    stop_listener_mock = MagicMock()
    coord._stop_listener = stop_listener_mock

    await coord.async_shutdown()

    stop_listener_mock.assert_called_once()
    assert coord._stop_listener is None
    coord._disconnect.assert_called_once()


# ---------------------------------------------------------------------------
# Group T — status_overview / performance_stats / get_diagnostic_data (2419-2522)
# ---------------------------------------------------------------------------


def test_status_overview_no_last_update():
    """status_overview works when no last successful update exists."""
    coord = _make_coordinator()
    overview = coord.status_overview
    assert "online" in overview
    assert "last_successful_read" in overview
    assert overview["last_successful_read"] is None
    assert "error_count" in overview


def test_status_overview_with_last_update_and_connected_transport():
    """status_overview shows online=True when transport connected and recent update."""
    coord = _make_coordinator()
    coord.statistics["last_successful_update"] = _utcnow()
    transport = MagicMock()
    transport.is_connected.return_value = True
    coord._transport = transport

    overview = coord.status_overview
    assert overview["online"] is True
    assert overview["last_successful_read"] is not None


def test_status_overview_counts_all_errors():
    """error_count sums failed_reads, connection_errors, and timeout_errors."""
    coord = _make_coordinator()
    coord.statistics["failed_reads"] = 2
    coord.statistics["connection_errors"] = 3
    coord.statistics["timeout_errors"] = 1

    overview = coord.status_overview
    assert overview["error_count"] == 6


def test_performance_stats_structure():
    """performance_stats returns expected keys."""
    coord = _make_coordinator()
    stats = coord.performance_stats
    assert "total_reads" in stats
    assert "failed_reads" in stats
    assert "success_rate" in stats
    assert "avg_response_time" in stats
    assert "connection_errors" in stats
    assert "last_error" in stats
    assert "registers_available" in stats
    assert "registers_read" in stats


def test_performance_stats_success_rate():
    """success_rate = 100% when only successful reads."""
    coord = _make_coordinator()
    coord.statistics["successful_reads"] = 10
    coord.statistics["failed_reads"] = 0
    stats = coord.performance_stats
    assert stats["success_rate"] == 100.0


def test_get_diagnostic_data_structure():
    """get_diagnostic_data returns all expected keys."""
    coord = _make_coordinator()
    coord.last_scan = _utcnow()
    coord.statistics["last_successful_update"] = _utcnow()
    data = coord.get_diagnostic_data()
    assert "connection" in data
    assert "statistics" in data
    assert "performance" in data
    assert "status_overview" in data
    assert "device_info" in data
    assert "available_registers" in data
    assert "capabilities" in data
    assert "last_scan" in data


def test_get_diagnostic_data_with_raw_registers():
    """get_diagnostic_data includes raw_registers when in device_scan_result."""
    coord = _make_coordinator()
    coord.device_scan_result = {
        "raw_registers": {"0": 123},
        "total_addresses_scanned": 100,
    }
    data = coord.get_diagnostic_data()
    assert "raw_registers" in data


# ---------------------------------------------------------------------------
# Additional coverage: __init__ branches (lines 289-294, 371-399)
# ---------------------------------------------------------------------------


def test_coordinator_init_super_type_error_fallback():
    """super().__init__ TypeError fallback sets attrs manually (lines 289-294)."""
    from custom_components.thessla_green_modbus.coordinator import ThesslaGreenModbusCoordinator
    hass = MagicMock()
    # Patch the base class __init__ to raise TypeError on the first call
    original_init = ThesslaGreenModbusCoordinator.__bases__[0].__init__

    call_count = [0]

    def patched_init(self, *args, **kwargs):
        call_count[0] += 1
        if call_count[0] == 1 and args:
            raise TypeError("unexpected keyword argument")
        # Second call (fallback with no args) should succeed

    with patch.object(ThresslaGreenCoordinatorBase := ThesslaGreenModbusCoordinator.__bases__[0],
                      "__init__", patched_init):
        coord = ThesslaGreenModbusCoordinator(
            hass=hass, host="localhost", port=502, slave_id=1
        )
    # If TypeError fallback ran, hass should be set
    assert coord.hass is hass


def test_coordinator_init_entry_bad_max_registers_per_request():
    """TypeError/ValueError in entry.options max_registers → MAX_REGS_PER_REQUEST (lines 371-372)."""
    from custom_components.thessla_green_modbus.const import CONF_MAX_REGISTERS_PER_REQUEST
    entry = MagicMock()
    entry.entry_id = "test"
    entry.data = {}
    entry.options = {CONF_MAX_REGISTERS_PER_REQUEST: "not_a_number"}
    hass = MagicMock()
    coord = ThesslaGreenModbusCoordinator(
        hass=hass, host="localhost", port=502, slave_id=1, entry=entry
    )
    from custom_components.thessla_green_modbus.const import MAX_BATCH_REGISTERS
    assert coord.effective_batch == MAX_BATCH_REGISTERS


def test_coordinator_init_max_registers_less_than_1():
    """effective_batch < 1 is raised to 1 (lines 375-376)."""
    coord = _make_coordinator(max_registers_per_request=0)
    assert coord.effective_batch == 1


def test_coordinator_init_entry_bad_capabilities():
    """Invalid capabilities dict in entry.data is caught (lines 397-399)."""
    from custom_components.thessla_green_modbus.coordinator import DeviceCapabilities
    entry = MagicMock()
    entry.entry_id = "test"
    entry.data = {"capabilities": {"_invalid_kwarg": "bad"}}
    entry.options = {}
    hass = MagicMock()

    original_init = DeviceCapabilities.__init__
    call_count = [0]

    def patched_init(self, **kwargs):
        call_count[0] += 1
        if kwargs:  # Called with kwargs from entry.data → raise TypeError
            raise TypeError("bad kwarg")
        original_init(self)

    with patch.object(DeviceCapabilities, "__init__", patched_init):
        coord = ThesslaGreenModbusCoordinator(
            hass=hass, host="localhost", port=502, slave_id=1, entry=entry
        )
    # Should not raise; capabilities remains default
    assert coord.capabilities is not None


# ---------------------------------------------------------------------------
# _read_coils_transport / _read_discrete_inputs_transport (lines 680-704)
# ---------------------------------------------------------------------------


async def test_read_coils_transport_raises_when_no_client():
    """_read_coils_transport raises ConnectionException when client=None (lines 680-681)."""
    coord = _make_coordinator()
    coord._client = None
    coord._transport = None

    with pytest.raises(ConnectionException):
        await coord._read_coils_transport(1, 0, count=1)


async def test_read_discrete_inputs_transport_raises_when_no_client():
    """_read_discrete_inputs_transport raises ConnectionException when client=None (lines 697-698)."""
    coord = _make_coordinator()
    coord._client = None
    coord._transport = None

    with pytest.raises(ConnectionException):
        await coord._read_discrete_inputs_transport(1, 0, count=1)


# ---------------------------------------------------------------------------
# async_setup shortcuts (lines 709, 720-728, 874-877)
# ---------------------------------------------------------------------------


async def test_async_setup_force_full_register_list():
    """force_full_register_list=True skips scan and loads full list (lines 874-877)."""
    coord = _make_coordinator(force_full_register_list=True)
    coord._ensure_connection = AsyncMock()
    coord._test_connection = AsyncMock()

    result = await coord.async_setup()
    assert result is True
    # All registers should be loaded
    assert len(coord.available_registers["input_registers"]) > 0


async def test_async_setup_scan_disabled_no_entry():
    """scan disabled with no entry falls back to full register list (lines 720-728)."""
    coord = _make_coordinator()
    coord.enable_device_scan = False
    coord.force_full_register_list = False
    coord.entry = None
    coord._ensure_connection = AsyncMock()
    coord._test_connection = AsyncMock()

    result = await coord.async_setup()
    assert result is True


async def test_async_setup_rtu_connection_type():
    """async_setup uses serial_port endpoint for RTU connection type (line 709)."""
    from custom_components.thessla_green_modbus.const import CONNECTION_TYPE_RTU
    coord = _make_coordinator(connection_type=CONNECTION_TYPE_RTU, serial_port="/dev/ttyUSB0")
    coord.enable_device_scan = False
    coord.force_full_register_list = False
    coord.entry = None
    coord._ensure_connection = AsyncMock()
    coord._test_connection = AsyncMock()

    result = await coord.async_setup()
    assert result is True


# ---------------------------------------------------------------------------
# _load_full_register_list with skip_missing_registers (lines 944-946)
# ---------------------------------------------------------------------------


def test_load_full_register_list_skips_missing():
    """skip_missing_registers=True removes known-missing registers (lines 944-946)."""
    coord = _make_coordinator(skip_missing_registers=True)
    coord._load_full_register_list()
    # Should have loaded registers without raising
    assert isinstance(coord.available_registers, dict)


# ---------------------------------------------------------------------------
# _clear_register_failure (line 1085)
# ---------------------------------------------------------------------------


def test_clear_register_failure_with_attribute():
    """_clear_register_failure discards from _failed_registers when attr exists (line 1085)."""
    coord = _make_coordinator()
    coord._failed_registers = {"outside_temperature", "mode"}
    coord._clear_register_failure("outside_temperature")
    assert "outside_temperature" not in coord._failed_registers
    assert "mode" in coord._failed_registers


# ---------------------------------------------------------------------------
# _test_connection: transport is None after _ensure_connection (line 1095)
# ---------------------------------------------------------------------------


async def test_test_connection_transport_none_raises():
    """ConnectionException when transport is None after _ensure_connection (line 1095)."""
    coord = _make_coordinator()
    coord._transport = None
    coord._ensure_connection = AsyncMock()  # does nothing, transport stays None

    with pytest.raises(ConnectionException):
        await coord._test_connection()


async def test_test_connection_response_none_raises():
    """ConnectionException when read_input_registers returns None (lines 1105-1106)."""
    coord = _make_coordinator()
    coord._ensure_connection = AsyncMock()

    transport = MagicMock()
    transport.is_connected.return_value = True
    transport.read_input_registers = AsyncMock(return_value=None)
    coord._transport = transport

    with pytest.raises(ConnectionException):
        await coord._test_connection()


async def test_test_connection_successful():
    """Full successful connection test (lines 1110-1124)."""
    coord = _make_coordinator()
    coord._ensure_connection = AsyncMock()

    ok_response = MagicMock()
    ok_response.isError.return_value = False
    ok_response.registers = [100]

    transport = MagicMock()
    transport.is_connected.return_value = True
    transport.read_input_registers = AsyncMock(return_value=ok_response)
    coord._transport = transport

    # Should complete without exception
    await coord._test_connection()


async def test_test_connection_modbus_exception_raises():
    """ModbusException in _test_connection is re-raised (lines 1133-1135)."""
    coord = _make_coordinator()
    coord._ensure_connection = AsyncMock()

    transport = MagicMock()
    transport.is_connected.return_value = True
    transport.read_input_registers = AsyncMock(
        side_effect=ModbusException("modbus error")
    )
    coord._transport = transport

    with pytest.raises(ModbusException):
        await coord._test_connection()


# ---------------------------------------------------------------------------
# _apply_scan_cache exception branch (lines 985-986)
# ---------------------------------------------------------------------------


def test_apply_scan_cache_normalise_exception():
    """TypeError in _normalise_available_registers returns False (lines 985-986)."""
    coord = _make_coordinator()
    with patch.object(
        coord,
        "_normalise_available_registers",
        side_effect=TypeError("bad"),
    ):
        result = coord._apply_scan_cache(
            {"available_registers": {"input_registers": ["mode"]}}
        )
    assert result is False


def test_apply_scan_cache_invalid_capabilities():
    """Invalid capabilities dict in cache is caught silently (lines 994-995)."""
    from custom_components.thessla_green_modbus.coordinator import DeviceCapabilities
    coord = _make_coordinator()
    with patch.object(DeviceCapabilities, "__init__", side_effect=TypeError("bad")):
        result = coord._apply_scan_cache({
            "available_registers": {"input_registers": ["mode"]},
            "capabilities": {"bad_key": 1},
        })
    assert result is True  # overall still succeeds
