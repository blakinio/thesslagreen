"""Tests for ThesslaGreen coordinator utilities."""

import asyncio
import os
import sys
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# Ensure repository root is on path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from custom_components.thessla_green_modbus.coordinator import (
    ThesslaGreenDataCoordinator,
)


@pytest.mark.asyncio
async def test_async_write_invalid_register():
    """Return False and do not refresh on unknown register."""
    hass = MagicMock()
    coordinator = ThesslaGreenDataCoordinator(hass, "localhost", 502, 1)
    coordinator.async_request_refresh = AsyncMock()

    result = await coordinator.async_write_register("invalid", 1)

    assert result is False
    coordinator.async_request_refresh.assert_not_awaited()


@pytest.mark.asyncio
async def test_async_write_success_triggers_refresh():
    """Ensure a successful write triggers a refresh request."""
    hass = MagicMock()
    coordinator = ThesslaGreenDataCoordinator(hass, "localhost", 502, 1)

    with patch(
        "custom_components.thessla_green_modbus.coordinator.ModbusTcpClient"
    ) as mock_client_cls:
        client = MagicMock()
        client.connect.return_value = True
        response = MagicMock()
        response.isError.return_value = False
        client.write_register.return_value = response
        mock_client_cls.return_value = client

        coordinator.async_request_refresh = AsyncMock()

        result = await coordinator.async_write_register("mode", 1)

    assert result is True
    coordinator.async_request_refresh.assert_awaited_once()
