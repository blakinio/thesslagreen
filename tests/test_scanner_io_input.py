"""Split scanner I/O coverage tests."""

import logging
from unittest.mock import AsyncMock, MagicMock, patch

from custom_components.thessla_green_modbus.scanner.core import ThesslaGreenDeviceScanner
from pymodbus.exceptions import (
    ModbusIOException,
)


def _make_ok_response(registers):
    resp = MagicMock()
    resp.isError.return_value = False
    resp.registers = list(registers)
    return resp


def _make_bit_response(bits):
    resp = MagicMock()
    resp.isError.return_value = False
    resp.bits = list(bits)
    return resp


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


async def test_read_input_two_arg_count_none(caplog):
    """Lines 1878-1881: _read_input(address, count) — count=None path."""
    scanner = await _make_scanner(retry=1)
    mock_transport = _make_transport(input_response=_make_ok_response([42]))
    scanner._transport = mock_transport
    scanner._client = None

    result = await scanner._read_input(5, 1)
    assert result == [42]


async def test_read_input_two_arg_int_address():
    """Lines 1882-1885: _read_input(int, count, count) — int address path."""
    scanner = await _make_scanner(retry=1)
    mock_transport = _make_transport(input_response=_make_ok_response([99]))
    scanner._transport = mock_transport
    scanner._client = None

    result = await scanner._read_input(5, 1, 1)
    assert result == [99]


async def test_read_input_modbus_io_cancelled(caplog):
    """Lines 1983-1985: ModbusIOException with 'cancelled' aborts."""
    scanner = await _make_scanner(retry=2)
    mock_client = AsyncMock()
    exc = ModbusIOException("Request cancelled outside pymodbus")

    with (
        patch(
            "custom_components.thessla_green_modbus.scanner.io_core._call_modbus",
            AsyncMock(side_effect=exc),
        ),
        patch("asyncio.sleep", AsyncMock()),
        caplog.at_level(logging.WARNING),
    ):
        result = await scanner._read_input(mock_client, 0, 1)

    assert result is None
    assert "Aborted reading input registers" in caplog.text


async def test_read_input_timeout_error(caplog):
    """Lines 1993-2003: TimeoutError aborts and logs warning."""
    scanner = await _make_scanner(retry=2)
    mock_client = AsyncMock()

    with (
        patch(
            "custom_components.thessla_green_modbus.scanner.io_core._call_modbus",
            AsyncMock(side_effect=TimeoutError("timeout")),
        ),
        patch("asyncio.sleep", AsyncMock()),
        caplog.at_level(logging.WARNING),
    ):
        result = await scanner._read_input(mock_client, 0, 1)

    assert result is None
    assert "Aborted reading input registers" in caplog.text


async def test_read_input_oserror(caplog):
    """Lines 2004-2012: OSError causes break, not abort_transiently."""
    scanner = await _make_scanner(retry=2)
    mock_client = AsyncMock()

    with (
        patch(
            "custom_components.thessla_green_modbus.scanner.io_core._call_modbus",
            AsyncMock(side_effect=OSError("connection reset")),
        ),
        patch("asyncio.sleep", AsyncMock()),
        caplog.at_level(logging.ERROR),
    ):
        result = await scanner._read_input(mock_client, 0, 1)

    assert result is None
    # OSError breaks the loop but does NOT set aborted_transiently
    assert "Failed to read input registers" in caplog.text


async def test_read_input_block_no_client():
    """Line 2075: when active_client=None, delegates to _read_input(chunk_start, chunk_count)."""
    scanner = await _make_scanner()
    scanner._client = None
    scanner._transport = None

    with patch.object(scanner, "_read_input", AsyncMock(return_value=[10, 20])) as mock_ri:
        result = await scanner._read_input_block(0, 2)

    assert result == [10, 20]
    # Called with positional args (chunk_start, chunk_count) — no client
    mock_ri.assert_called()
    args = mock_ri.call_args[0]
    assert len(args) == 2  # (chunk_start, chunk_count), no client


async def test_read_input_block_int_start():
    """Lines 2063-2066: int start path."""
    scanner = await _make_scanner()
    mock_transport = _make_transport(input_response=_make_ok_response([5]))
    scanner._transport = mock_transport
    scanner._client = None

    result = await scanner._read_input_block(0, 1)
    assert result == [5]


async def test_read_holding_block_no_client():
    """Lines 2105-2106: when active_client=None, delegates to _read_holding."""
    scanner = await _make_scanner()
    scanner._client = None
    scanner._transport = None

    with patch.object(scanner, "_read_holding", AsyncMock(return_value=[30, 40])) as mock_rh:
        result = await scanner._read_holding_block(0, 2)

    assert result == [30, 40]
    mock_rh.assert_called()
    args = mock_rh.call_args[0]
    assert len(args) == 2  # (chunk_start, chunk_count), no client


async def test_read_holding_block_int_start():
    """Lines 2094-2097: int start path."""
    scanner = await _make_scanner()
    mock_transport = _make_transport(holding_response=_make_ok_response([7]))
    scanner._transport = mock_transport
    scanner._client = None

    result = await scanner._read_holding_block(0, 1)
    assert result == [7]
