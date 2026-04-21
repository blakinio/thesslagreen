# mypy: ignore-errors
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from tests.platform_stubs import install_fan_stubs

install_fan_stubs()

from custom_components.thessla_green_modbus.coordinator import (
    ThesslaGreenModbusCoordinator,
)
from custom_components.thessla_green_modbus.fan import ThesslaGreenFan


def test_fan_percentage_clamps_to_max():
    hass = SimpleNamespace()
    coordinator = ThesslaGreenModbusCoordinator.from_params(hass, "host", 502, 1, "dev")
    coordinator.data = {"min_percentage": 10, "max_percentage": 150, "air_flow_rate_manual": 160}

    fan = ThesslaGreenFan(coordinator)

    assert fan.percentage == 150


@pytest.mark.asyncio
async def test_fan_set_percentage_clamps_to_limits():
    hass = SimpleNamespace()
    coordinator = ThesslaGreenModbusCoordinator.from_params(hass, "host", 502, 1, "dev")
    coordinator.available_registers["holding_registers"] = {"mode", "air_flow_rate_manual"}
    coordinator.data = {"min_percentage": 30, "max_percentage": 120, "mode": 1}
    coordinator.async_write_register = AsyncMock(return_value=True)
    coordinator.async_request_refresh = AsyncMock()

    fan = ThesslaGreenFan(coordinator)

    await fan.async_set_percentage(10)

    coordinator.async_write_register.assert_any_call("air_flow_rate_manual", 30, refresh=False)
