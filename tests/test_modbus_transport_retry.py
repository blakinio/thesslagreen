# mypy: ignore-errors
"""Retry and backoff behavior tests for modbus transport."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from custom_components.thessla_green_modbus.const import CONNECTION_TYPE_TCP
from custom_components.thessla_green_modbus.modbus_exceptions import ConnectionException
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
async def test_handle_timeout_sets_offline():
    t = _make_tcp()
    with patch.object(t, "_reset_connection", new=AsyncMock()):
        with patch.object(t, "_apply_backoff", new=AsyncMock()):
            await t._handle_timeout(1, TimeoutError("t"))
    assert t.offline_state is True


@pytest.mark.asyncio
async def test_handle_transient_sets_offline():
    t = _make_tcp()
    with patch.object(t, "_reset_connection", new=AsyncMock()):
        with patch.object(t, "_apply_backoff", new=AsyncMock()):
            await t._handle_transient(1, ConnectionException("c"))
    assert t.offline_state is True


@pytest.mark.asyncio
async def test_apply_backoff_zero():
    t = _make_tcp(base_backoff=0.0)
    with patch("asyncio.sleep", new=AsyncMock()) as mock_sleep:
        await t._apply_backoff(1)
    mock_sleep.assert_not_called()


@pytest.mark.asyncio
async def test_apply_backoff_respects_max():
    t = _make_tcp(base_backoff=10.0, max_backoff=0.01)
    with patch("asyncio.sleep", new=AsyncMock()) as mock_sleep:
        await t._apply_backoff(1)
    mock_sleep.assert_called_once()
    assert mock_sleep.call_args[0][0] <= 0.01
