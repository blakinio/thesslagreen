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

    assert await coordinator.async_write_registers(100, [1, 2, 3]) is True
    client.write_registers.assert_called_once()


@pytest.mark.asyncio
async def test_async_write_registers_rejects_oversize():
    hass = MagicMock()
    coordinator = ThesslaGreenModbusCoordinator(
        hass=hass,
        host="localhost",
        port=502,
        slave_id=1,
        name="test",
    )
    coordinator._ensure_connection = AsyncMock()

    oversized = list(range(17))
    assert await coordinator.async_write_registers(100, oversized) is False


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
        REG_TEMPORARY_FLOW_START, [2, 55, 1], refresh=True
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
        REG_TEMPORARY_TEMP_START, [2, 21.5, 1], refresh=True
    )
