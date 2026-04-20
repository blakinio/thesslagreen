"""Test config entry migrations."""

from unittest.mock import MagicMock

import pytest
from custom_components.thessla_green_modbus import async_migrate_entry
from custom_components.thessla_green_modbus.const import CONF_SLAVE_ID
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PORT


@pytest.mark.asyncio
async def test_migrate_entry_v1_returns_false():
    """v1 entries (pre-2021) are no longer supported since 2.5.0."""
    hass = MagicMock()
    hass.config_entries.async_update_entry = MagicMock()

    config_entry = MagicMock(spec=ConfigEntry)
    config_entry.version = 1
    config_entry.data = {CONF_HOST: "192.168.0.10"}
    config_entry.options = {}

    result = await async_migrate_entry(hass, config_entry)

    assert result is False


@pytest.mark.asyncio
async def test_migrate_entry_v2_returns_false():
    """v2 entries are no longer supported since 2.8.0."""
    hass = MagicMock()
    hass.config_entries.async_update_entry = MagicMock()

    config_entry = MagicMock(spec=ConfigEntry)
    config_entry.version = 2
    config_entry.data = {CONF_HOST: "192.168.0.10"}
    config_entry.options = {}

    result = await async_migrate_entry(hass, config_entry)

    assert result is False


@pytest.mark.asyncio
async def test_migrate_entry_v3_returns_false():
    """v3 entries are no longer supported since 2.8.0."""
    hass = MagicMock()
    hass.config_entries.async_update_entry = MagicMock()

    config_entry = MagicMock(spec=ConfigEntry)
    config_entry.version = 3
    config_entry.data = {CONF_HOST: "192.168.0.10"}
    config_entry.options = {}

    result = await async_migrate_entry(hass, config_entry)

    assert result is False


@pytest.mark.asyncio
async def test_migrate_entry_v4_updates_unique_id():
    """v4 migration replaces colons in host for unique_id."""
    hass = MagicMock()
    hass.config_entries.async_update_entry = MagicMock()

    config_entry = MagicMock(spec=ConfigEntry)
    config_entry.version = 4
    config_entry.data = {
        CONF_HOST: "fe80::1",
        CONF_PORT: 1234,
        CONF_SLAVE_ID: 5,
    }
    config_entry.options = {}
    config_entry.unique_id = "fe80::1:1234:5"

    result = await async_migrate_entry(hass, config_entry)

    assert result is True
    assert hass.config_entries.async_update_entry.call_args.kwargs["unique_id"] == "fe80--1:1234:5"
