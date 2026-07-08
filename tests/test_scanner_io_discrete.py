"""Split scanner I/O coverage tests."""

import asyncio
import logging
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from custom_components.thessla_green_modbus.scanner.core import ThesslaGreenDeviceScanner
from pymodbus.exceptions import (
    ConnectionException,
    ModbusException,
)

from .helpers_scanner import _make_bit_response, _make_ok_response


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


async def test_read_discrete_two_arg_count_none():
    """Lines 2443-2446: _read_discrete(address, count) — count=None path."""
    scanner = await _make_scanner(retry=1)
    mock_client = AsyncMock()
    scanner._client = mock_client

    bit_resp = _make_bit_response([True])
    with (
        patch(
            "custom_components.thessla_green_modbus.scanner.io_core._call_modbus",
            AsyncMock(return_value=bit_resp),
        ),
    ):
        result = await scanner._read_discrete(0, 1)

    assert result == [True]


async def test_read_discrete_two_arg_int_address():
    """Lines 2447-2450: _read_discrete(int, count, count) — int address path."""
    scanner = await _make_scanner(retry=1)
    mock_client = AsyncMock()
    scanner._client = mock_client

    bit_resp = _make_bit_response([False])
    with (
        patch(
            "custom_components.thessla_green_modbus.scanner.io_core._call_modbus",
            AsyncMock(return_value=bit_resp),
        ),
    ):
        result = await scanner._read_discrete(0, 1, 1)

    assert result == [False]


async def test_read_discrete_no_client_raises():
    """Lines 2455-2456: client=None raises ConnectionException."""
    scanner = await _make_scanner()
    scanner._client = None
    scanner._transport = None

    with pytest.raises(ConnectionException, match="Modbus client is not connected"):
        await scanner._read_discrete(0, 1)


async def test_read_discrete_timeout_error(caplog):
    """Lines 2484-2491: TimeoutError logged."""
    scanner = await _make_scanner(retry=2)
    mock_client = AsyncMock()
    scanner._client = mock_client

    with (
        patch(
            "custom_components.thessla_green_modbus.scanner.io_core._call_modbus",
            AsyncMock(side_effect=TimeoutError("timeout")),
        ),
        patch("asyncio.sleep", AsyncMock()),
        caplog.at_level(logging.WARNING),
    ):
        result = await scanner._read_discrete(mock_client, 0, 1)

    assert result is None
    assert "Timeout reading discrete" in caplog.text


async def test_read_discrete_modbus_exception_with_transport_reconnect():
    """Lines 2492-2508: ModbusException triggers transport ensure_connected."""
    scanner = await _make_scanner(retry=2)
    new_client = AsyncMock()
    mock_transport = MagicMock()
    mock_transport.ensure_connected = AsyncMock()
    mock_transport.client = new_client
    scanner._transport = mock_transport
    mock_client = AsyncMock()
    scanner._client = mock_client

    bit_resp = _make_bit_response([True])
    call_count = {"n": 0}

    async def call_side_effect(*args, **kwargs):
        call_count["n"] += 1
        if call_count["n"] == 1:
            raise ModbusException("fail")
        return bit_resp

    with (
        patch(
            "custom_components.thessla_green_modbus.scanner.io_core._call_modbus",
            side_effect=call_side_effect,
        ),
        patch("asyncio.sleep", AsyncMock()),
    ):
        result = await scanner._read_discrete(mock_client, 0, 1)

    assert result == [True]
    mock_transport.ensure_connected.assert_called()


async def test_read_discrete_cancelled_error_reraises():
    """Lines 2509-2515: asyncio.CancelledError is re-raised."""
    scanner = await _make_scanner(retry=1)
    mock_client = AsyncMock()
    scanner._client = mock_client

    with (
        patch(
            "custom_components.thessla_green_modbus.scanner.io_core._call_modbus",
            AsyncMock(side_effect=asyncio.CancelledError()),
        ),
        pytest.raises(asyncio.CancelledError),
    ):
        await scanner._read_discrete(mock_client, 0, 1)


async def test_read_discrete_oserror_breaks(caplog):
    """Lines 2516-2524: OSError breaks retry loop."""
    scanner = await _make_scanner(retry=2)
    mock_client = AsyncMock()
    scanner._client = mock_client

    with (
        patch(
            "custom_components.thessla_green_modbus.scanner.io_core._call_modbus",
            AsyncMock(side_effect=OSError("network error")),
        ),
        patch("asyncio.sleep", AsyncMock()),
        caplog.at_level(logging.ERROR),
    ):
        result = await scanner._read_discrete(mock_client, 0, 1)

    assert result is None
    assert "Unexpected error reading discrete" in caplog.text
