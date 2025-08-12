"""Test integration setup for ThesslaGreen Modbus integration."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PORT

from custom_components.thessla_green_modbus import async_setup_entry, async_unload_entry
from custom_components.thessla_green_modbus.const import DOMAIN


async def test_async_setup_entry_success():
    """Test successful setup entry."""
    hass = MagicMock()
    hass.data = {}
    hass.config_entries.async_forward_entry_setups = AsyncMock()
    
    entry = MagicMock(spec=ConfigEntry)
    entry.entry_id = "test_entry"
    entry.data = {
        CONF_HOST: "192.168.1.100",
        CONF_PORT: 502,
        "slave_id": 10,
    }
    entry.options = {}
    entry.add_update_listener = MagicMock()
    entry.async_on_unload = MagicMock()
    
    with patch(
        "custom_components.thessla_green_modbus.coordinator.ThesslaGreenModbusCoordinator"
    ) as mock_coordinator_class:
        mock_coordinator = MagicMock()
        mock_coordinator.async_config_entry_first_refresh = AsyncMock()
        mock_coordinator_class.return_value = mock_coordinator
        
        result = await async_setup_entry(hass, entry)
        
        assert result is True
        assert DOMAIN in hass.data
        assert entry.entry_id in hass.data[DOMAIN]
        hass.config_entries.async_forward_entry_setups.assert_called_once()


async def test_async_setup_entry_failure():
    """Test setup entry with coordinator failure."""
    hass = MagicMock()
    hass.data = {}
    
    entry = MagicMock(spec=ConfigEntry)
    entry.entry_id = "test_entry"
    entry.data = {
        CONF_HOST: "192.168.1.100",
        CONF_PORT: 502,
        "slave_id": 10,
    }
    entry.options = {}
    
    with patch(
        "custom_components.thessla_green_modbus.coordinator.ThesslaGreenModbusCoordinator"
    ) as mock_coordinator_class:
        mock_coordinator = MagicMock()
        mock_coordinator.async_config_entry_first_refresh = AsyncMock(
            side_effect=Exception("Connection failed")
        )
        mock_coordinator_class.return_value = mock_coordinator
        
        with pytest.raises(ConfigEntryNotReady):
            await async_setup_entry(hass, entry)


async def test_async_unload_entry_success():
    """Test successful unload entry."""
    hass = MagicMock()
    hass.data = {DOMAIN: {"test_entry": MagicMock()}}
    hass.config_entries.async_unload_platforms = AsyncMock(return_value=True)
    
    entry = MagicMock(spec=ConfigEntry)
    entry.entry_id = "test_entry"
    
    # Mock coordinator with shutdown method
    mock_coordinator = MagicMock()
    mock_coordinator.async_shutdown = AsyncMock()
    hass.data[DOMAIN]["test_entry"] = mock_coordinator
    
    result = await async_unload_entry(hass, entry)
    
    assert result is True
    hass.config_entries.async_unload_platforms.assert_called_once()
    mock_coordinator.async_shutdown.assert_called_once()


async def test_async_unload_entry_failure():
    """Test unload entry with platform unload failure."""
    hass = MagicMock()
    hass.data = {DOMAIN: {"test_entry": MagicMock()}}
    hass.config_entries.async_unload_platforms = AsyncMock(return_value=False)
    
    entry = MagicMock(spec=ConfigEntry)
    entry.entry_id = "test_entry"
    
    result = await async_unload_entry(hass, entry)
    
    assert result is False
    hass.config_entries.async_unload_platforms.assert_called_once()


async def test_default_values():
    """Test default configuration values."""
    from custom_components.thessla_green_modbus.const import (
        DEFAULT_NAME,
        DEFAULT_PORT,
        DEFAULT_SLAVE_ID,
        DEFAULT_SCAN_INTERVAL,
        DEFAULT_TIMEOUT,
        DEFAULT_RETRY,
    )
    
    assert DEFAULT_NAME == "ThesslaGreen"
    assert DEFAULT_PORT == 502
    assert DEFAULT_SLAVE_ID == 10
    assert DEFAULT_SCAN_INTERVAL == 30
    assert DEFAULT_TIMEOUT == 10
    assert DEFAULT_RETRY == 3


async def test_register_constants():
    """Test that register constants are properly defined."""
    from custom_components.thessla_green_modbus.const import (
        COIL_REGISTERS,
        DISCRETE_INPUTS,
        INPUT_REGISTERS,
        HOLDING_REGISTERS,
    )
    
    # Test that key registers are defined
    assert "power_supply_fans" in COIL_REGISTERS
    assert "outside_temperature" in INPUT_REGISTERS
    assert "mode" in HOLDING_REGISTERS
    assert "expansion" in DISCRETE_INPUTS
    
    # Test address ranges
    assert COIL_REGISTERS["power_supply_fans"] == 0x000B
    assert INPUT_REGISTERS["outside_temperature"] == 0x0010
    assert HOLDING_REGISTERS["mode"] == 0x1070
