"""Test config entry migrations."""

from unittest.mock import MagicMock

import pytest
from custom_components.thessla_green_modbus import async_migrate_entry
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST


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
async def test_migrate_current_entry_is_noop():
    """Current entries must not have stable identity replaced by endpoint data."""
    hass = MagicMock()
    hass.config_entries.async_update_entry = MagicMock()

    config_entry = MagicMock(spec=ConfigEntry)
    config_entry.version = 4
    config_entry.unique_id = "serial:sn-123"

    result = await async_migrate_entry(hass, config_entry)

    assert result is True
    hass.config_entries.async_update_entry.assert_not_called()
