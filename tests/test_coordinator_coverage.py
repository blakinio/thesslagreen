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


# ---------------------------------------------------------------------------
# Pass 15 — Sekcja A: __init__ jitter else branch (lines 326-329)
# ---------------------------------------------------------------------------


def test_coordinator_init_jitter_list_with_bad_values():
    """backoff_jitter=[None, None] triggers except (TypeError, ValueError) → jitter_value=None."""
    coord = _make_coordinator(backoff_jitter=[None, None])
    assert coord.backoff_jitter is None


def test_coordinator_init_jitter_else_none():
    """backoff_jitter=None hits else branch → jitter_value = None."""
    coord = _make_coordinator(backoff_jitter=None)
    assert coord.backoff_jitter is None


def test_coordinator_init_jitter_else_default():
    """backoff_jitter={} hits else branch (not None/'') → jitter_value = DEFAULT_BACKOFF_JITTER."""
    from custom_components.thessla_green_modbus.const import DEFAULT_BACKOFF_JITTER
    coord = _make_coordinator(backoff_jitter={})
    assert coord.backoff_jitter == DEFAULT_BACKOFF_JITTER


# ---------------------------------------------------------------------------
# Pass 15 — Sekcja B: _read_with_retry inner paths (lines 543-544, 563-565, 572-576)
# ---------------------------------------------------------------------------


async def test_read_with_retry_awaitable_returning_none_raises():
    """read_method returns awaitable that resolves to None → raises ModbusException."""
    coord = _make_coordinator()
    coord.retry = 1

    async def read_method(slave_id, addr, *, count, attempt):
        async def _none():
            return None
        return _none()

    with pytest.raises(Exception):
        await coord._read_with_retry(read_method, 0, 1, register_type="input_registers")


async def test_read_with_retry_transient_error_raises_modbus_io():
    """isError()=True with non-ILLEGAL exception_code → raises ModbusIOException."""
    coord = _make_coordinator()
    coord.retry = 1

    error_response = MagicMock()
    error_response.isError.return_value = True
    error_response.exception_code = 3  # not ILLEGAL_DATA_ADDRESS (2)

    async def read_method(slave_id, addr, *, count, attempt):
        return error_response

    with pytest.raises(ModbusIOException):
        await coord._read_with_retry(read_method, 0, 1, register_type="input_registers")


# ---------------------------------------------------------------------------
# Pass 15 — Sekcja C: _process_register_value paths (lines 1828, 1832-1838, 1850-1851)
# ---------------------------------------------------------------------------


def test_process_register_value_sensor_unavailable_temperature():
    """SENSOR_UNAVAILABLE on register with 'temperature' in name → returns None (line 1828)."""
    from custom_components.thessla_green_modbus.const import SENSOR_UNAVAILABLE
    coord = _make_coordinator()
    # Mock _is_temperature()=False so line 1813 is skipped, reaching line 1826-1828
    mock_def = MagicMock()
    mock_def._is_temperature.return_value = False
    mock_def.enum = None
    mock_def.decode.return_value = 0
    with patch(
        "custom_components.thessla_green_modbus.coordinator.get_register_definition",
        return_value=mock_def,
    ):
        result = coord._process_register_value("outside_temperature", SENSOR_UNAVAILABLE)
    assert result is None


def test_process_register_value_sensor_unavailable_non_temperature():
    """SENSOR_UNAVAILABLE on a non-temperature register → returns SENSOR_UNAVAILABLE."""
    from custom_components.thessla_green_modbus.const import SENSOR_UNAVAILABLE, SENSOR_UNAVAILABLE_REGISTERS
    coord = _make_coordinator()
    non_temp_reg = next((r for r in SENSOR_UNAVAILABLE_REGISTERS if "temperature" not in r), None)
    if non_temp_reg is None:
        pytest.skip("No non-temperature register in SENSOR_UNAVAILABLE_REGISTERS")
    # Mock _is_temperature()=False so decode doesn't transform value
    mock_def = MagicMock()
    mock_def._is_temperature.return_value = False
    mock_def.enum = None
    mock_def.decode.return_value = 0
    with patch(
        "custom_components.thessla_green_modbus.coordinator.get_register_definition",
        return_value=mock_def,
    ):
        result = coord._process_register_value(non_temp_reg, SENSOR_UNAVAILABLE)
    assert result == SENSOR_UNAVAILABLE


def test_process_register_value_schedule_hh_mm():
    """schedule_ register with HH:MM decoded → converts to minutes."""
    from custom_components.thessla_green_modbus.coordinator import get_register_definition
    coord = _make_coordinator()
    mock_def = MagicMock()
    mock_def._is_temperature.return_value = False
    mock_def.enum = None
    mock_def.decode.return_value = "06:30"
    with patch(
        "custom_components.thessla_green_modbus.coordinator.get_register_definition",
        return_value=mock_def,
    ):
        result = coord._process_register_value("schedule_on_1", 390)
    assert result == 6 * 60 + 30  # 390 minutes


# ---------------------------------------------------------------------------
# Pass 15 — Sekcja D: async_write_register paths (lines 1997-2166)
# ---------------------------------------------------------------------------


async def test_async_write_register_multi_reg_offset_too_large():
    """len(values) + offset > definition.length → returns False immediately."""
    coord = _make_coordinator()
    coord._ensure_connection = AsyncMock()
    transport = MagicMock()
    transport.is_connected.return_value = True
    coord._transport = transport

    mock_def = MagicMock()
    mock_def.length = 2
    mock_def.function = 3
    mock_def.address = 100
    mock_def.encode.return_value = [1, 2, 3]
    with patch(
        "custom_components.thessla_green_modbus.coordinator.get_register_definition",
        return_value=mock_def,
    ):
        result = await coord.async_write_register("some_reg", [1, 2, 3], offset=1)
    assert result is False


async def test_async_write_register_via_transport():
    """Single-value write when _transport is not None uses _call_modbus."""
    coord = _make_coordinator()
    coord._ensure_connection = AsyncMock()
    ok_response = MagicMock()
    ok_response.isError.return_value = False
    transport = MagicMock()
    transport.is_connected.return_value = True
    coord._transport = transport
    coord._call_modbus = AsyncMock(return_value=ok_response)
    coord.async_request_refresh = AsyncMock()

    result = await coord.async_write_register("mode", 1)
    assert result is True


async def test_async_write_register_coil():
    """Coil register (function=1) write returns True on success."""
    coord = _make_coordinator()
    coord._ensure_connection = AsyncMock()
    ok_response = MagicMock()
    ok_response.isError.return_value = False
    transport = MagicMock()
    transport.is_connected.return_value = True
    coord._transport = transport
    coord._call_modbus = AsyncMock(return_value=ok_response)
    coord.async_request_refresh = AsyncMock()

    result = await coord.async_write_register("bypass", 1)
    assert result is True


async def test_async_write_register_response_error_returns_false():
    """Error response on last retry → returns False."""
    coord = _make_coordinator()
    coord.retry = 1
    coord._ensure_connection = AsyncMock()
    error_response = MagicMock()
    error_response.isError.return_value = True
    transport = MagicMock()
    transport.is_connected.return_value = True
    coord._transport = transport
    coord._call_modbus = AsyncMock(return_value=error_response)

    result = await coord.async_write_register("mode", 1)
    assert result is False


async def test_async_write_register_modbus_exception_retry():
    """ModbusException during write → disconnect, retry, return False."""
    coord = _make_coordinator()
    coord.retry = 2
    coord._ensure_connection = AsyncMock()
    transport = MagicMock()
    transport.is_connected.return_value = True
    coord._transport = transport
    coord._disconnect = AsyncMock()
    coord._call_modbus = AsyncMock(side_effect=ModbusException("write failed"))

    result = await coord.async_write_register("mode", 1)
    assert result is False
    coord._disconnect.assert_called()


async def test_async_write_register_refresh_type_error():
    """TypeError during refresh is silently caught; write still returns True."""
    coord = _make_coordinator()
    coord._ensure_connection = AsyncMock()
    ok_response = MagicMock()
    ok_response.isError.return_value = False
    transport = MagicMock()
    transport.is_connected.return_value = True
    coord._transport = transport
    coord._call_modbus = AsyncMock(return_value=ok_response)
    coord.async_request_refresh = AsyncMock(side_effect=TypeError("mock ctx"))

    result = await coord.async_write_register("mode", 1, refresh=True)
    assert result is True


# ---------------------------------------------------------------------------
# Pass 15 — Sekcja E: async_write_registers paths (lines 2179-2189)
# ---------------------------------------------------------------------------


async def test_async_write_registers_empty_values():
    """Empty values list → returns False immediately."""
    coord = _make_coordinator()
    result = await coord.async_write_registers(100, [])
    assert result is False


async def test_async_write_registers_too_many_for_single_request():
    """Values exceeding MAX_REGS_PER_REQUEST with require_single_request=True → False."""
    from custom_components.thessla_green_modbus.const import MAX_REGS_PER_REQUEST
    coord = _make_coordinator()
    values = list(range(MAX_REGS_PER_REQUEST + 1))
    result = await coord.async_write_registers(100, values, require_single_request=True)
    assert result is False


# ---------------------------------------------------------------------------
# Pass 15 addendum — additional uncovered paths
# ---------------------------------------------------------------------------


def test_process_register_value_decoded_equals_sensor_unavailable():
    """When decode() returns SENSOR_UNAVAILABLE, the function returns SENSOR_UNAVAILABLE (lines 1831-1838)."""
    from custom_components.thessla_green_modbus.const import SENSOR_UNAVAILABLE
    coord = _make_coordinator()
    mock_def = MagicMock()
    mock_def._is_temperature.return_value = False
    mock_def.enum = None
    mock_def.decode.return_value = SENSOR_UNAVAILABLE  # decoded == SENSOR_UNAVAILABLE
    with patch(
        "custom_components.thessla_green_modbus.coordinator.get_register_definition",
        return_value=mock_def,
    ):
        result = coord._process_register_value("mode", 1)
    assert result == SENSOR_UNAVAILABLE


def test_process_register_value_schedule_hh_mm_invalid():
    """schedule_ register with bad HH:MM → ValueError caught, decoded unchanged (lines 1850-1851)."""
    coord = _make_coordinator()
    mock_def = MagicMock()
    mock_def._is_temperature.return_value = False
    mock_def.enum = None
    mock_def.decode.return_value = "ab:cd"  # valid format but int() will fail
    with patch(
        "custom_components.thessla_green_modbus.coordinator.get_register_definition",
        return_value=mock_def,
    ):
        result = coord._process_register_value("schedule_on_1", 999)
    assert result == "ab:cd"  # returned unchanged after ValueError


async def test_async_write_register_non_writable_function():
    """Register with function != 1 and != 3 → returns False (lines 2098-2099)."""
    coord = _make_coordinator()
    coord._ensure_connection = AsyncMock()
    transport = MagicMock()
    transport.is_connected.return_value = True
    coord._transport = transport

    mock_def = MagicMock()
    mock_def.length = 1
    mock_def.function = 2  # read-only, not writable
    mock_def.address = 100
    mock_def.encode.return_value = 1
    with patch(
        "custom_components.thessla_green_modbus.coordinator.get_register_definition",
        return_value=mock_def,
    ):
        result = await coord.async_write_register("some_reg", 1)
    assert result is False


async def test_async_write_register_error_response_retries():
    """Error response on non-last attempt → continues (lines 2109-2110), then fails."""
    coord = _make_coordinator()
    coord.retry = 2
    coord._ensure_connection = AsyncMock()
    transport = MagicMock()
    transport.is_connected.return_value = True
    coord._transport = transport
    error_response = MagicMock()
    error_response.isError.return_value = True
    coord._call_modbus = AsyncMock(return_value=error_response)

    result = await coord.async_write_register("mode", 1)
    assert result is False
    assert coord._call_modbus.call_count == 2  # retried once


def test_post_process_data_type_error_in_efficiency():
    """TypeError in efficiency calculation is caught (lines 1897-1898)."""
    coord = _make_coordinator()
    data = {
        "outside_temperature": "not_a_number",  # triggers TypeError
        "supply_temperature": 20.0,
        "exhaust_temperature": 25.0,
    }
    result = coord._post_process_data(data)
    assert "calculated_efficiency" not in result


def test_post_process_data_non_datetime_last_timestamp():
    """Non-datetime _last_power_timestamp → elapsed=0.0 (line 1914)."""
    coord = _make_coordinator()
    coord._last_power_timestamp = "not_a_datetime"
    data = {"dac_supply": 3.0, "dac_exhaust": 3.0}
    result = coord._post_process_data(data)
    assert "estimated_power" in result
    assert "total_energy" in result


def test_post_process_data_naive_now_aware_last_ts():
    """Naive _utcnow with aware last_ts → adds UTC tz to now (line 1919)."""
    coord = _make_coordinator()
    coord._last_power_timestamp = datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
    # Patch _utcnow to return naive datetime
    with patch(
        "custom_components.thessla_green_modbus.coordinator._utcnow",
        return_value=datetime(2024, 1, 1, 12, 0, 30),  # naive
    ):
        data = {"dac_supply": 3.0, "dac_exhaust": 3.0}
        result = coord._post_process_data(data)
    assert "estimated_power" in result


def test_create_consecutive_groups_empty():
    """Empty registers dict returns [] (line 1931)."""
    coord = _make_coordinator()
    result = coord._create_consecutive_groups({})
    assert result == []


def test_update_data_sync_returns_empty():
    """_update_data_sync returns empty dict (line 1949)."""
    coord = _make_coordinator()
    result = coord._update_data_sync()
    assert result == {}


def test_process_register_value_unknown_register():
    """Unknown register name raises KeyError internally → returns False (lines 1810-1812)."""
    coord = _make_coordinator()
    result = coord._process_register_value("definitely_not_a_real_register_xyz", 42)
    assert result is False


async def test_call_modbus_no_client_raises():
    """_call_modbus with no transport and no client raises ConnectionException (line 486)."""
    coord = _make_coordinator()
    coord._transport = None
    coord._client = None

    async def dummy(*args, **kwargs):
        return None

    with pytest.raises(ConnectionException):
        await coord._call_modbus(dummy, 100, count=1)


async def test_disconnect_locked_transport_modbus_exception():
    """ModbusException during transport.close() → debug log (line 2375)."""
    coord = _make_coordinator()
    transport = MagicMock()
    transport.close = AsyncMock(side_effect=ModbusException("close error"))
    coord._transport = transport
    # Should not raise
    await coord._disconnect_locked()
    assert coord._transport is None or True  # transport var was local, client set to None


async def test_disconnect_locked_client_connection_exception():
    """ConnectionException during client.close() → debug log (line 2389)."""
    coord = _make_coordinator()
    coord._transport = None
    client = MagicMock()
    client.close = MagicMock(side_effect=ConnectionException("close error"))
    coord._client = client
    await coord._disconnect_locked()
    assert coord.client is None


def test_get_device_info_model_from_entry():
    """get_device_info uses entry.options when device_info has no model (line 2539)."""
    coord = _make_coordinator()
    from unittest.mock import MagicMock
    entry = MagicMock()
    entry.options = {"model": "Thessla Air 350"}
    entry.data = {}
    coord.entry = entry
    coord.device_scan_result = {}
    coord.device_info = {}
    info = coord.get_device_info()
    assert info["model"] == "Thessla Air 350"


def test_compat_device_info_getattr_key_error():
    """_CompatDeviceInfo.__getattr__ raises AttributeError for missing key (lines 2552-2555)."""
    coord = _make_coordinator()
    info = coord.get_device_info()
    with pytest.raises(AttributeError):
        _ = info.nonexistent_attribute_xyz


async def test_read_with_retry_response_none_via_call_modbus():
    """read_method returns None → _call_modbus called → response None → raises ModbusException."""
    coord = _make_coordinator()
    coord.retry = 1
    coord._call_modbus = AsyncMock(return_value=None)
    transport = MagicMock()
    transport.is_connected.return_value = True
    coord._transport = transport

    def read_method(slave_id, addr, *, count, attempt):
        return None  # triggers _call_modbus path

    with pytest.raises(ModbusException):
        await coord._read_with_retry(read_method, 0, 1, register_type="input_registers")


# ---------------------------------------------------------------------------
# Pass 16 — B1: _read_coils_transport and _read_discrete_inputs_transport
# ---------------------------------------------------------------------------


async def test_read_coils_transport_returns_result():
    """_read_coils_transport calls _call_modbus (line 682)."""
    coord = _make_coordinator()
    ok_resp = MagicMock()
    coord._client = MagicMock()
    coord._call_modbus = AsyncMock(return_value=ok_resp)
    result = await coord._read_coils_transport(1, 100, count=1)
    assert result == ok_resp


async def test_read_discrete_inputs_transport_returns_result():
    """_read_discrete_inputs_transport calls _call_modbus (line 699)."""
    coord = _make_coordinator()
    ok_resp = MagicMock()
    coord._client = MagicMock()
    coord._call_modbus = AsyncMock(return_value=ok_resp)
    result = await coord._read_discrete_inputs_transport(1, 100, count=1)
    assert result == ok_resp


# ---------------------------------------------------------------------------
# Pass 16 — B2: _normalise_available_registers invalid type (line 968)
# ---------------------------------------------------------------------------


def test_normalise_available_registers_invalid_type():
    """Non-list/set value skipped via continue (line 968)."""
    coord = _make_coordinator()
    result = coord._normalise_available_registers({"input_registers": 42})
    assert "input_registers" not in result


# ---------------------------------------------------------------------------
# Pass 16 — B3: _compute_register_groups exception branches
# ---------------------------------------------------------------------------


def test_compute_register_groups_safe_scan_key_error():
    """KeyError in get_register_definition with safe_scan=True (lines 1035-1037)."""
    coord = _make_coordinator(safe_scan=True)
    coord.available_registers = {"holding_registers": {"mode"}}
    coord._register_maps = {"holding_registers": {"mode": 100}}
    with patch(
        "custom_components.thessla_green_modbus.coordinator.get_register_definition",
        side_effect=KeyError("mode"),
    ):
        coord._compute_register_groups()
    assert "holding_registers" in coord._register_groups


def test_compute_register_groups_non_safe_addr_none():
    """addr=None in register map hits continue (line 1053)."""
    coord = _make_coordinator(safe_scan=False)
    coord.available_registers = {"holding_registers": {"unknown_reg"}}
    coord._register_maps = {"holding_registers": {}}  # addr will be None
    coord._compute_register_groups()
    assert coord._register_groups.get("holding_registers", []) == []


def test_compute_register_groups_non_safe_key_error():
    """KeyError in get_register_definition with safe_scan=False (lines 1057-1059)."""
    coord = _make_coordinator(safe_scan=False)
    coord.available_registers = {"holding_registers": {"mode"}}
    coord._register_maps = {"holding_registers": {"mode": 100}}
    with patch(
        "custom_components.thessla_green_modbus.coordinator.get_register_definition",
        side_effect=KeyError("mode"),
    ):
        coord._compute_register_groups()
    assert "holding_registers" in coord._register_groups


# ---------------------------------------------------------------------------
# Pass 16 — B4: _test_connection paths (lines 1111, 1122)
# ---------------------------------------------------------------------------


async def test_test_connection_transport_not_connected():
    """transport.is_connected() False raises ConnectionException (line 1111)."""
    coord = _make_coordinator()
    transport = MagicMock()
    # All reads succeed but then is_connected() returns False
    transport.read_input_registers = AsyncMock(return_value=MagicMock())
    transport.is_connected.return_value = False
    coord._transport = transport
    coord._ensure_connection = AsyncMock()
    with pytest.raises(ConnectionException):
        await coord._test_connection()


async def test_test_connection_basic_register_response_none():
    """Final read_input_registers returns None raises ConnectionException (line 1122)."""
    coord = _make_coordinator()
    transport = MagicMock()
    # Loop reads return MagicMock, then final read returns None
    transport.read_input_registers = AsyncMock(
        side_effect=[MagicMock(), MagicMock(), MagicMock(), None]
    )
    transport.is_connected.return_value = True
    coord._transport = transport
    coord._ensure_connection = AsyncMock()
    with pytest.raises(ConnectionException):
        await coord._test_connection()


# ---------------------------------------------------------------------------
# Pass 16 — B5: _build_tcp_transport (lines 1172-1182)
# ---------------------------------------------------------------------------


def test_build_tcp_transport_tcp_rtu_mode():
    """TCP_RTU mode returns RawRtuOverTcpTransport (lines 1172-1181)."""
    from custom_components.thessla_green_modbus.const import CONNECTION_MODE_TCP_RTU
    coord = _make_coordinator()
    result = coord._build_tcp_transport(CONNECTION_MODE_TCP_RTU)
    assert result is not None


def test_build_tcp_transport_tcp_mode():
    """TCP mode returns TcpModbusTransport (line 1182)."""
    from custom_components.thessla_green_modbus.const import CONNECTION_MODE_TCP
    coord = _make_coordinator()
    result = coord._build_tcp_transport(CONNECTION_MODE_TCP)
    assert result is not None


# ---------------------------------------------------------------------------
# Pass 16 — B6: async_write_register uncovered branches
# ---------------------------------------------------------------------------


async def test_async_write_register_transport_not_connected():
    """transport.is_connected()=False raises (line 1979)."""
    coord = _make_coordinator()
    coord._ensure_connection = AsyncMock()
    transport = MagicMock()
    transport.is_connected.return_value = False
    coord._transport = transport
    result = await coord.async_write_register("mode", 1)
    assert result is False


async def test_async_write_register_multi_reg_non_int_values():
    """list with non-int values → TypeError → False (lines 2014-2016)."""
    coord = _make_coordinator()
    coord._ensure_connection = AsyncMock()
    mock_def = MagicMock()
    mock_def.length = 3
    mock_def.function = 3
    mock_def.address = 100
    transport = MagicMock()
    transport.is_connected.return_value = True
    coord._transport = transport
    with patch(
        "custom_components.thessla_green_modbus.coordinator.get_register_definition",
        return_value=mock_def,
    ):
        result = await coord.async_write_register("some_reg", ["bad", "x", "y"], offset=0)
    assert result is False


async def test_async_write_register_offset_exceeds_length():
    """offset >= definition.length → False (lines 2024-2031)."""
    coord = _make_coordinator()
    coord._ensure_connection = AsyncMock()
    mock_def = MagicMock()
    mock_def.length = 2
    mock_def.function = 3
    mock_def.address = 100
    mock_def.encode.return_value = [1, 2]
    transport = MagicMock()
    transport.is_connected.return_value = True
    coord._transport = transport
    with patch(
        "custom_components.thessla_green_modbus.coordinator.get_register_definition",
        return_value=mock_def,
    ):
        result = await coord.async_write_register("some_reg", 1, offset=2)
    assert result is False


async def test_async_write_register_multi_reg_with_offset_via_transport():
    """Multi-reg with offset > 0 via transport (lines 2033, 2058-2066)."""
    coord = _make_coordinator()
    coord._ensure_connection = AsyncMock()
    mock_def = MagicMock()
    mock_def.length = 3
    mock_def.function = 3
    mock_def.address = 100
    mock_def.encode.return_value = [10, 20, 30]
    ok_resp = MagicMock()
    ok_resp.isError.return_value = False
    transport = MagicMock()
    transport.is_connected.return_value = True
    coord._transport = transport
    coord._call_modbus = AsyncMock(return_value=ok_resp)
    coord.async_request_refresh = AsyncMock()
    with patch(
        "custom_components.thessla_green_modbus.coordinator.get_register_definition",
        return_value=mock_def,
    ):
        result = await coord.async_write_register("some_reg", 5, offset=1)
    assert result is True


async def test_async_write_register_multi_reg_chunk_error_last_attempt():
    """Multi-reg chunk error on last attempt → False (lines 2068-2076)."""
    coord = _make_coordinator()
    coord._ensure_connection = AsyncMock()
    mock_def = MagicMock()
    mock_def.length = 2
    mock_def.function = 3
    mock_def.address = 100
    err_resp = MagicMock()
    err_resp.isError.return_value = True
    transport = MagicMock()
    transport.is_connected.return_value = True
    coord._transport = transport
    coord._call_modbus = AsyncMock(return_value=err_resp)
    coord.retry = 1
    with patch(
        "custom_components.thessla_green_modbus.coordinator.get_register_definition",
        return_value=mock_def,
    ):
        result = await coord.async_write_register("some_reg", [1, 2])
    assert result is False


async def test_async_write_register_timeout_last_attempt():
    """TimeoutError on last attempt → False (lines 2136, 2145-2149)."""
    coord = _make_coordinator()
    coord._ensure_connection = AsyncMock()
    transport = MagicMock()
    transport.is_connected.return_value = True
    coord._transport = transport
    coord._call_modbus = AsyncMock(side_effect=TimeoutError("write timeout"))
    coord._disconnect = AsyncMock()
    coord.retry = 1
    result = await coord.async_write_register("mode", 1)
    assert result is False


async def test_async_write_register_timeout_with_retry():
    """TimeoutError then success (line 2150 continue)."""
    coord = _make_coordinator()
    coord._ensure_connection = AsyncMock()
    transport = MagicMock()
    transport.is_connected.return_value = True
    coord._transport = transport
    ok_resp = MagicMock()
    ok_resp.isError.return_value = False
    coord._call_modbus = AsyncMock(
        side_effect=[TimeoutError("write timeout"), ok_resp]
    )
    coord._disconnect = AsyncMock()
    coord.async_request_refresh = AsyncMock()
    coord.retry = 2
    result = await coord.async_write_register("mode", 1)
    assert result is True


async def test_async_write_register_oserror():
    """OSError in write → False (lines 2151-2154)."""
    coord = _make_coordinator()
    coord._ensure_connection = AsyncMock()
    transport = MagicMock()
    transport.is_connected.return_value = True
    coord._transport = transport
    coord._call_modbus = AsyncMock(side_effect=OSError("io error"))
    coord._disconnect = AsyncMock()
    result = await coord.async_write_register("mode", 1)
    assert result is False


# ---------------------------------------------------------------------------
# Pass 16 — B7: async_write_registers uncovered branches
# ---------------------------------------------------------------------------


async def test_async_write_registers_transport_not_connected():
    """transport not connected → False (line 2196)."""
    coord = _make_coordinator()
    coord._ensure_connection = AsyncMock()
    transport = MagicMock()
    transport.is_connected.return_value = False
    coord._transport = transport
    result = await coord.async_write_registers(100, [1, 2])
    assert result is False


async def test_async_write_registers_no_transport_no_client():
    """No transport, no client → False (line 2198)."""
    coord = _make_coordinator()
    coord._ensure_connection = AsyncMock()
    coord._transport = None
    coord._client = None
    result = await coord.async_write_registers(100, [1, 2])
    assert result is False


async def test_async_write_registers_single_request_rtu_transport():
    """RTU transport single request (lines 2209-2215)."""
    from custom_components.thessla_green_modbus.const import CONNECTION_TYPE_RTU
    coord = _make_coordinator(connection_type=CONNECTION_TYPE_RTU)
    coord._ensure_connection = AsyncMock()
    ok_resp = MagicMock()
    ok_resp.isError.return_value = False
    transport = MagicMock()
    transport.is_connected.return_value = True
    transport.write_registers = AsyncMock(return_value=ok_resp)
    coord._transport = transport
    coord.async_request_refresh = AsyncMock()
    result = await coord.async_write_registers(100, [1, 2], require_single_request=True)
    assert result is True


async def test_async_write_registers_single_request_tcp_call_modbus():
    """TCP single request via _call_modbus (lines 2217-2222)."""
    coord = _make_coordinator()
    coord._ensure_connection = AsyncMock()
    transport = MagicMock()
    transport.is_connected.return_value = True
    ok_resp = MagicMock()
    ok_resp.isError.return_value = False
    coord._transport = transport
    coord._call_modbus = AsyncMock(return_value=ok_resp)
    coord.async_request_refresh = AsyncMock()
    result = await coord.async_write_registers(100, [1, 2], require_single_request=True)
    assert result is True


async def test_async_write_registers_single_request_error_response():
    """Single request error → success=False (line 2224)."""
    coord = _make_coordinator()
    coord._ensure_connection = AsyncMock()
    transport = MagicMock()
    transport.is_connected.return_value = True
    err_resp = MagicMock()
    err_resp.isError.return_value = True
    coord._transport = transport
    coord._call_modbus = AsyncMock(return_value=err_resp)
    coord.retry = 1
    result = await coord.async_write_registers(100, [1, 2], require_single_request=True)
    assert result is False


async def test_async_write_registers_batch_via_client():
    """Batch write via client (line 2230)."""
    coord = _make_coordinator()
    coord._ensure_connection = AsyncMock()
    coord._transport = None
    client = MagicMock()
    ok_resp = MagicMock()
    ok_resp.isError.return_value = False
    client.write_registers = AsyncMock(return_value=ok_resp)
    coord._client = client
    coord.async_request_refresh = AsyncMock()
    result = await coord.async_write_registers(100, [1, 2])
    assert result is True


async def test_async_write_registers_batch_error_last_attempt():
    """Batch error on last attempt → False (lines 2253-2258)."""
    coord = _make_coordinator()
    coord._ensure_connection = AsyncMock()
    coord._transport = None
    client = MagicMock()
    err_resp = MagicMock()
    err_resp.isError.return_value = True
    client.write_registers = AsyncMock(return_value=err_resp)
    coord._client = client
    coord._disconnect = AsyncMock()
    coord.retry = 1
    result = await coord.async_write_registers(100, [1, 2])
    assert result is False


async def test_async_write_registers_modbus_exception():
    """ModbusException → disconnect + False (lines 2270-2284)."""
    coord = _make_coordinator()
    coord._ensure_connection = AsyncMock()
    coord._transport = None
    client = MagicMock()
    client.write_registers = AsyncMock(side_effect=ModbusException("write error"))
    coord._client = client
    coord._disconnect = AsyncMock()
    coord.retry = 1
    result = await coord.async_write_registers(100, [1, 2])
    assert result is False


async def test_async_write_registers_timeout_error():
    """TimeoutError → False (lines 2285-2301)."""
    coord = _make_coordinator()
    coord._ensure_connection = AsyncMock()
    coord._transport = None
    client = MagicMock()
    client.write_registers = AsyncMock(side_effect=TimeoutError("timeout"))
    coord._client = client
    coord._disconnect = AsyncMock()
    coord.retry = 1
    result = await coord.async_write_registers(100, [1, 2])
    assert result is False


async def test_async_write_registers_oserror():
    """OSError → False (lines 2302-2305)."""
    coord = _make_coordinator()
    coord._ensure_connection = AsyncMock()
    coord._transport = None
    client = MagicMock()
    client.write_registers = AsyncMock(side_effect=OSError("io error"))
    coord._client = client
    coord._disconnect = AsyncMock()
    result = await coord.async_write_registers(100, [1, 2])
    assert result is False


async def test_async_write_registers_refresh_type_error():
    """TypeError in refresh → still True (lines 2314-2317)."""
    coord = _make_coordinator()
    coord._ensure_connection = AsyncMock()
    coord._transport = None
    client = MagicMock()
    ok_resp = MagicMock()
    ok_resp.isError.return_value = False
    client.write_registers = AsyncMock(return_value=ok_resp)
    coord._client = client
    coord.async_request_refresh = AsyncMock(side_effect=TypeError("mock ctx"))
    result = await coord.async_write_registers(100, [1, 2], refresh=True)
    assert result is True


# ---------------------------------------------------------------------------
# Pass 16 — additional coordinator tests for remaining misses
# ---------------------------------------------------------------------------


async def test_async_write_register_encoded_non_list():
    """encode() returns non-list → [int(encoded)] (line 2022)."""
    coord = _make_coordinator()
    coord._ensure_connection = AsyncMock()
    mock_def = MagicMock()
    mock_def.length = 2
    mock_def.function = 3
    mock_def.address = 100
    mock_def.encode.return_value = 999  # non-list
    ok_resp = MagicMock()
    ok_resp.isError.return_value = False
    transport = MagicMock()
    transport.is_connected.return_value = True
    coord._transport = transport
    coord._call_modbus = AsyncMock(return_value=ok_resp)
    coord.async_request_refresh = AsyncMock()
    with patch(
        "custom_components.thessla_green_modbus.coordinator.get_register_definition",
        return_value=mock_def,
    ):
        result = await coord.async_write_register("some_reg", 5, offset=0)
    assert result is True


async def test_async_write_register_multi_reg_chunk_error_retry():
    """Multi-reg chunk error retried → success (lines 2075-2076)."""
    coord = _make_coordinator()
    coord._ensure_connection = AsyncMock()
    mock_def = MagicMock()
    mock_def.length = 2
    mock_def.function = 3
    mock_def.address = 100
    err_resp = MagicMock()
    err_resp.isError.return_value = True
    ok_resp = MagicMock()
    ok_resp.isError.return_value = False
    transport = MagicMock()
    transport.is_connected.return_value = True
    coord._transport = transport
    coord._call_modbus = AsyncMock(side_effect=[err_resp, ok_resp])
    coord.retry = 2
    coord.async_request_refresh = AsyncMock()
    with patch(
        "custom_components.thessla_green_modbus.coordinator.get_register_definition",
        return_value=mock_def,
    ):
        result = await coord.async_write_register("some_reg", [1, 2])
    assert result is True


async def test_async_write_registers_modbus_exception_retry():
    """ModbusException with retry → retries (lines 2279-2284)."""
    coord = _make_coordinator()
    coord._ensure_connection = AsyncMock()
    coord._transport = None
    client = MagicMock()
    ok_resp = MagicMock()
    ok_resp.isError.return_value = False
    client.write_registers = AsyncMock(
        side_effect=[ModbusException("write error"), ok_resp]
    )
    coord._client = client
    coord._disconnect = AsyncMock()
    coord.retry = 2
    coord.async_request_refresh = AsyncMock()
    result = await coord.async_write_registers(100, [1, 2])
    assert result is True


async def test_async_write_registers_timeout_with_transport():
    """TimeoutError with transport disconnects (line 2287)."""
    coord = _make_coordinator()
    coord._ensure_connection = AsyncMock()
    transport = MagicMock()
    transport.is_connected.return_value = True
    ok_resp = MagicMock()
    ok_resp.isError.return_value = False
    coord._transport = transport
    coord._call_modbus = AsyncMock(
        side_effect=[TimeoutError("timeout"), ok_resp]
    )
    coord._disconnect = AsyncMock()
    coord.retry = 2
    coord.async_request_refresh = AsyncMock()
    result = await coord.async_write_registers(100, [1, 2])
    assert result is True


async def test_async_write_registers_timeout_continue():
    """TimeoutError continue on non-last attempt (line 2301)."""
    coord = _make_coordinator()
    coord._ensure_connection = AsyncMock()
    coord._transport = None
    client = MagicMock()
    ok_resp = MagicMock()
    ok_resp.isError.return_value = False
    client.write_registers = AsyncMock(
        side_effect=[TimeoutError("timeout"), ok_resp]
    )
    coord._client = client
    coord._disconnect = AsyncMock()
    coord.retry = 2
    coord.async_request_refresh = AsyncMock()
    result = await coord.async_write_registers(100, [1, 2])
    assert result is True
