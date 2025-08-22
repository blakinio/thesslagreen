"""Test integration setup for ThesslaGreen Modbus integration."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.exceptions import ConfigEntryNotReady

from custom_components.thessla_green_modbus import (
    async_setup_entry,
    async_unload_entry,
)
from custom_components.thessla_green_modbus.const import DOMAIN
from custom_components.thessla_green_modbus.registers.loader import (
    get_registers_by_function,
)


async def test_async_setup_entry_success():
    """Test successful setup entry."""
    hass = MagicMock()
    hass.data = {}
    hass.config_entries.async_forward_entry_setups = AsyncMock()

    entry = MagicMock(spec=ConfigEntry)
    entry.entry_id = "test_entry"
    entry.title = "Test"
    entry.data = {
        CONF_HOST: "192.168.1.100",
        CONF_PORT: 502,
        "slave_id": 10,
    }
    entry.options = {}
    entry.title = "Test"
    entry.title = "Test"
    entry.add_update_listener = MagicMock()
    entry.async_on_unload = MagicMock()

    with patch(
        "custom_components.thessla_green_modbus.coordinator.ThesslaGreenModbusCoordinator"
    ) as mock_coordinator_class:
        mock_coordinator = MagicMock()
        mock_coordinator.async_setup = AsyncMock(return_value=True)
        mock_coordinator.async_config_entry_first_refresh = AsyncMock()
        mock_coordinator.async_setup = AsyncMock(return_value=True)
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
    entry.title = "Test"
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
        mock_coordinator.async_setup = AsyncMock(return_value=True)
        mock_coordinator.async_config_entry_first_refresh = AsyncMock(
            side_effect=ConfigEntryNotReady("Connection failed")
        )
        mock_coordinator_class.return_value = mock_coordinator

        with pytest.raises(ConfigEntryNotReady):
            await async_setup_entry(hass, entry)


@pytest.mark.asyncio
async def test_async_setup_entry_custom_port():
    """Test setup entry with a non-default port."""
    hass = MagicMock()
    hass.data = {}
    hass.config_entries.async_forward_entry_setups = AsyncMock()

    entry = MagicMock(spec=ConfigEntry)
    entry.entry_id = "test_entry"
    entry.data = {
        CONF_HOST: "192.168.1.100",
        CONF_PORT: 8899,
        "slave_id": 10,
    }
    entry.options = {}
    entry.title = "Test Entry"
    entry.add_update_listener = MagicMock()
    entry.async_on_unload = MagicMock()

    with patch(
        "custom_components.thessla_green_modbus.coordinator.ThesslaGreenModbusCoordinator"
    ) as mock_coordinator_class:
        mock_coordinator = MagicMock()
        mock_coordinator.async_config_entry_first_refresh = AsyncMock()
        mock_coordinator.async_setup = AsyncMock(return_value=True)
        mock_coordinator_class.return_value = mock_coordinator

        result = await async_setup_entry(hass, entry)

        assert result is True
        assert mock_coordinator_class.call_args.kwargs["port"] == 8899


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
        DEFAULT_RETRY,
        DEFAULT_SCAN_INTERVAL,
        DEFAULT_SLAVE_ID,
        DEFAULT_TIMEOUT,
    )

    assert DEFAULT_NAME == "ThesslaGreen"
    assert DEFAULT_PORT == 502
    assert DEFAULT_SLAVE_ID == 10
    assert DEFAULT_SCAN_INTERVAL == 30
    assert DEFAULT_TIMEOUT == 10
    assert DEFAULT_RETRY == 3


async def test_register_constants():
    """Test that register constants are properly defined."""

    coil = {r.name: r.address for r in get_registers_by_function("01")}
    discrete = {r.name: r.address for r in get_registers_by_function("02")}
    input_regs = {r.name: r.address for r in get_registers_by_function("04")}
    holding = {r.name: r.address for r in get_registers_by_function("03")}

    regs_by_fn = {
        "coil": {r.name: r.address for r in get_registers_by_function("01")},
        "discrete": {r.name: r.address for r in get_registers_by_function("02")},
        "input": {r.name: r.address for r in get_registers_by_function("04")},
        "holding": {r.name: r.address for r in get_registers_by_function("03")},
    }
    coil = regs_by_fn["coil"]
    discrete = regs_by_fn["discrete"]
    input_regs = regs_by_fn["input"]
    holding = regs_by_fn["holding"]

    # Test that key registers are defined
    assert "power_supply_fans" in coil
    assert "outside_temperature" in input_regs
    assert "mode" in holding
    assert "expansion" in discrete

    # Test address ranges
    assert coil["power_supply_fans"] == 11
    assert input_regs["outside_temperature"] == 16
    assert holding["mode"] == 4097
    assert discrete["expansion"] == 0
    # Test that key registers are defined
    assert "power_supply_fans" in coil
    assert "outside_temperature" in input_regs
    assert "mode" in holding
    assert "expansion" in discrete

    # Test address ranges
    assert coil["power_supply_fans"] == 0x000B
    assert input_regs["outside_temperature"] == 0x0010
    assert holding["mode"] == 0x1070


async def test_unload_and_reload_entry():
    """Test unloading and reloading a config entry reinitializes the integration."""
    hass = MagicMock()
    hass.data = {}
    hass.config_entries.async_forward_entry_setups = AsyncMock()
    hass.config_entries.async_unload_platforms = AsyncMock(return_value=True)

    entry = MagicMock(spec=ConfigEntry)
    entry.entry_id = "test_entry"
    entry.data = {
        CONF_HOST: "192.168.1.100",
        CONF_PORT: 502,
        "slave_id": 10,
    }
    entry.options = {}
    entry.title = "Test Entry"
    entry.add_update_listener = MagicMock()
    entry.async_on_unload = MagicMock()

    coordinator1 = MagicMock()
    coordinator1.async_config_entry_first_refresh = AsyncMock()
    coordinator1.async_setup = AsyncMock(return_value=True)
    coordinator1.async_shutdown = AsyncMock()

    coordinator2 = MagicMock()
    coordinator2.async_config_entry_first_refresh = AsyncMock()
    coordinator2.async_setup = AsyncMock(return_value=True)
    coordinator2.async_shutdown = AsyncMock()

    with (
        patch(
            "homeassistant.helpers.entity_registry.async_entries_for_config_entry",
            return_value=[],
            create=True,
        ),
        patch(
            "custom_components.thessla_green_modbus.coordinator.ThesslaGreenModbusCoordinator",
            side_effect=[coordinator1, coordinator2],
        ) as mock_coordinator_class,
        patch(
            "custom_components.thessla_green_modbus.services.async_setup_services",
            AsyncMock(),
        ) as mock_setup_services,
        patch(
            "custom_components.thessla_green_modbus.services.async_unload_services",
            AsyncMock(),
        ) as mock_unload_services,
    ):
        # Initial setup
        assert await async_setup_entry(hass, entry)
        assert hass.data[DOMAIN][entry.entry_id] is coordinator1
        hass.config_entries.async_forward_entry_setups.assert_called_once()
        mock_setup_services.assert_called_once()

        # Unload
        assert await async_unload_entry(hass, entry)
        mock_unload_services.assert_called_once()
        coordinator1.async_shutdown.assert_called_once()
        assert DOMAIN not in hass.data

        # Reset mocks for reload
        hass.config_entries.async_forward_entry_setups.reset_mock()
        mock_setup_services.reset_mock()

        # Reload
        assert await async_setup_entry(hass, entry)
        assert hass.data[DOMAIN][entry.entry_id] is coordinator2
        assert hass.config_entries.async_forward_entry_setups.call_count == 1
        mock_setup_services.assert_called_once()
        assert mock_coordinator_class.call_count == 2
