import asyncio
import time
from unittest.mock import MagicMock, patch

import pytest

from custom_components.thessla_green_modbus.device_registry import ThesslaGreenDeviceScanner
from custom_components.thessla_green_modbus.coordinator import ThesslaGreenCoordinator


@pytest.mark.asyncio
async def test_device_scanner_non_blocking():
    """Ensure scanner uses executor and doesn't block event loop."""
    scanner = ThesslaGreenDeviceScanner("localhost", 502, 1)

    def slow_scan():
        time.sleep(0.1)
        return {}

    with patch.object(scanner, "_scan_device_sync", side_effect=slow_scan):
        task = asyncio.create_task(scanner.scan_device())
        await asyncio.sleep(0.01)
        assert not task.done()
        await task


@pytest.mark.asyncio
async def test_coordinator_update_non_blocking():
    """Ensure coordinator updates run in executor without blocking."""
    hass = MagicMock()
    coordinator = ThesslaGreenCoordinator(hass, "localhost", 502, 1, 30, 10, 3)

    def slow_update():
        time.sleep(0.1)
        return {}

    with patch.object(coordinator, "_update_data_sync", side_effect=slow_update):
        task = asyncio.create_task(coordinator._async_update_data())
        await asyncio.sleep(0.01)
        assert not task.done()
        await task
