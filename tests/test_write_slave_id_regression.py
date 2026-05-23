"""Regression tests: write path must use the configured slave_id, not 1."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from custom_components.thessla_green_modbus.coordinator import (
    ThesslaGreenModbusCoordinator,
)

SLAVE_ID = 10


@pytest.fixture()
def coordinator_slave10():
    """Coordinator with slave_id=10 and a mocked transport."""
    hass = MagicMock()
    coord = ThesslaGreenModbusCoordinator.from_params(
        hass=hass,
        host="192.0.2.1",
        port=502,
        slave_id=SLAVE_ID,
        name="real_device",
        scan_interval=30,
        timeout=10,
        retry=3,
    )
    coord._ensure_connection = AsyncMock()
    coord.async_request_refresh = AsyncMock()
    coord.device_client.available_registers = {
        "holding_registers": {"mode"},
        "input_registers": set(),
        "coil_registers": set(),
        "discrete_inputs": set(),
    }

    response = MagicMock()
    response.isError.return_value = False
    transport = MagicMock()
    transport.is_connected.return_value = True
    transport.write_register = AsyncMock(return_value=response)
    transport.write_registers = AsyncMock(return_value=response)
    coord.device_client._transport = transport

    return coord, transport


@pytest.mark.asyncio
async def test_single_holding_register_write_uses_configured_slave_id(
    coordinator_slave10, monkeypatch
):
    """Regression: write_register must use slave_id=10, not the pymodbus default 1."""
    coordinator, transport = coordinator_slave10

    reg = SimpleNamespace(
        function=3,
        address=0x1070,
        length=1,
        access="rw",
        encode=lambda v: int(v),
    )
    monkeypatch.setattr(
        "custom_components.thessla_green_modbus.coordinator.schedule._get_register_definition",
        lambda _name: reg,
    )

    result = await coordinator.async_write_register("mode", 1)

    assert result is True, "Write should succeed"
    transport.write_register.assert_awaited_once()
    slave_arg = transport.write_register.await_args.args[0]
    assert slave_arg == SLAVE_ID, (
        f"write_register called with slave_id={slave_arg!r}, expected {SLAVE_ID}"
    )


@pytest.mark.asyncio
async def test_multi_register_write_uses_configured_slave_id(coordinator_slave10):
    """Regression: write_registers must use slave_id=10, not the pymodbus default 1."""
    coordinator, transport = coordinator_slave10

    result = await coordinator.async_write_registers(0x1000, [1, 2, 3])

    assert result is True, "Write should succeed"
    transport.write_registers.assert_awaited_once()
    slave_arg = transport.write_registers.await_args.args[0]
    assert slave_arg == SLAVE_ID, (
        f"write_registers called with slave_id={slave_arg!r}, expected {SLAVE_ID}"
    )
