# mypy: ignore-errors
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from custom_components.thessla_green_modbus.coordinator import (
    ThesslaGreenModbusCoordinator,
)
from custom_components.thessla_green_modbus.fan import ThesslaGreenFan


def test_fan_percentage_clamps_to_100():
    """HA FanEntity.percentage must not exceed 100 regardless of device max."""
    hass = SimpleNamespace()
    coordinator = ThesslaGreenModbusCoordinator.from_params(hass, "host", 502, 1, "dev")
    coordinator.data = {"min_percentage": 10, "max_percentage": 150, "air_flow_rate_manual": 160}

    fan = ThesslaGreenFan(coordinator)

    assert fan.percentage == 100


def test_fan_percentage_over_100_device_clamps(mock_coordinator):
    """Real-device finding: device reports supply_percentage=109 with max_percentage=109.

    HA FanEntity.percentage must be clamped to 100.  The raw value is preserved
    in extra_state_attributes['supply_percentage'].
    """
    mock_coordinator.data["min_percentage"] = 10
    mock_coordinator.data["max_percentage"] = 109
    mock_coordinator.data["supply_percentage"] = 109

    fan = ThesslaGreenFan(mock_coordinator)

    assert fan.percentage == 100
    assert fan.extra_state_attributes.get("supply_percentage") == 109


@pytest.mark.asyncio
async def test_fan_set_percentage_clamps_to_limits():
    hass = SimpleNamespace()
    coordinator = ThesslaGreenModbusCoordinator.from_params(hass, "host", 502, 1, "dev")
    coordinator.device_client.available_registers["holding_registers"] = {
        "mode",
        "air_flow_rate_manual",
    }
    coordinator.data = {"min_percentage": 30, "max_percentage": 120, "mode": 1}
    coordinator.async_write_register = AsyncMock(return_value=True)
    coordinator.async_request_refresh = AsyncMock()

    fan = ThesslaGreenFan(coordinator)

    await fan.async_set_percentage(10)

    coordinator.async_write_register.assert_any_call("air_flow_rate_manual", 30, refresh=False)
