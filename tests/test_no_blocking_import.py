"""Test that platform imports do not trigger blocking warnings."""

from __future__ import annotations

import logging
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from homeassistant.const import CONF_HOST, CONF_PORT

from custom_components.thessla_green_modbus import async_setup_entry


@pytest.mark.asyncio
async def test_no_blocking_import_log(caplog: pytest.LogCaptureFixture) -> None:
    """Ensure setup does not log blocking import warnings."""
    hass = MagicMock()
    hass.data = {}
    hass.config_entries.async_forward_entry_setups = AsyncMock()

    entry = MagicMock()
    entry.entry_id = "test"
    entry.data = {CONF_HOST: "192.168.1.100", CONF_PORT: 502, "slave_id": 10}
    entry.options = {}
    entry.title = "Test"
    entry.add_update_listener = MagicMock()
    entry.async_on_unload = MagicMock()

    with (
        patch(
            "custom_components.thessla_green_modbus.coordinator.ThesslaGreenModbusCoordinator"
        ) as mock_coord,
        patch("custom_components.thessla_green_modbus.er.async_get"),
        patch(
            "custom_components.thessla_green_modbus.er.async_entries_for_config_entry",
            return_value=[],
            create=True,
        ),
    ):
        mock_coordinator = MagicMock()
        mock_coordinator.async_config_entry_first_refresh = AsyncMock()
        mock_coordinator.async_setup = AsyncMock(return_value=True)
        mock_coord.return_value = mock_coordinator

        with caplog.at_level(logging.WARNING):
            await async_setup_entry(hass, entry)

    assert "blocking call to import_module" not in caplog.text
