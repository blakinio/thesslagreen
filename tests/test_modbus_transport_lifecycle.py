# mypy: ignore-errors
"""Lifecycle tests for transport execute/connect state transitions."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

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
async def test_execute_success_clears_offline():
    t = _make_tcp(offline_state=True)

    async def success():
        return "ok"

    with patch.object(t, "ensure_connected", new=AsyncMock()):
        result = await t._execute(success)

    assert result == "ok"
    assert t.offline_state is False
