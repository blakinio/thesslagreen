# mypy: ignore-errors
"""Error-path tests for modbus transport execution helpers."""

from __future__ import annotations

import asyncio
from unittest.mock import MagicMock, patch

import pytest
from custom_components.thessla_green_modbus.const import CONNECTION_TYPE_TCP
from custom_components.thessla_green_modbus.modbus_transport import TcpModbusTransport


def _make_tcp(connection_type=CONNECTION_TYPE_TCP, **kwargs):
    defaults = dict(
        host="127.0.0.1",
        port=502,
        connection_type=connection_type,
        max_retries=1,
        base_backoff=0.0,
        max_backoff=0.0,
        timeout=1.0,
    )
    defaults.update(kwargs)
    return TcpModbusTransport(**defaults)


@pytest.mark.asyncio
async def test_execute_cancelled_suppresses_reset_exception():
    t = _make_tcp()
    t.client = MagicMock()
    t.client.connected = True

    async def failing_reset():
        raise RuntimeError("reset blew up")

    async def cancel_func():
        raise asyncio.CancelledError()

    with patch.object(t, "_reset_connection", side_effect=failing_reset):
        with pytest.raises(asyncio.CancelledError):
            await t._execute(cancel_func)
