"""Service interaction tests for optimized integration."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant


@pytest.mark.asyncio
async def test_services_registration():
    from custom_components.thessla_green_modbus import async_setup_entry

    hass = MagicMock(spec=HomeAssistant)
    hass.data = {}
    hass.async_add_executor_job = AsyncMock(side_effect=lambda func, *a: func(*a))
    hass.config_entries = MagicMock()
    hass.config_entries.async_forward_entry_setups = AsyncMock()
    hass.config_entries.async_unload_platforms = AsyncMock(return_value=True)
    hass.config_entries.async_entries.return_value = [MagicMock()]
    hass.services = MagicMock()
    hass.services.has_service = MagicMock(return_value=False)
    hass.services.async_register = MagicMock()
    hass.services.async_remove = MagicMock()

    entry = MagicMock(spec=ConfigEntry)
    entry.entry_id = "test_entry"
    entry.data = {CONF_HOST: "192.168.1.100", CONF_PORT: 502, "slave_id": 10}
    entry.options = {"scan_interval": 30, "timeout": 10, "retry": 3, "scan_uart_settings": False}
    entry.add_update_listener = MagicMock()
    entry.async_on_unload = MagicMock()

    mock_coordinator = MagicMock()
    mock_coordinator.host = "192.168.1.100"
    mock_coordinator.port = 502
    mock_coordinator.slave_id = 10
    mock_coordinator.last_update_success = True
    mock_coordinator.async_config_entry_first_refresh = AsyncMock()
    mock_coordinator.async_shutdown = AsyncMock()
    mock_coordinator.async_request_refresh = AsyncMock()
    mock_coordinator.async_write_register = AsyncMock(return_value=True)

    with patch("custom_components.thessla_green_modbus.coordinator.ThesslaGreenModbusCoordinator") as mock_coordinator_class:
        mock_coordinator_class.return_value = mock_coordinator
        await async_setup_entry(hass, entry)

        service_calls = hass.services.async_register.call_args_list
        service_names = [call[0][1] for call in service_calls]

        expected_services = ["set_mode", "set_intensity", "set_special_function"]
        for service in expected_services:
            assert service in service_names
