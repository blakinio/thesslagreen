"""Tests for coordinator disconnect helper module."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from custom_components.thessla_green_modbus.coordinator import disconnect


@pytest.mark.asyncio
async def test_disconnect_locked_uses_close_client_helper():
    """disconnect_locked delegates client-close branch to helper callback."""
    close_client = AsyncMock()
    mark_disconnected = MagicMock()

    await disconnect.disconnect_locked(
        transport=None,
        client=MagicMock(),
        close_client_connection_fn=close_client,
        mark_connection_disconnected_fn=mark_disconnected,
        logger=MagicMock(),
    )

    close_client.assert_awaited_once()
    mark_disconnected.assert_called_once()


@pytest.mark.asyncio
async def test_close_client_connection_awaits_awaitable_close_result():
    """close_client_connection awaits an awaitable returned from sync close()."""
    client = MagicMock()

    async def _close_coro():
        return None

    client.close = MagicMock(return_value=_close_coro())
    await disconnect.close_client_connection(client=client, logger=MagicMock())
    client.close.assert_called_once()
