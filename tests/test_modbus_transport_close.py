from unittest.mock import AsyncMock, MagicMock

import pytest

from custom_components.thessla_green_modbus.const import CONNECTION_TYPE_TCP
from custom_components.thessla_green_modbus.modbus_transport import TcpModbusTransport


@pytest.mark.asyncio
async def test_tcp_reset_connection_handles_sync_close():
    """Ensure reset_connection handles sync close and clears the client."""

    transport = TcpModbusTransport(
        host="127.0.0.1",
        port=502,
        connection_type=CONNECTION_TYPE_TCP,
        max_retries=1,
        base_backoff=0.0,
        max_backoff=0.0,
        timeout=1.0,
    )
    client = MagicMock()
    client.close = MagicMock(return_value=None)
    transport.client = client

    await transport._reset_connection()

    client.close.assert_called_once()
    assert transport.client is None  # nosec B101


@pytest.mark.asyncio
async def test_tcp_reset_connection_handles_async_close():
    """Ensure reset_connection awaits async close and clears the client."""

    transport = TcpModbusTransport(
        host="127.0.0.1",
        port=502,
        connection_type=CONNECTION_TYPE_TCP,
        max_retries=1,
        base_backoff=0.0,
        max_backoff=0.0,
        timeout=1.0,
    )
    client = MagicMock()
    client.close = AsyncMock()
    transport.client = client

    await transport._reset_connection()

    client.close.assert_awaited_once()
    assert transport.client is None  # nosec B101
