from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest


@pytest.mark.asyncio
async def test_disconnect_retry_transportless_restores_client(coordinator):
    """Transport-less retry restores client when disconnect clears it."""
    client = MagicMock()
    dc = coordinator.device_client
    dc.client = client
    dc._transport = None
    dc._disconnect = _disconnect_clear_client(coordinator)
    coordinator._ensure_connection = AsyncMock()

    reconnect_error = await dc._disconnect_and_reconnect_for_retry(
        register_type="input",
        start_address=0,
        attempt=1,
    )

    assert reconnect_error is None
    assert dc.client is client
    coordinator._ensure_connection.assert_not_awaited()


@pytest.mark.asyncio
async def test_disconnect_retry_transportless_returns_disconnect_error(coordinator):
    """Transport-less retry returns disconnect error and skips reconnect."""
    client = MagicMock()
    dc = coordinator.device_client
    dc.client = client
    dc._transport = None
    dc._disconnect = _disconnect_raise_oserror()
    coordinator._ensure_connection = AsyncMock()

    reconnect_error = await dc._disconnect_and_reconnect_for_retry(
        register_type="input",
        start_address=0,
        attempt=1,
    )

    assert isinstance(reconnect_error, OSError)
    coordinator._ensure_connection.assert_not_awaited()


def _disconnect_clear_client(coordinator):
    async def _disconnect() -> None:
        coordinator.device_client.client = None

    return _disconnect


def _disconnect_raise_oserror():
    async def _disconnect() -> None:
        raise OSError("disconnect failed")

    return _disconnect
