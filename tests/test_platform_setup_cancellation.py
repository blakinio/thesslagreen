"""Tests for cancellation during platform setup."""

import asyncio
import logging
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PORT

from custom_components.thessla_green_modbus import async_setup_entry

pytestmark = pytest.mark.asyncio


async def test_platform_setup_cancellation(caplog):
    """Cancellation during platform setup is logged without errors."""
    hass = MagicMock()
    hass.data = {}
    hass.config_entries.async_forward_entry_setups = AsyncMock(side_effect=asyncio.CancelledError)

    entry = MagicMock(spec=ConfigEntry)
    entry.entry_id = "test_entry"
    entry.data = {
        CONF_HOST: "192.168.3.17",
        CONF_PORT: 8899,
        "slave_id": 10,
    }
    entry.options = {}
    entry.add_update_listener = MagicMock()
    entry.async_on_unload = MagicMock()
    entry.title = "Test Entry"

    with (
        patch(
            "custom_components.thessla_green_modbus.coordinator.ThesslaGreenModbusCoordinator"
        ) as mock_coordinator_class,
        patch(
            "custom_components.thessla_green_modbus.__init__.er.async_get",
            return_value=MagicMock(),
        ),
        patch(
            "custom_components.thessla_green_modbus.__init__.er.async_entries_for_config_entry",
            return_value=[],
            create=True,
        ),
        patch(
            "custom_components.thessla_green_modbus._async_migrate_unique_ids",
            AsyncMock(),
        ),
        caplog.at_level(logging.DEBUG),
    ):
        mock_coordinator = MagicMock()
        mock_coordinator.async_setup = AsyncMock(return_value=True)
        mock_coordinator.async_config_entry_first_refresh = AsyncMock()
        mock_coordinator_class.return_value = mock_coordinator

        with pytest.raises(asyncio.CancelledError):
            await async_setup_entry(hass, entry)

    assert not any(record.levelno >= logging.ERROR for record in caplog.records)
    assert any("cancelled" in record.message.lower() for record in caplog.records)
