"""Setup and lifecycle tests for ThesslaGreen Modbus integration."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant


class TestThesslaGreenIntegration:
    """Test the main integration setup and teardown."""

    @pytest.fixture
    def mock_hass(self):
        """Create a mock Home Assistant instance."""
        hass = MagicMock(spec=HomeAssistant)
        hass.data = {}
        hass.async_add_executor_job = AsyncMock(side_effect=lambda func, *a: func(*a))
        hass.config_entries = MagicMock()
        hass.config_entries.async_forward_entry_setups = AsyncMock()
        hass.config_entries.async_unload_platforms = AsyncMock(return_value=True)
        hass.services = MagicMock()
        hass.services.has_service = MagicMock(return_value=False)
        hass.services.async_register = MagicMock()
        hass.services.async_remove = MagicMock()
        hass.config_entries.async_entries.return_value = [MagicMock()]
        return hass

    @pytest.fixture
    def mock_config_entry(self):
        """Create a mock config entry."""
        entry = MagicMock(spec=ConfigEntry)
        entry.entry_id = "test_entry"
        entry.data = {CONF_HOST: "192.168.1.100", CONF_PORT: 502, "slave_id": 10}
        entry.options = {"scan_interval": 30, "timeout": 10, "retry": 3, "scan_uart_settings": False}
        entry.add_update_listener = MagicMock()
        entry.async_on_unload = MagicMock()
        return entry

    @pytest.fixture
    def mock_coordinator(self):
        """Create a mock coordinator with realistic data."""
        coordinator = MagicMock()
        coordinator.async_config_entry_first_refresh = AsyncMock()
        coordinator.async_shutdown = AsyncMock()
        return coordinator

    @pytest.mark.asyncio
    async def test_async_setup_entry_success(self, mock_hass, mock_config_entry, mock_coordinator):
        from custom_components.thessla_green_modbus import async_setup_entry

        with patch("custom_components.thessla_green_modbus.coordinator.ThesslaGreenModbusCoordinator") as mock_coordinator_class:
            mock_coordinator_class.return_value = mock_coordinator
            result = await async_setup_entry(mock_hass, mock_config_entry)

            assert result is True
            assert mock_config_entry.runtime_data is mock_coordinator
            mock_hass.config_entries.async_forward_entry_setups.assert_called_once()
            mock_coordinator.async_config_entry_first_refresh.assert_called_once()

    @pytest.mark.asyncio
    async def test_async_setup_entry_connection_failure(self, mock_hass, mock_config_entry):
        from custom_components.thessla_green_modbus import async_setup_entry

        mock_coordinator = MagicMock()
        mock_coordinator.async_config_entry_first_refresh = AsyncMock(side_effect=Exception("Connection failed"))

        with patch("custom_components.thessla_green_modbus.coordinator.ThesslaGreenModbusCoordinator") as mock_coordinator_class:
            mock_coordinator_class.return_value = mock_coordinator
            import homeassistant.exceptions as _ha_exc

            _ConfigEntryNotReady = _ha_exc.ConfigEntryNotReady
            with pytest.raises(_ConfigEntryNotReady):
                await async_setup_entry(mock_hass, mock_config_entry)

    @pytest.mark.asyncio
    async def test_async_unload_entry_success(self, mock_hass, mock_config_entry, mock_coordinator):
        from custom_components.thessla_green_modbus import async_unload_entry

        mock_config_entry.runtime_data = mock_coordinator
        result = await async_unload_entry(mock_hass, mock_config_entry)

        assert result is True
        mock_hass.config_entries.async_unload_platforms.assert_called_once()
        mock_coordinator.async_shutdown.assert_called_once()


class TestThesslaGreenConfigFlow:
    """Test the configuration flow."""

    @pytest.fixture
    def mock_scanner(self):
        scanner_result = {
            "available_registers": {"input_registers": {"outside_temperature", "supply_temperature"}, "holding_registers": {"mode", "on_off_panel_mode"}},
            "device_info": {"device_name": "ThesslaGreen AirPack Test", "firmware": "4.85.0"},
            "capabilities": {"basic_control": True, "constant_flow": True},
        }

        with patch("custom_components.thessla_green_modbus.scanner.core.ThesslaGreenDeviceScanner.scan_device", return_value=scanner_result):
            yield

    @pytest.mark.asyncio
    async def test_config_flow_user_step(self, mock_scanner):
        from custom_components.thessla_green_modbus.config_flow import ConfigFlow

        flow = ConfigFlow()
        flow.hass = MagicMock()
        result = await flow.async_step_user()
        assert result["type"] == "form"
        assert result["step_id"] == "user"

    @pytest.mark.asyncio
    async def test_config_flow_user_input_success(self, mock_scanner):
        from custom_components.thessla_green_modbus.config_flow import ConfigFlow

        flow = ConfigFlow()
        flow.hass = MagicMock()
        flow.hass.async_add_executor_job = AsyncMock(return_value=MagicMock())

        with (
            patch("custom_components.thessla_green_modbus.config_flow.validate_input", return_value={"title": "ThesslaGreen AirPack Test", "device_info": {"device_name": "ThesslaGreen AirPack Test", "firmware": "4.85.0"}, "scan_result": {}}),
            patch.object(flow, "_prepare_entry_payload", return_value=({}, {})),
            patch.object(flow, "async_set_unique_id"),
            patch.object(flow, "_abort_if_unique_id_configured"),
            patch.object(flow, "async_step_confirm", AsyncMock(return_value={"type": "create_entry", "title": "ThesslaGreen AirPack Test", "data": {}, "options": {}})),
        ):
            result = await flow.async_step_user({CONF_HOST: "192.168.1.100", CONF_PORT: 502, "slave_id": 10})

            assert result["type"] == "create_entry"
            assert "ThesslaGreen AirPack Test" in result["title"]

    @pytest.mark.asyncio
    async def test_config_flow_cannot_connect(self):
        from custom_components.thessla_green_modbus.config_flow import CannotConnect, ConfigFlow

        flow = ConfigFlow()
        flow.hass = MagicMock()

        with patch("custom_components.thessla_green_modbus.config_flow.validate_input", side_effect=CannotConnect):
            result = await flow.async_step_user({CONF_HOST: "192.168.1.100", CONF_PORT: 502, "slave_id": 10})

            assert result["type"] == "form"
            assert result["errors"]["base"] == "cannot_connect"
