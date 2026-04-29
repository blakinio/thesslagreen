"""Entity creation and behavior tests for optimized integration."""

import logging
from unittest.mock import AsyncMock, MagicMock, call

import pytest
from custom_components.thessla_green_modbus.const import (
    coil_registers,
    discrete_input_registers,
    holding_registers,
    input_registers,
)


class TestThesslaGreenClimate:
    @pytest.fixture
    def mock_climate_coordinator(self):
        coordinator = MagicMock()
        coordinator.host = "192.168.1.100"
        coordinator.slave_id = 10
        coordinator.device_scan_result = {"device_info": {"device_name": "Test AirPack", "firmware": "4.85.0"}}
        coordinator.available_registers = {"holding_registers": {"mode", "on_off_panel_mode", "air_flow_rate_manual"}}
        coordinator.data = {"on_off_panel_mode": 1, "mode": 0, "supply_temperature": 22.0, "supply_percentage": 50, "air_flow_rate_manual": 60, "special_mode": 0}
        coordinator.async_write_register = AsyncMock(return_value=True)
        coordinator._register_maps = {"input_registers": input_registers(), "holding_registers": holding_registers(), "coil_registers": coil_registers(), "discrete_inputs": discrete_input_registers()}
        coordinator.async_request_refresh = AsyncMock()
        return coordinator

    @pytest.mark.asyncio
    async def test_climate_entity_creation(self, mock_climate_coordinator):
        from custom_components.thessla_green_modbus.climate import ThesslaGreenClimate
        from homeassistant.components.climate import HVACMode

        climate = ThesslaGreenClimate(mock_climate_coordinator)
        assert climate.name == "Test AirPack Rekuperator"
        assert HVACMode.AUTO in climate.hvac_modes
        assert HVACMode.FAN_ONLY in climate.hvac_modes
        assert HVACMode.OFF in climate.hvac_modes
        assert climate.hvac_mode == HVACMode.AUTO

    @pytest.mark.asyncio
    async def test_climate_set_hvac_mode(self, mock_climate_coordinator):
        from custom_components.thessla_green_modbus.climate import ThesslaGreenClimate
        from homeassistant.components.climate import HVACMode

        climate = ThesslaGreenClimate(mock_climate_coordinator)
        await climate.async_set_hvac_mode(HVACMode.FAN_ONLY)
        mock_climate_coordinator.async_write_register.assert_has_calls([call("on_off_panel_mode", 1, refresh=False, offset=0), call("mode", 1, refresh=False, offset=0)])
        assert mock_climate_coordinator.async_write_register.call_count == 2
        mock_climate_coordinator.async_request_refresh.assert_called_once()

    @pytest.mark.asyncio
    async def test_climate_set_hvac_mode_enable_failed(self, mock_climate_coordinator, caplog):
        from custom_components.thessla_green_modbus.climate import ThesslaGreenClimate
        from homeassistant.components.climate import HVACMode

        climate = ThesslaGreenClimate(mock_climate_coordinator)
        mock_climate_coordinator.async_write_register = AsyncMock(side_effect=[False, False])

        with caplog.at_level(logging.ERROR):
            await climate.async_set_hvac_mode(HVACMode.FAN_ONLY)

        mock_climate_coordinator.async_write_register.assert_has_calls([call("on_off_panel_mode", 1, refresh=False, offset=0), call("on_off_panel_mode", 1, refresh=False, offset=0)])
        assert mock_climate_coordinator.async_write_register.call_count == 2
        mock_climate_coordinator.async_request_refresh.assert_not_called()
        assert "Failed to enable device" in caplog.text

    @pytest.mark.asyncio
    async def test_climate_set_preset_mode(self, mock_climate_coordinator):
        from custom_components.thessla_green_modbus.climate import ThesslaGreenClimate
        from homeassistant.components.climate import PRESET_ECO

        climate = ThesslaGreenClimate(mock_climate_coordinator)
        await climate.async_set_preset_mode(PRESET_ECO)
        assert mock_climate_coordinator.async_write_register.call_count >= 2

    def test_climate_fan_mode_calculation(self, mock_climate_coordinator):
        from custom_components.thessla_green_modbus.climate import ThesslaGreenClimate

        climate = ThesslaGreenClimate(mock_climate_coordinator)
        mock_climate_coordinator.data["mode"] = 1
        mock_climate_coordinator.data["air_flow_rate_manual"] = 65
        assert climate.fan_mode == "70%"

    def test_climate_fan_mode_no_data(self, mock_climate_coordinator):
        from custom_components.thessla_green_modbus.climate import ThesslaGreenClimate

        climate = ThesslaGreenClimate(mock_climate_coordinator)
        mock_climate_coordinator.data.pop("air_flow_rate_manual", None)
        mock_climate_coordinator.data.pop("air_flow_rate_temporary_2", None)
        assert climate.fan_mode is None

    def test_climate_fan_mode_zero_airflow(self, mock_climate_coordinator):
        from custom_components.thessla_green_modbus.climate import ThesslaGreenClimate

        climate = ThesslaGreenClimate(mock_climate_coordinator)
        mock_climate_coordinator.data["air_flow_rate_manual"] = 0
        assert climate.fan_mode is None
