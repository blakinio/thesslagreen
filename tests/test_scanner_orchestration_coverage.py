"""Orchestration edge-case coverage tests for scanner core."""

from unittest.mock import MagicMock

import pytest
from custom_components.thessla_green_modbus.modbus_exceptions import ConnectionException
from custom_components.thessla_green_modbus.scanner.core import ThesslaGreenDeviceScanner


async def _make_scanner(**kwargs):
    return await ThesslaGreenDeviceScanner.create("192.168.1.1", 502, 1, **kwargs)


@pytest.mark.asyncio
async def test_scan_raises_without_transport_and_client():
    scanner = await _make_scanner()
    scanner._transport = None
    scanner._client = None
    with pytest.raises(ConnectionException, match="Transport not connected"):
        await scanner.scan()


@pytest.mark.asyncio
async def test_scan_raises_when_transport_disconnected_and_no_client():
    scanner = await _make_scanner()
    mock_transport = MagicMock()
    mock_transport.is_connected.return_value = False
    scanner._transport = mock_transport
    scanner._client = None
    with pytest.raises(ConnectionException, match="Transport not connected"):
        await scanner.scan()
