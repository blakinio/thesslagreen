# mypy: ignore-errors
"""Cover transport probe I/O errors that must trigger candidate fallback."""

from __future__ import annotations

import logging
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from custom_components.thessla_green_modbus.const import (
    CONNECTION_MODE_TCP,
    CONNECTION_MODE_TCP_RTU,
)
from custom_components.thessla_green_modbus.core.transport_select import select_auto_transport
from pymodbus.exceptions import ModbusIOException


class _ProbeTransport:
    def __init__(self) -> None:
        self.ensure_connected = AsyncMock()
        self.read_holding_registers = AsyncMock(return_value=SimpleNamespace(registers=[1, 2]))
        self.close = AsyncMock()


@pytest.mark.asyncio
async def test_protocol_io_error_rethrows_into_candidate_fallback():
    transports = {
        CONNECTION_MODE_TCP: _ProbeTransport(),
        CONNECTION_MODE_TCP_RTU: _ProbeTransport(),
    }
    transports[CONNECTION_MODE_TCP].read_holding_registers.side_effect = ModbusIOException(
        "short frame"
    )

    transport, mode = await select_auto_transport(
        resolved_connection_mode=None,
        build_tcp_transport=lambda candidate: transports[candidate],
        try_direct_client_connect=AsyncMock(return_value=False),
        port=502,
        timeout=6.0,
        slave_id=1,
        host="192.0.2.10",
        logger=logging.getLogger("tests.quality_scale.transport_error"),
    )

    assert mode == CONNECTION_MODE_TCP_RTU
    assert transport is transports[CONNECTION_MODE_TCP_RTU]
    transports[CONNECTION_MODE_TCP].close.assert_awaited_once()
