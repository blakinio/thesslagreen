from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from custom_components.thessla_green_modbus.coordinator import ThesslaGreenModbusCoordinator
from custom_components.thessla_green_modbus.registers import (
    REG_TEMPORARY_FLOW_START,
    REG_TEMPORARY_TEMP_START,
)


@pytest.mark.asyncio
async def test_async_write_registers_calls_modbus():
    hass = MagicMock()
    coordinator = ThesslaGreenModbusCoordinator(
        hass=hass,
        host="localhost",
        port=502,
        slave_id=1,
        name="test",
    )
    coordinator._ensure_connection = AsyncMock()
    response = MagicMock()
    response.isError.return_value = False
    client = MagicMock()
    client.write_registers = AsyncMock(return_value=response)
    coordinator.client = client
    coordinator._transport = AsyncMock()
    coordinator._transport.call = AsyncMock(return_value=response)

    assert await coordinator.async_write_registers(100, [1, 2, 3]) is True
    coordinator._transport.call.assert_called_once()


@pytest.mark.asyncio
async def test_async_write_registers_chunks_oversize():
    hass = MagicMock()
    coordinator = ThesslaGreenModbusCoordinator(
        hass=hass,
        host="localhost",
        port=502,
        slave_id=1,
        name="test",
    )
    coordinator._ensure_connection = AsyncMock()
    response = MagicMock()
    response.isError.return_value = False
    client = MagicMock()
    client.write_registers = AsyncMock(return_value=response)
    coordinator.client = client
    coordinator._transport = AsyncMock()
    coordinator._transport.call = AsyncMock(return_value=response)

    oversized = list(range(17))
    assert await coordinator.async_write_registers(100, oversized) is True
    assert coordinator._transport.call.await_count == 2


@pytest.mark.asyncio
async def test_async_write_registers_passes_attempt():
    hass = MagicMock()
    coordinator = ThesslaGreenModbusCoordinator(
        hass=hass,
        host="localhost",
        port=502,
        slave_id=1,
        name="test",
        retry=2,
    )
    coordinator._ensure_connection = AsyncMock()
    response_error = MagicMock()
    response_error.isError.return_value = True
    response_ok = MagicMock()
    response_ok.isError.return_value = False
    coordinator.client = MagicMock(connected=True)
    coordinator._transport = AsyncMock()
    coordinator._transport.call = AsyncMock(side_effect=[response_error, response_ok])

    assert await coordinator.async_write_registers(100, [1, 2]) is True
    attempts = [call.kwargs.get("attempt") for call in coordinator._transport.call.await_args_list]
    assert attempts == [1, 2]


@pytest.mark.asyncio
async def test_async_write_registers_single_request_override():
    """Temporary writes should bypass chunking to keep 3-register atomicity."""
    hass = MagicMock()
    coordinator = ThesslaGreenModbusCoordinator(
        hass=hass,
        host="localhost",
        port=502,
        slave_id=1,
        name="test",
    )
    coordinator._ensure_connection = AsyncMock()
    coordinator.effective_batch = 1
    response = MagicMock()
    response.isError.return_value = False
    client = MagicMock(connected=True)
    client.write_registers = AsyncMock(return_value=response)
    coordinator.client = client

    assert (
        await coordinator.async_write_registers(
            REG_TEMPORARY_FLOW_START,
            [1, 2, 3],
            require_single_request=True,
        )
        is True
    )
    client.write_registers.assert_awaited_once_with(
        address=REG_TEMPORARY_FLOW_START,
        values=[1, 2, 3],
    )


@pytest.mark.asyncio
async def test_async_write_temporary_airflow_uses_three_registers(monkeypatch):
    hass = MagicMock()
    coordinator = ThesslaGreenModbusCoordinator(
        hass=hass,
        host="localhost",
        port=502,
        slave_id=1,
        name="test",
    )
    coordinator.async_write_registers = AsyncMock(return_value=True)

    def fake_def(_name):
        return SimpleNamespace(encode=lambda value: value)

    monkeypatch.setattr(
        "custom_components.thessla_green_modbus.coordinator.get_register_definition",
        fake_def,
    )

    assert await coordinator.async_write_temporary_airflow(55) is True
    coordinator.async_write_registers.assert_called_once_with(
        REG_TEMPORARY_FLOW_START,
        [2, 55, 1],
        refresh=True,
        require_single_request=True,
    )


@pytest.mark.asyncio
async def test_async_write_temporary_temperature_uses_three_registers(monkeypatch):
    hass = MagicMock()
    coordinator = ThesslaGreenModbusCoordinator(
        hass=hass,
        host="localhost",
        port=502,
        slave_id=1,
        name="test",
    )
    coordinator.async_write_registers = AsyncMock(return_value=True)

    def fake_def(_name):
        return SimpleNamespace(encode=lambda value: value)

    monkeypatch.setattr(
        "custom_components.thessla_green_modbus.coordinator.get_register_definition",
        fake_def,
    )

    assert await coordinator.async_write_temporary_temperature(21.5) is True
    coordinator.async_write_registers.assert_called_once_with(
        REG_TEMPORARY_TEMP_START,
        [2, 21.5, 1],
        refresh=True,
        require_single_request=True,
    )


@pytest.mark.asyncio
async def test_async_write_temporary_airflow_writes_three_registers(monkeypatch):
    hass = MagicMock()
    coordinator = ThesslaGreenModbusCoordinator(
        hass=hass,
        host="localhost",
        port=502,
        slave_id=1,
        name="test",
    )
    coordinator._ensure_connection = AsyncMock()
    response = MagicMock()
    response.isError.return_value = False
    client = MagicMock(connected=True)
    client.write_registers = AsyncMock(return_value=response)
    coordinator.client = client

    def fake_def(_name):
        return SimpleNamespace(encode=lambda value: value)

    monkeypatch.setattr(
        "custom_components.thessla_green_modbus.coordinator.get_register_definition",
        fake_def,
    )

    assert await coordinator.async_write_temporary_airflow(55) is True
    client.write_registers.assert_awaited_once_with(
        address=REG_TEMPORARY_FLOW_START,
        values=[2, 55, 1],
    )
