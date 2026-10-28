"""A plain HA turn_on must not replace the controller's stored target with 50%."""

from unittest.mock import AsyncMock

import pytest
from custom_components.thessla_green_modbus.fan import ThesslaGreenFan
from homeassistant.exceptions import HomeAssistantError


@pytest.mark.asyncio
@pytest.mark.parametrize("mode", [0, 1, 2])
async def test_turn_on_without_percentage_preserves_auto_manual_and_temporary(
    mock_coordinator, mode
):
    mock_coordinator.data.update(
        mode=mode,
        on_off_panel_mode=0,
        air_flow_rate_manual=30,
        air_flow_rate_temporary=80,
        supply_percentage=0,
        exhaust_percentage=0,
    )
    mock_coordinator.async_write_register = AsyncMock(return_value=True)
    mock_coordinator.async_write_temporary_airflow = AsyncMock(return_value=True)
    fan = ThesslaGreenFan(mock_coordinator)

    await fan.async_turn_on()

    writes = mock_coordinator.async_write_register.await_args_list
    assert [call.args for call in writes] == [("on_off_panel_mode", 1)]
    mock_coordinator.async_write_temporary_airflow.assert_not_awaited()
    assert mock_coordinator.data["mode"] == mode
    assert mock_coordinator.data["air_flow_rate_manual"] == 30
    assert mock_coordinator.data["air_flow_rate_temporary"] == 80


@pytest.mark.asyncio
async def test_resume_rejected_power_write_does_not_replace_speed_or_report_on(mock_coordinator):
    mock_coordinator.data.update(mode=2, on_off_panel_mode=0, air_flow_rate_temporary=80)
    mock_coordinator.async_write_register = AsyncMock(return_value=False)
    mock_coordinator.async_write_temporary_airflow = AsyncMock()
    fan = ThesslaGreenFan(mock_coordinator)

    with pytest.raises(HomeAssistantError):
        await fan.async_turn_on()

    assert fan.is_on is False
    assert mock_coordinator.data["air_flow_rate_temporary"] == 80
    mock_coordinator.async_write_temporary_airflow.assert_not_awaited()
