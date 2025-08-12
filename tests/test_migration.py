"""Test config entry migrations."""
import pytest
from unittest.mock import MagicMock

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PORT

from custom_components.thessla_green_modbus import async_migrate_entry
from custom_components.thessla_green_modbus.const import CONF_SLAVE_ID


@pytest.mark.asyncio
async def test_migrate_entry_adds_legacy_port():
    """Test migration adds legacy default port when missing."""
    hass = MagicMock()
    hass.config_entries.async_update_entry = MagicMock()

    config_entry = MagicMock(spec=ConfigEntry)
    config_entry.version = 1
    config_entry.data = {CONF_HOST: "192.168.0.10"}
    config_entry.options = {}

    result = await async_migrate_entry(hass, config_entry)

    assert result is True
    new_data = hass.config_entries.async_update_entry.call_args.kwargs["data"]
    assert new_data[CONF_PORT] == 8899
    assert config_entry.version == 2


@pytest.mark.asyncio
async def test_migrate_entry_preserves_existing_port():
    """Test migration keeps existing port value."""
    hass = MagicMock()
    hass.config_entries.async_update_entry = MagicMock()

    config_entry = MagicMock(spec=ConfigEntry)
    config_entry.version = 1
    config_entry.data = {CONF_HOST: "192.168.0.10", CONF_PORT: 1234}
    config_entry.options = {}

    result = await async_migrate_entry(hass, config_entry)

    assert result is True
    new_data = hass.config_entries.async_update_entry.call_args.kwargs["data"]
    assert new_data[CONF_PORT] == 1234
    assert config_entry.version == 2


@pytest.mark.asyncio
async def test_migrate_entry_updates_unique_id():
    """Test migration replaces colons in host for unique_id."""
    hass = MagicMock()
    hass.config_entries.async_update_entry = MagicMock()

    config_entry = MagicMock(spec=ConfigEntry)
    config_entry.version = 2
    config_entry.data = {
        CONF_HOST: "fe80::1",
        CONF_PORT: 1234,
        CONF_SLAVE_ID: 5,
    }
    config_entry.options = {}
    config_entry.unique_id = "fe80::1:1234:5"

    result = await async_migrate_entry(hass, config_entry)

    assert result is True
    assert (
        hass.config_entries.async_update_entry.call_args.kwargs["unique_id"]
        == "fe80--1:1234:5"
    )
