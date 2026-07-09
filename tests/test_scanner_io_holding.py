"""Split scanner I/O coverage tests."""

import asyncio
import logging
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from custom_components.thessla_green_modbus.scanner.core import ThesslaGreenDeviceScanner

from .helpers_scanner import _make_ok_response


async def _make_scanner(**kwargs):
    return await ThesslaGreenDeviceScanner.create("192.168.1.1", 502, 1, **kwargs)


def _make_transport(
    *, raises_on_close=None, ensure_side_effect=None, input_response=None, holding_response=None
):
    t = MagicMock()
    if raises_on_close:
        t.close = AsyncMock(side_effect=raises_on_close)
    else:
        t.close = AsyncMock()
    if ensure_side_effect:
        t.ensure_connected = AsyncMock(side_effect=ensure_side_effect)
    else:
        t.ensure_connected = AsyncMock()
    t.read_input_registers = AsyncMock(return_value=input_response or _make_ok_response([1]))
    t.read_holding_registers = AsyncMock(return_value=holding_response or _make_ok_response([1]))
    t.is_connected = MagicMock(return_value=True)
    return t


async def test_read_holding_two_arg_count_none():
    """Lines 2129-2132: _read_holding(address, count) — count=None path."""
    scanner = await _make_scanner(retry=1)
    mock_transport = _make_transport(holding_response=_make_ok_response([55]))
    scanner._transport = mock_transport
    scanner._client = None

    result = await scanner._read_holding(5, 1)
    assert result == [55]


async def test_read_holding_two_arg_int_address():
    """Lines 2133-2136: _read_holding(int, count, count) — int address path."""
    scanner = await _make_scanner(retry=1)
    mock_transport = _make_transport(holding_response=_make_ok_response([77]))
    scanner._transport = mock_transport
    scanner._client = None

    result = await scanner._read_holding(5, 1, 1)
    assert result == [77]


async def test_read_holding_cancelled_error_reraises():
    """Lines 2286-2293: asyncio.CancelledError is re-raised."""
    scanner = await _make_scanner(retry=1)
    mock_client = AsyncMock()

    with (
        patch(
            "custom_components.thessla_green_modbus.scanner.io_core._call_modbus",
            AsyncMock(side_effect=asyncio.CancelledError()),
        ),
        patch("asyncio.sleep", AsyncMock()),
        pytest.raises(asyncio.CancelledError),
    ):
        await scanner._read_holding(mock_client, 0, 1)


async def test_read_holding_oserror_breaks(caplog):
    """Lines 2294-2302: OSError breaks retry loop."""
    scanner = await _make_scanner(retry=2)
    mock_client = AsyncMock()

    with (
        patch(
            "custom_components.thessla_green_modbus.scanner.io_core._call_modbus",
            AsyncMock(side_effect=OSError("broken pipe")),
        ),
        patch("asyncio.sleep", AsyncMock()),
        caplog.at_level(logging.ERROR),
    ):
        result = await scanner._read_holding(mock_client, 0, 1)

    assert result is None
    assert "Unexpected error reading holding" in caplog.text
