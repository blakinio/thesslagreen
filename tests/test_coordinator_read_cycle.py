"""Coordinator read-cycle coverage tests split from test_coordinator_coverage.py."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from custom_components.thessla_green_modbus.coordinator import ThesslaGreenModbusCoordinator
from custom_components.thessla_green_modbus.modbus_exceptions import (
    ConnectionException,
    ModbusException,
    ModbusIOException,
)


def _make_coordinator(**kwargs) -> ThesslaGreenModbusCoordinator:
    hass = MagicMock()
    hass.async_add_executor_job = None
    return ThesslaGreenModbusCoordinator.from_params(
        hass=hass, host="192.168.1.1", port=502, slave_id=1, name="test", scan_interval=30, timeout=3, retry=2, **kwargs
    )


@pytest.mark.asyncio
async def test_read_coils_transport_raises_when_no_client():
    coord = _make_coordinator()
    coord.client = None
    coord._transport = None
    with pytest.raises(ConnectionException):
        await coord._read_coils_transport(1, 0, count=1)


@pytest.mark.asyncio
async def test_read_discrete_inputs_transport_raises_when_no_client():
    coord = _make_coordinator()
    coord.client = None
    coord._transport = None
    with pytest.raises(ConnectionException):
        await coord._read_discrete_inputs_transport(1, 0, count=1)


@pytest.mark.asyncio
async def test_read_with_retry_awaitable_returning_none_raises():
    coord = _make_coordinator()
    coord.retry = 1

    async def read_method(slave_id, addr, *, count, attempt):
        return None

    with pytest.raises(ModbusException):
        await coord._read_with_retry(read_method, 0, 1, register_type="input_registers")


@pytest.mark.asyncio
async def test_read_with_retry_transient_error_raises_modbus_io():
    coord = _make_coordinator()
    coord.retry = 1
    error_response = MagicMock()
    error_response.isError.return_value = True
    error_response.exception_code = 3

    async def read_method(slave_id, addr, *, count, attempt):
        return error_response

    with pytest.raises(ModbusIOException):
        await coord._read_with_retry(read_method, 0, 1, register_type="input_registers")


def test_process_register_value_sensor_unavailable_temperature():
    from custom_components.thessla_green_modbus.const import SENSOR_UNAVAILABLE

    coord = _make_coordinator()
    mock_def = MagicMock()
    mock_def.is_temperature.return_value = True
    mock_def.enum = None
    mock_def.decode.return_value = 0
    with patch("custom_components.thessla_green_modbus.coordinator.get_register_definition", return_value=mock_def):
        result = coord._process_register_value("outside_temperature", SENSOR_UNAVAILABLE)
    assert result is None
