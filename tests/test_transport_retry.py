"""Tests for Modbus transport retry and reconnect logic."""

from unittest.mock import AsyncMock, patch

import pytest

from custom_components.thessla_green_modbus.modbus_exceptions import ModbusIOException
from custom_components.thessla_green_modbus.modbus_transport import BaseModbusTransport


class DummyTransport(BaseModbusTransport):
    """Simple transport to observe reconnect behaviour."""

    def __init__(self) -> None:
        super().__init__(max_retries=2, base_backoff=0, max_backoff=0, timeout=1)
        self._connected = False
        self.connect_calls = 0
        self.reset_calls = 0

    def _is_connected(self) -> bool:
        return self._connected

    async def _connect(self) -> None:
        self.connect_calls += 1
        self._connected = True

    async def _reset_connection(self) -> None:
        self.reset_calls += 1
        self._connected = False


class DummyResponse:
    def isError(self) -> bool:
        return False


@pytest.mark.asyncio
async def test_transport_retries_and_reconnects():
    """Transient failures should trigger retry with reconnect."""
    transport = DummyTransport()
    func = AsyncMock()

    with patch(
        "custom_components.thessla_green_modbus.modbus_transport._call_modbus",
        AsyncMock(side_effect=[ModbusIOException("boom"), DummyResponse()]),
    ) as call_mock:
        response = await transport.call(func, 10)

    assert response is not None
    assert call_mock.await_count == 2
    assert transport.connect_calls == 2
    assert transport.reset_calls >= 1
