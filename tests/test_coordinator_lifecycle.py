from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from custom_components.thessla_green_modbus.coordinator import ThesslaGreenModbusCoordinator


def _make_coordinator(**kwargs) -> ThesslaGreenModbusCoordinator:
    hass = MagicMock()
    hass.async_add_executor_job = None
    return ThesslaGreenModbusCoordinator.from_params(
        hass=hass,
        host="192.168.1.1",
        port=502,
        slave_id=1,
        name="test",
        scan_interval=30,
        timeout=3,
        retry=2,
        **kwargs,
    )


@pytest.mark.asyncio
async def test_disconnect_acquires_lock():
    coord = _make_coordinator()
    coord._disconnect_locked = AsyncMock()
    await coord._disconnect()
    coord._disconnect_locked.assert_called_once()


@pytest.mark.asyncio
async def test_async_shutdown_calls_disconnect():
    coord = _make_coordinator()
    coord._disconnect = AsyncMock()
    stop_listener_mock = MagicMock()
    coord._stop_listener = stop_listener_mock

    await coord.async_shutdown()

    stop_listener_mock.assert_called_once()
    assert coord._stop_listener is None
    coord._disconnect.assert_called_once()
