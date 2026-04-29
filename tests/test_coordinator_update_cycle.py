"""Targeted coverage tests for coordinator.py uncovered lines."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from custom_components.thessla_green_modbus.coordinator import (
    ThesslaGreenModbusCoordinator,
)
from custom_components.thessla_green_modbus.modbus_exceptions import (
    ConnectionException,
    ModbusException,
    ModbusIOException,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_coordinator(**kwargs) -> ThesslaGreenModbusCoordinator:
    hass = MagicMock()
    hass.async_add_executor_job = None
    return ThesslaGreenModbusCoordinator.from_params(
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
# Group A — _utcnow behavior
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Group C — _get_client_method fallback no-op (lines 509-527)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio

async def test_get_client_method_fallback_noop():
    """_get_client_method returns callable no-op when method not found (lines 523-527)."""
    coord = _make_coordinator()
    coord.client = None
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
    coord.client = client
    method = coord._get_client_method("read_holding_registers")
    assert method is expected

async def test_read_coils_transport_raises_when_no_client():
    """_read_coils_transport raises ConnectionException when client=None (lines 680-681)."""
    coord = _make_coordinator()
    coord.client = None
    coord._transport = None

    with pytest.raises(ConnectionException):
        await coord._read_coils_transport(1, 0, count=1)

async def test_read_discrete_inputs_transport_raises_when_no_client():
    """_read_discrete_inputs_transport raises ConnectionException when client=None (lines 697-698)."""
    coord = _make_coordinator()
    coord.client = None
    coord._transport = None

    with pytest.raises(ConnectionException):
        await coord._read_discrete_inputs_transport(1, 0, count=1)

def test_clear_register_failure_with_attribute():
    """_clear_register_failure discards from _failed_registers when attr exists (line 1085)."""
    coord = _make_coordinator()
    coord._failed_registers = {"outside_temperature", "mode"}
    coord._clear_register_failure("outside_temperature")
    assert "outside_temperature" not in coord._failed_registers
    assert "mode" in coord._failed_registers

async def test_read_with_retry_awaitable_returning_none_raises():
    """read_method returns awaitable that resolves to None → raises ModbusException."""
    coord = _make_coordinator()
    coord.retry = 1

    async def read_method(slave_id, addr, *, count, attempt):
        return None

    with pytest.raises(ModbusException):
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

def test_process_register_value_sensor_unavailable_temperature():
    """SENSOR_UNAVAILABLE on a temperature register → returns None."""
    from custom_components.thessla_green_modbus.const import SENSOR_UNAVAILABLE

    coord = _make_coordinator()
    # Use a mock that correctly identifies this as a temperature register.
    mock_def = MagicMock()
    mock_def.is_temperature.return_value = True
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
    from custom_components.thessla_green_modbus.const import (
        SENSOR_UNAVAILABLE,
        SENSOR_UNAVAILABLE_REGISTERS,
    )

    coord = _make_coordinator()
    non_temp_reg = next((r for r in SENSOR_UNAVAILABLE_REGISTERS if "temperature" not in r), None)
    if non_temp_reg is None:
        pytest.skip("No non-temperature register in SENSOR_UNAVAILABLE_REGISTERS")
    # Mock is_temperature()=False so decode doesn't transform value
    mock_def = MagicMock()
    mock_def.is_temperature.return_value = False
    mock_def.enum = None
    mock_def.decode.return_value = 0
    with patch(
        "custom_components.thessla_green_modbus.coordinator.get_register_definition",
        return_value=mock_def,
    ):
        result = coord._process_register_value(non_temp_reg, SENSOR_UNAVAILABLE)
    assert result == SENSOR_UNAVAILABLE

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
    """Single-value write when _transport is not None uses transport.write_register."""
    coord = _make_coordinator()
    coord._ensure_connection = AsyncMock()
    ok_response = MagicMock()
    ok_response.isError.return_value = False
    transport = MagicMock()
    transport.is_connected.return_value = True
    transport.write_register = AsyncMock(return_value=ok_response)
    coord._transport = transport
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
    transport.write_register = AsyncMock(return_value=error_response)
    coord._transport = transport

    result = await coord.async_write_register("mode", 1)
    assert result is False

async def test_async_write_register_refresh_type_error():
    """TypeError during refresh is silently caught; write still returns True."""
    coord = _make_coordinator()
    coord._ensure_connection = AsyncMock()
    ok_response = MagicMock()
    ok_response.isError.return_value = False
    transport = MagicMock()
    transport.is_connected.return_value = True
    transport.write_register = AsyncMock(return_value=ok_response)
    coord._transport = transport
    coord.async_request_refresh = AsyncMock(side_effect=TypeError("mock ctx"))

    result = await coord.async_write_register("mode", 1, refresh=True)
    assert result is True

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

def test_process_register_value_decoded_equals_sensor_unavailable():
    """When decode() returns SENSOR_UNAVAILABLE, the function returns SENSOR_UNAVAILABLE (lines 1831-1838)."""
    from custom_components.thessla_green_modbus import _coordinator_register_processing as rp
    from custom_components.thessla_green_modbus.const import SENSOR_UNAVAILABLE

    coord = _make_coordinator()
    mock_def = MagicMock()
    mock_def.is_temperature.return_value = False
    mock_def.enum = None
    mock_def.decode.return_value = SENSOR_UNAVAILABLE  # decoded == SENSOR_UNAVAILABLE
    with patch.object(rp, "get_register_definitions", return_value={"mode": mock_def}):
        result = coord._process_register_value("mode", 1)
    assert result == SENSOR_UNAVAILABLE

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

def test_create_consecutive_groups_empty():
    """Empty registers dict returns [] (line 1931)."""
    from custom_components.thessla_green_modbus._coordinator_register_processing import (
        create_consecutive_groups,
    )

    result = create_consecutive_groups({})
    assert result == []

def test_process_register_value_unknown_register():
    """Unknown register name raises KeyError internally → returns False (lines 1810-1812)."""
    coord = _make_coordinator()
    result = coord._process_register_value("definitely_not_a_real_register_xyz", 42)
    assert result is False

async def test_call_modbus_no_client_raises():
    """_call_modbus with no transport and no client raises ConnectionException (line 486)."""
    coord = _make_coordinator()
    coord._transport = None
    coord.client = None

    async def dummy(*args, **kwargs):
        return None

    with pytest.raises(ConnectionException):
        await coord._call_modbus(dummy, 100, count=1)

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

async def test_read_coils_transport_returns_result():
    """_read_coils_transport calls _call_modbus (line 682)."""
    coord = _make_coordinator()
    ok_resp = MagicMock()
    coord.client = MagicMock()
    coord._call_modbus = AsyncMock(return_value=ok_resp)
    result = await coord._read_coils_transport(1, 100, count=1)
    assert result == ok_resp

async def test_read_discrete_inputs_transport_returns_result():
    """_read_discrete_inputs_transport calls _call_modbus (line 699)."""
    coord = _make_coordinator()
    ok_resp = MagicMock()
    coord.client = MagicMock()
    coord._call_modbus = AsyncMock(return_value=ok_resp)
    result = await coord._read_discrete_inputs_transport(1, 100, count=1)
    assert result == ok_resp

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
    transport.write_registers = AsyncMock(return_value=ok_resp)
    coord._transport = transport
    coord.async_request_refresh = AsyncMock()
    with patch(
        "custom_components.thessla_green_modbus.coordinator.get_register_definition",
        return_value=mock_def,
    ):
        result = await coord.async_write_register("some_reg", 5, offset=1)
    assert result is True

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
    """TCP single request via transport (lines 2217-2222)."""
    coord = _make_coordinator()
    coord._ensure_connection = AsyncMock()
    transport = MagicMock()
    transport.is_connected.return_value = True
    ok_resp = MagicMock()
    ok_resp.isError.return_value = False
    transport.write_registers = AsyncMock(return_value=ok_resp)
    coord._transport = transport
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
    transport.write_registers = AsyncMock(return_value=err_resp)
    coord._transport = transport
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
    coord.client = client
    coord.async_request_refresh = AsyncMock()
    result = await coord.async_write_registers(100, [1, 2])
    assert result is True

async def test_async_write_registers_refresh_type_error():
    """TypeError in refresh → still True (lines 2314-2317)."""
    coord = _make_coordinator()
    coord._ensure_connection = AsyncMock()
    coord._transport = None
    client = MagicMock()
    ok_resp = MagicMock()
    ok_resp.isError.return_value = False
    client.write_registers = AsyncMock(return_value=ok_resp)
    coord.client = client
    coord.async_request_refresh = AsyncMock(side_effect=TypeError("mock ctx"))
    result = await coord.async_write_registers(100, [1, 2], refresh=True)
    assert result is True

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
    transport.write_registers = AsyncMock(return_value=ok_resp)
    coord._transport = transport
    coord.async_request_refresh = AsyncMock()
    with patch(
        "custom_components.thessla_green_modbus.coordinator.get_register_definition",
        return_value=mock_def,
    ):
        result = await coord.async_write_register("some_reg", 5, offset=0)
    assert result is True
