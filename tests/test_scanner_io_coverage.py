"""Additional I/O coverage tests for scanner read helpers."""

import asyncio
import logging
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from custom_components.thessla_green_modbus.modbus_exceptions import (
    ConnectionException,
    ModbusException,
    ModbusIOException,
)
from custom_components.thessla_green_modbus.scanner.core import ThesslaGreenDeviceScanner


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


# ---------------------------------------------------------------------------
# Group U: _read_input two-arg forms (lines 1878-1885)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_read_input_two_arg_count_none(caplog):
    """Lines 1878-1881: _read_input(address, count) — count=None path."""
    scanner = await _make_scanner(retry=1)
    mock_transport = _make_transport(input_response=_make_ok_response([42]))
    scanner._transport = mock_transport
    scanner._client = None

    result = await scanner._read_input(5, 1)
    assert result == [42]


@pytest.mark.asyncio
async def test_read_input_two_arg_int_address():
    """Lines 1882-1885: _read_input(int, count, count) — int address path."""
    scanner = await _make_scanner(retry=1)
    mock_transport = _make_transport(input_response=_make_ok_response([99]))
    scanner._transport = mock_transport
    scanner._client = None

    result = await scanner._read_input(5, 1, 1)
    assert result == [99]


# ---------------------------------------------------------------------------
# Group W: _read_input timeout/CancelledError/OSError (lines 1983-2041)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
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


@pytest.mark.asyncio
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


@pytest.mark.asyncio
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


# ---------------------------------------------------------------------------
# Group X: _read_input_block no client path (line 2075)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
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


@pytest.mark.asyncio
async def test_read_input_block_int_start():
    """Lines 2063-2066: int start path."""
    scanner = await _make_scanner()
    mock_transport = _make_transport(input_response=_make_ok_response([5]))
    scanner._transport = mock_transport
    scanner._client = None

    result = await scanner._read_input_block(0, 1)
    assert result == [5]


# ---------------------------------------------------------------------------
# Group Y: _read_holding_block two-arg forms (lines 2090-2106)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
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


@pytest.mark.asyncio
async def test_read_holding_block_int_start():
    """Lines 2094-2097: int start path."""
    scanner = await _make_scanner()
    mock_transport = _make_transport(holding_response=_make_ok_response([7]))
    scanner._transport = mock_transport
    scanner._client = None

    result = await scanner._read_holding_block(0, 1)
    assert result == [7]


# ---------------------------------------------------------------------------
# Group Z: _read_holding two-arg forms (lines 2129-2136)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_read_holding_two_arg_count_none():
    """Lines 2129-2132: _read_holding(address, count) — count=None path."""
    scanner = await _make_scanner(retry=1)
    mock_transport = _make_transport(holding_response=_make_ok_response([55]))
    scanner._transport = mock_transport
    scanner._client = None

    result = await scanner._read_holding(5, 1)
    assert result == [55]


@pytest.mark.asyncio
async def test_read_holding_two_arg_int_address():
    """Lines 2133-2136: _read_holding(int, count, count) — int address path."""
    scanner = await _make_scanner(retry=1)
    mock_transport = _make_transport(holding_response=_make_ok_response([77]))
    scanner._transport = mock_transport
    scanner._client = None

    result = await scanner._read_holding(5, 1, 1)
    assert result == [77]


# ---------------------------------------------------------------------------
# Group AA: Holding failure counter skips (lines 2157-2161)
# ---------------------------------------------------------------------------



# ---------------------------------------------------------------------------
# Group AB: Holding success clears failure counter (line 2217)
# ---------------------------------------------------------------------------



# ---------------------------------------------------------------------------
# Group AC: Holding CancelledError/OSError (lines 2286-2302)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
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


@pytest.mark.asyncio
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


# ---------------------------------------------------------------------------
# Group AD: _read_coil two-arg forms (lines 2340-2347)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_read_coil_two_arg_count_none():
    """Lines 2340-2343: _read_coil(address, count) — count=None path uses self._client."""
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
        result = await scanner._read_coil(0, 1)

    assert result == [True]


@pytest.mark.asyncio
async def test_read_coil_two_arg_int_address():
    """Lines 2344-2347: _read_coil(int, count, count) — int address path."""
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
        result = await scanner._read_coil(0, 1, 1)

    assert result == [False]


# ---------------------------------------------------------------------------
# Group AE: _read_coil client None raises (line 2352-2353)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_read_coil_no_client_raises():
    """Lines 2352-2353: client=None raises ConnectionException."""
    scanner = await _make_scanner()
    scanner._client = None
    scanner._transport = None

    with pytest.raises(ConnectionException, match="Modbus client is not connected"):
        await scanner._read_coil(0, 1)


# ---------------------------------------------------------------------------
# Group AF: _read_coil TimeoutError (lines 2381-2388)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_read_coil_timeout_error(caplog):
    """Lines 2381-2388: TimeoutError logged, retries exhausted → None."""
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
        result = await scanner._read_coil(mock_client, 0, 1)

    assert result is None
    assert "Timeout reading coil" in caplog.text


# ---------------------------------------------------------------------------
# Group AG: _read_coil ModbusException triggers transport reconnect (2389-2405)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_read_coil_modbus_exception_with_transport_reconnect(caplog):
    """Lines 2389-2405: ModbusException triggers transport ensure_connected."""
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

    async def call_modbus_side_effect(*args, **kwargs):
        call_count["n"] += 1
        if call_count["n"] == 1:
            raise ModbusException("connection lost")
        return bit_resp

    with (
        patch(
            "custom_components.thessla_green_modbus.scanner.io_core._call_modbus",
            side_effect=call_modbus_side_effect,
        ),
        patch("asyncio.sleep", AsyncMock()),
        caplog.at_level(logging.DEBUG),
    ):
        result = await scanner._read_coil(mock_client, 0, 1)

    assert result == [True]
    mock_transport.ensure_connected.assert_called()


# ---------------------------------------------------------------------------
# Group AH: _read_coil CancelledError/OSError (lines 2406-2421)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_read_coil_cancelled_error_reraises():
    """Lines 2406-2412: asyncio.CancelledError is re-raised."""
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
        await scanner._read_coil(mock_client, 0, 1)


@pytest.mark.asyncio
async def test_read_coil_oserror_breaks(caplog):
    """Lines 2413-2421: OSError breaks retry loop."""
    scanner = await _make_scanner(retry=2)
    mock_client = AsyncMock()
    scanner._client = mock_client

    with (
        patch(
            "custom_components.thessla_green_modbus.scanner.io_core._call_modbus",
            AsyncMock(side_effect=OSError("broken pipe")),
        ),
        patch("asyncio.sleep", AsyncMock()),
        caplog.at_level(logging.ERROR),
    ):
        result = await scanner._read_coil(mock_client, 0, 1)

    assert result is None
    assert "Unexpected error reading coil" in caplog.text


# ---------------------------------------------------------------------------
# Group AI: _read_discrete two-arg forms (lines 2443-2453)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
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


@pytest.mark.asyncio
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


@pytest.mark.asyncio
async def test_read_discrete_no_client_raises():
    """Lines 2455-2456: client=None raises ConnectionException."""
    scanner = await _make_scanner()
    scanner._client = None
    scanner._transport = None

    with pytest.raises(ConnectionException, match="Modbus client is not connected"):
        await scanner._read_discrete(0, 1)


# ---------------------------------------------------------------------------
# Group AJ: _read_discrete TimeoutError/exceptions (lines 2484-2524)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
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


@pytest.mark.asyncio
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


@pytest.mark.asyncio
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


@pytest.mark.asyncio
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


