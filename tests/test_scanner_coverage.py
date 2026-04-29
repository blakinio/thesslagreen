"""Targeted coverage tests for scanner_core.py uncovered lines."""

import asyncio
import logging
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from custom_components.thessla_green_modbus.const import CONNECTION_TYPE_RTU
from custom_components.thessla_green_modbus.modbus_exceptions import (
    ConnectionException,
    ModbusException,
    ModbusIOException,
)
from custom_components.thessla_green_modbus.scanner.core import (
    ThesslaGreenDeviceScanner,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_ok_response(registers):
    """Return a mock Modbus register response."""
    resp = MagicMock()
    resp.isError.return_value = False
    resp.registers = list(registers)
    return resp


def _make_bit_response(bits):
    """Return a mock Modbus bit response."""
    resp = MagicMock()
    resp.isError.return_value = False
    resp.bits = list(bits)
    return resp


def _make_error_response(code=2):
    resp = MagicMock()
    resp.isError.return_value = True
    resp.exception_code = code
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
# Group A/B: module-level init & _maybe_retry_yield early return
# ---------------------------------------------------------------------------


def test_build_register_maps_direct():
    """Build register maps via scanner register-map runtime module."""
    from custom_components.thessla_green_modbus.scanner.register_map_runtime import (
        build_register_maps,
    )

    build_register_maps()
    from custom_components.thessla_green_modbus.scanner.core import REGISTER_DEFINITIONS

    assert isinstance(REGISTER_DEFINITIONS, dict)


@pytest.mark.asyncio
async def test_maybe_retry_yield_backoff_positive():
    """Cover line 145: backoff > 0 causes early return without sleeping."""
    from custom_components.thessla_green_modbus.scanner.io_runtime import maybe_retry_yield

    with patch("asyncio.sleep", AsyncMock()) as mock_sleep:
        # backoff > 0 → early return, no sleep
        await maybe_retry_yield(backoff=0.1, attempt=0, retry=3)
        mock_sleep.assert_not_called()


@pytest.mark.asyncio
async def test_call_modbus_with_fallback_type_error_reraise():
    """Cover line 182: TypeError with non-'unexpected keyword' message is re-raised."""
    from custom_components.thessla_green_modbus.scanner.io_runtime import call_modbus_with_fallback

    async def raise_other_type_error(*args, **kwargs):
        raise TypeError("something unrelated to keyword")

    with pytest.raises(TypeError, match="something unrelated"):
        await call_modbus_with_fallback(
            raise_other_type_error,
            MagicMock(),
            1,
            0,
            count=1,
            attempt=1,
            retry=1,
            timeout=5,
            backoff=0.0,
            backoff_jitter=None,
        )


# ---------------------------------------------------------------------------
# Group E: Parameter coercion in __init__ (lines 446-501)
# ---------------------------------------------------------------------------
























# ---------------------------------------------------------------------------
# Group F: close() exception handling (lines 686-687, 697-698)
# ---------------------------------------------------------------------------










# ---------------------------------------------------------------------------
# Group G: verify_connection safe holding registers (lines 824-829)
# ---------------------------------------------------------------------------




# ---------------------------------------------------------------------------
# Group H: verify_connection exception paths (lines 844-865)
# ---------------------------------------------------------------------------










# ---------------------------------------------------------------------------
# Group I: _is_valid_register_value BCD time (lines 889, 897)
# ---------------------------------------------------------------------------








# ---------------------------------------------------------------------------
# Group J: safe_scan=True forces single-register batches (line 994)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_scan_raises_without_transport_and_client():
    """Lines 1027-1028: transport=None and client=None raises ConnectionException."""
    scanner = await _make_scanner()
    scanner._transport = None
    scanner._client = None
    with pytest.raises(ConnectionException, match="Transport not connected"):
        await scanner.scan()


@pytest.mark.asyncio
async def test_scan_raises_when_transport_disconnected_and_no_client():
    """Lines 1029-1030: transport not connected and client=None raises."""
    scanner = await _make_scanner()
    mock_transport = MagicMock()
    mock_transport.is_connected.return_value = False
    scanner._transport = mock_transport
    scanner._client = None
    with pytest.raises(ConnectionException, match="Transport not connected"):
        await scanner.scan()


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


@pytest.mark.asyncio
async def test_read_holding_skips_when_failures_exceed_retry():
    """Lines 2158-2161: When failures >= retry, skip register immediately."""
    scanner = await _make_scanner(retry=2)
    scanner._holding_failures[10] = 2  # equals retry
    mock_client = AsyncMock()

    with patch(
        "custom_components.thessla_green_modbus.scanner.io_core._call_modbus",
        AsyncMock(),
    ) as mock_call:
        result = await scanner._read_holding(mock_client, 10, 1)

    assert result is None
    mock_call.assert_not_called()


# ---------------------------------------------------------------------------
# Group AB: Holding success clears failure counter (line 2217)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_read_holding_success_clears_failure_counter():
    """Line 2217: Successful read removes address from _holding_failures."""
    scanner = await _make_scanner(retry=3)
    scanner._holding_failures[5] = 1  # partial failure
    mock_client = AsyncMock()

    ok_resp = _make_ok_response([42])
    with (
        patch(
            "custom_components.thessla_green_modbus.scanner.io_core._call_modbus",
            AsyncMock(return_value=ok_resp),
        ),
        patch("asyncio.sleep", AsyncMock()),
    ):
        result = await scanner._read_holding(mock_client, 5, 1)

    assert result == [42]
    assert 5 not in scanner._holding_failures


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


# ---------------------------------------------------------------------------
# Scan() tests — minimal infrastructure
# ---------------------------------------------------------------------------


def _ok_input_block(count):
    """Return a list of zeros for firmware reads."""
    return [0] * count


async def _run_minimal_scan(
    scanner, *, input_return=None, holding_return=None, coil_return=None, discrete_return=None
):
    """Run scan() with all reads mocked."""
    with (
        patch.object(scanner, "_read_input_block", AsyncMock(return_value=_ok_input_block(30))),
        patch.object(scanner, "_read_holding_block", AsyncMock(return_value=[])),
        patch.object(scanner, "_read_input", AsyncMock(return_value=input_return)),
        patch.object(scanner, "_read_holding", AsyncMock(return_value=holding_return)),
        patch.object(scanner, "_read_coil", AsyncMock(return_value=coil_return)),
        patch.object(scanner, "_read_discrete", AsyncMock(return_value=discrete_return)),
    ):
        return await scanner.scan()


# ---------------------------------------------------------------------------
# Group O: Normal scan batch failure recovery (lines 1302-1341)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_scan_device_rtu_no_serial_port_raises():
    """Line 1669-1670: scan_device with RTU and no serial_port raises."""
    scanner = await _make_scanner(connection_type=CONNECTION_TYPE_RTU)
    scanner.serial_port = ""

    with pytest.raises(ConnectionException, match="Serial port not configured"):
        await scanner.scan_device()


@pytest.mark.asyncio
async def test_scan_device_rtu_creates_transport():
    """Lines 1671-1684: scan_device with RTU creates RtuModbusTransport."""
    scanner = await _make_scanner(connection_type=CONNECTION_TYPE_RTU, serial_port="/dev/ttyUSB0")

    mock_client = AsyncMock()
    mock_transport = _make_transport()
    mock_transport.ensure_connected = AsyncMock()
    mock_transport.client = mock_client

    with (
        patch(
            "custom_components.thessla_green_modbus.scanner.core.RtuModbusTransport",
            return_value=mock_transport,
        ) as mock_rtu,
        patch.object(scanner, "_read_input_block", AsyncMock(return_value=[])),
        patch.object(scanner, "_read_holding_block", AsyncMock(return_value=[])),
        patch.object(scanner, "_read_input", AsyncMock(return_value=None)),
        patch.object(scanner, "_read_holding", AsyncMock(return_value=None)),
        patch.object(scanner, "_read_coil", AsyncMock(return_value=None)),
        patch.object(scanner, "_read_discrete", AsyncMock(return_value=None)),
    ):
        result = await scanner.scan_device()

    mock_rtu.assert_called_once()
    assert "available_registers" in result


# ---------------------------------------------------------------------------
# Group T: Auto-detect mode all attempts fail (lines 1721-1724)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_scan_device_auto_detect_all_fail():
    """Lines 1721-1724: all auto-detect attempts fail → ConnectionException."""
    scanner = await _make_scanner(connection_mode="auto")

    failing_transport = MagicMock()
    failing_transport.ensure_connected = AsyncMock(side_effect=ConnectionException("no"))
    failing_transport.close = AsyncMock()

    with (
        patch.object(
            scanner,
            "_build_auto_tcp_attempts",
            return_value=[
                ("tcp", failing_transport, 1.0),
            ],
        ),
        pytest.raises(ConnectionException, match="Auto-detect Modbus transport failed"),
    ):
        await scanner.scan_device()


# ---------------------------------------------------------------------------
# Group R: scan_device non-dict return path
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_scan_device_scan_returns_non_dict_raises():
    """scan() returning non-dict should raise TypeError."""
    scanner = await _make_scanner()

    # Patch scan at class level with a regular coroutine function so that
    # scan_method.__func__ IS ThesslaGreenDeviceScanner.scan (bypassing first branch).
    # scan() returns non-dict → TypeError.
    async def fake_scan(self_arg):
        return "not_a_dict"

    with patch.object(ThesslaGreenDeviceScanner, "scan", fake_scan):
        with patch.object(scanner, "close", AsyncMock()):
            with pytest.raises(TypeError, match="scan\\(\\) must return a dict"):
                await scanner.scan_device()


# ===========================================================================
# Pass 12 — remaining uncovered lines
# ===========================================================================

# ---------------------------------------------------------------------------
# Lines 473-474: max_registers_per_request ValueError fallback
# ---------------------------------------------------------------------------




# ---------------------------------------------------------------------------
# Lines 697-698: close() catches exception from async_maybe_await_close
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_close_client_async_maybe_await_raises():
    """Lines 697-698: async_maybe_await_close raises → caught and logged."""
    scanner = await _make_scanner()
    scanner._transport = None
    scanner._client = AsyncMock()

    with patch(
        "custom_components.thessla_green_modbus.scanner.core.async_maybe_await_close",
        AsyncMock(side_effect=OSError("async close failed")),
    ):
        # Should not propagate
        await scanner.close()

    assert scanner._client is None


# ---------------------------------------------------------------------------
# Lines 262: _ensure_register_maps rebuilds on hash mismatch
# ---------------------------------------------------------------------------


def test_ensure_register_maps_rebuilds_on_hash_mismatch():
    """register_map_runtime.ensure_register_maps should rebuild mismatched cache hash."""
    import custom_components.thessla_green_modbus.scanner.register_map_cache as cache
    from custom_components.thessla_green_modbus.scanner.register_map_runtime import (
        ensure_register_maps,
    )

    original_hash = cache.REGISTER_HASH
    try:
        cache.REGISTER_HASH = "stale_hash"
        updated_hash = ensure_register_maps("stale_hash")
        assert updated_hash != "stale_hash"
    finally:
        cache.REGISTER_HASH = original_hash


# ---------------------------------------------------------------------------
# Lines 1217, 1221-1222: full_register_scan input no-alias and invalid value
# ---------------------------------------------------------------------------


def _sized_read_mock(value=1):
    """Return an AsyncMock that returns count-sized lists."""

    async def _mock(*args, **kw):
        # Last positional int arg is count
        count = 1
        for a in reversed(args):
            if isinstance(a, int):
                count = a
                break
        return [value] * count

    return _mock


@pytest.mark.asyncio
async def test_scan_device_legacy_returns_dict():
    """Line 1634: overridden scan() returns a plain dict → cast and return."""
    scanner = await _make_scanner()

    async def fake_scan_returns_dict():
        return {"custom_key": "custom_value"}

    # Patch scan on instance (triggers first branch since __func__ != class method)
    scanner.scan = fake_scan_returns_dict  # type: ignore[method-assign]

    with patch.object(scanner, "close", AsyncMock()):
        result = await scanner.scan_device()

    assert result == {"custom_key": "custom_value"}


# ---------------------------------------------------------------------------
# Lines 1643-1644: importlib.import_module raises → legacy_ctor = None
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_scan_device_importlib_fails():
    """scan_device should continue via transport path when setup probes fail."""
    scanner = await _make_scanner()
    mock_transport = _make_transport()
    mock_transport.client = AsyncMock()

    with (
        patch.object(scanner, "_build_tcp_transport", return_value=mock_transport),
        patch.object(scanner, "_read_input_block", AsyncMock(return_value=[])),
        patch.object(scanner, "_read_holding_block", AsyncMock(return_value=[])),
        patch.object(scanner, "_read_input", AsyncMock(return_value=None)),
        patch.object(scanner, "_read_holding", AsyncMock(return_value=None)),
        patch.object(scanner, "_read_coil", AsyncMock(return_value=None)),
        patch.object(scanner, "_read_discrete", AsyncMock(return_value=None)),
    ):
        result = await scanner.scan_device()

    assert "available_registers" in result


# ---------------------------------------------------------------------------
# Lines 1701, 1703-1704: auto-detect probe TimeoutError / ModbusIOException
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_scan_device_auto_detect_probe_timeout():
    """Lines 1700-1701: read_input_registers raises TimeoutError → re-raised → retry next."""
    scanner = await _make_scanner(connection_mode="auto")

    # First transport: ensure_connected ok, but probe raises TimeoutError
    t1 = MagicMock()
    t1.ensure_connected = AsyncMock()
    t1.read_input_registers = AsyncMock(side_effect=TimeoutError("probe timeout"))
    t1.close = AsyncMock()

    # Second transport: fully ok
    t2 = _make_transport()
    t2.client = AsyncMock()

    with (
        patch.object(
            scanner,
            "_build_auto_tcp_attempts",
            return_value=[("tcp", t1, 1.0), ("tcp_rtu", t2, 1.0)],
        ),
        patch.object(scanner, "_read_input_block", AsyncMock(return_value=[])),
        patch.object(scanner, "_read_holding_block", AsyncMock(return_value=[])),
        patch.object(scanner, "_read_input", AsyncMock(return_value=None)),
        patch.object(scanner, "_read_holding", AsyncMock(return_value=None)),
        patch.object(scanner, "_read_coil", AsyncMock(return_value=None)),
        patch.object(scanner, "_read_discrete", AsyncMock(return_value=None)),
    ):
        result = await scanner.scan_device()

    assert "available_registers" in result


@pytest.mark.asyncio
async def test_scan_device_auto_detect_probe_modbus_io_cancelled():
    """Lines 1703-1704: ModbusIOException with 'cancelled' → TimeoutError → retry next."""
    scanner = await _make_scanner(connection_mode="auto")

    cancelled_exc = ModbusIOException("Request cancelled outside pymodbus")
    t1 = MagicMock()
    t1.ensure_connected = AsyncMock()
    t1.read_input_registers = AsyncMock(side_effect=cancelled_exc)
    t1.close = AsyncMock()

    t2 = _make_transport()
    t2.client = AsyncMock()

    with (
        patch.object(
            scanner,
            "_build_auto_tcp_attempts",
            return_value=[("tcp", t1, 1.0), ("tcp_rtu", t2, 1.0)],
        ),
        patch.object(scanner, "_read_input_block", AsyncMock(return_value=[])),
        patch.object(scanner, "_read_holding_block", AsyncMock(return_value=[])),
        patch.object(scanner, "_read_input", AsyncMock(return_value=None)),
        patch.object(scanner, "_read_holding", AsyncMock(return_value=None)),
        patch.object(scanner, "_read_coil", AsyncMock(return_value=None)),
        patch.object(scanner, "_read_discrete", AsyncMock(return_value=None)),
    ):
        result = await scanner.scan_device()

    assert "available_registers" in result


# ---------------------------------------------------------------------------
# Line 1738: scan_device main path scan() returns non-dict
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_scan_device_main_scan_non_dict_raises():
    """Line 1738: scan_device main path — scan() returns non-dict → TypeError."""
    scanner = await _make_scanner()

    async def fake_scan_non_dict(self_arg):
        return "not_a_dict"

    mock_transport = _make_transport()
    mock_transport.client = AsyncMock()

    with patch.object(ThesslaGreenDeviceScanner, "scan", fake_scan_non_dict):
        with patch.object(scanner, "_build_tcp_transport", return_value=mock_transport):
            with patch.object(scanner, "close", AsyncMock()):
                with pytest.raises(TypeError, match="scan\\(\\) must return a dict"):
                    await scanner.scan_device()


# ---------------------------------------------------------------------------
# Lines 1754, 1757: _load_registers populates register_ranges for min/max regs
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_load_registers_with_min_max():
    """Lines 1754-1757: registers with min/max populate _register_ranges."""
    from unittest.mock import MagicMock

    scanner = await _make_scanner()

    reg = MagicMock()
    reg.name = "test_reg_with_range"
    reg.function = 3
    reg.address = 9999
    reg.min = 0
    reg.max = 100

    with patch(
        "custom_components.thessla_green_modbus.scanner.core.async_get_all_registers",
        AsyncMock(return_value=[reg]),
    ):
        result = await scanner._load_registers()

    _register_map, register_ranges = result
    assert "test_reg_with_range" in register_ranges
    assert register_ranges["test_reg_with_range"] == (0, 100)


# ---------------------------------------------------------------------------
# Lines 1921, 1923: _read_input client fallback from self._client
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_read_input_client_fallback_from_self():
    """Line 1921: two-arg _read_input with _transport=None → uses self._client."""
    scanner = await _make_scanner(retry=1)
    scanner._transport = None
    mock_client = AsyncMock()
    scanner._client = mock_client

    ok_resp = _make_ok_response([88])
    with (
        patch(
            "custom_components.thessla_green_modbus.scanner.io_core._call_modbus",
            AsyncMock(return_value=ok_resp),
        ),
    ):
        result = await scanner._read_input(5, 1)

    assert result == [88]


@pytest.mark.asyncio
async def test_read_input_no_transport_no_client_raises():
    """Line 1923: _read_input with no transport and no client raises."""
    scanner = await _make_scanner()
    scanner._transport = None
    scanner._client = None

    with pytest.raises(ConnectionException, match="Modbus transport is not connected"):
        await scanner._read_input(5, 1)


# ---------------------------------------------------------------------------
# Lines 2064-2066: _read_input_block int start with explicit count
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_read_input_block_int_start_explicit_count():
    """Lines 2064-2066: _read_input_block(int, count, count) — int path."""
    scanner = await _make_scanner(retry=1)
    mock_transport = _make_transport(input_response=_make_ok_response([5]))
    scanner._transport = mock_transport
    scanner._client = None

    result = await scanner._read_input_block(0, 1, 1)
    assert result == [5]


# ---------------------------------------------------------------------------
# Lines 2094-2100: _read_holding_block int start with explicit count
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_read_holding_block_int_start_explicit_count():
    """Lines 2094-2100: _read_holding_block(int, count, count) — int path."""
    scanner = await _make_scanner(retry=1)
    mock_transport = _make_transport(holding_response=_make_ok_response([7]))
    scanner._transport = mock_transport
    scanner._client = None

    result = await scanner._read_holding_block(0, 1, 1)
    assert result == [7]


# ---------------------------------------------------------------------------
# Line 2110: _read_holding_block returns None when chunk returns None
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_read_holding_block_returns_none_on_chunk_fail():
    """Line 2110: _read_holding_block returns None when any chunk fails."""
    scanner = await _make_scanner(retry=1)
    mock_client = AsyncMock()
    scanner._client = mock_client
    scanner._transport = None

    with patch.object(scanner, "_read_holding", AsyncMock(return_value=None)):
        result = await scanner._read_holding_block(mock_client, 0, 1)

    assert result is None


# ---------------------------------------------------------------------------
# Lines 2165, 2167: _read_holding client fallback from self._client
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_read_holding_client_fallback_from_self():
    """Line 2165: two-arg _read_holding with _transport=None → uses self._client."""
    scanner = await _make_scanner(retry=1)
    scanner._transport = None
    mock_client = AsyncMock()
    scanner._client = mock_client

    ok_resp = _make_ok_response([77])
    with (
        patch(
            "custom_components.thessla_green_modbus.scanner.io_core._call_modbus",
            AsyncMock(return_value=ok_resp),
        ),
    ):
        result = await scanner._read_holding(5, 1)

    assert result == [77]


@pytest.mark.asyncio
async def test_read_holding_no_transport_no_client_raises():
    """Line 2167: _read_holding with no transport and no client raises."""
    scanner = await _make_scanner()
    scanner._transport = None
    scanner._client = None

    with pytest.raises(ConnectionException, match="Modbus transport is not connected"):
        await scanner._read_holding(5, 1)


# ---------------------------------------------------------------------------
# Lines 1848: _mark_holding_unsupported partial overlap (end+1 to exist_end)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_mark_holding_unsupported_partial_overlap():
    """Line 1848: new range partially overlaps existing range (right side)."""
    scanner = await _make_scanner()
    # Add existing range (0, 10)
    scanner._unsupported_holding_ranges[(0, 10)] = 2
    # Add new overlapping range (5, 8) — exists_start(0) < start(5) → line 1846 NOT hit
    # end(8) < exist_end(10) → line 1848 hit: add (9, 10)
    scanner._mark_holding_unsupported(5, 8, 3)
    assert (9, 10) in scanner._unsupported_holding_ranges
    assert (5, 8) in scanner._unsupported_holding_ranges


# ---------------------------------------------------------------------------
# Lines 119-120: ensure_pymodbus_client_module except branch
# ---------------------------------------------------------------------------


def test_ensure_pymodbus_import_fails():
    """Lines 119-120: except Exception: return when importlib raises."""
    from custom_components.thessla_green_modbus.scanner.io_runtime import (
        attach_pymodbus_client_module,
    )

    with patch(
        "custom_components.thessla_green_modbus.scanner.io_runtime.importlib.import_module",
        side_effect=ImportError("no pymodbus"),
    ):
        # Must not raise
        attach_pymodbus_client_module()


# ---------------------------------------------------------------------------
# Line 501: stop_bits clamped to DEFAULT_STOP_BITS when map returns invalid
# ---------------------------------------------------------------------------




# ---------------------------------------------------------------------------
# Line 581: _update_known_missing_addresses continue when name not in mapping
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_update_known_missing_name_not_in_mapping():
    """Line 581: continue when register name is not in the global mapping."""
    scanner = await _make_scanner()
    with patch(
        "custom_components.thessla_green_modbus.scanner.core.KNOWN_MISSING_REGISTERS",
        {
            "input_registers": {"nonexistent_reg_zzz_xyz"},
            "holding_registers": set(),
            "coil_registers": set(),
            "discrete_inputs": set(),
        },
    ):
        scanner._update_known_missing_addresses()
    # nonexistent register not in INPUT_REGISTERS → continue, nothing added
    assert isinstance(scanner._known_missing_addresses, set)


# ---------------------------------------------------------------------------
# Lines 594-595: _async_setup else branch when _load_registers returns plain dict
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_async_setup_load_registers_returns_plain_dict():
    """Lines 594-595: _async_setup when _load_registers returns a plain dict (not tuple)."""
    scanner = await _make_scanner()
    plain_dict = {3: {0: "test_reg"}, 4: {}, 1: {}, 2: {}}

    with (
        patch(
            "custom_components.thessla_green_modbus.scanner.setup.async_ensure_register_maps",
            AsyncMock(),
        ),
        patch.object(scanner, "_load_registers", AsyncMock(return_value=plain_dict)),
    ):
        await scanner._async_setup()

    assert scanner._registers == plain_dict
    assert scanner._register_ranges == {}


# ---------------------------------------------------------------------------
# Lines 795-796: verify_connection else (TCP explicit mode) path
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_verify_connection_tcp_explicit_mode():
    """Lines 795-796: else branch in verify_connection with connection_mode=tcp."""
    from custom_components.thessla_green_modbus.const import CONNECTION_MODE_TCP

    scanner = await _make_scanner(connection_mode=CONNECTION_MODE_TCP)
    fake_transport = _make_transport(ensure_side_effect=asyncio.CancelledError())

    with patch.object(scanner, "_build_tcp_transport", return_value=fake_transport):
        with pytest.raises(asyncio.CancelledError):
            await scanner.verify_connection()

    fake_transport.ensure_connected.assert_called_once()


# ---------------------------------------------------------------------------
# Lines 766, 824-829: verify_connection safe_holding non-empty
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_verify_connection_safe_holding_with_patched_definitions():
    """Lines 766, 824-829: safe_holding populated when REGISTER_DEFINITIONS has holding reg."""
    from custom_components.thessla_green_modbus.scanner.core import (
        REGISTER_DEFINITIONS,
        SAFE_REGISTERS,
    )

    # Find the holding SAFE_REGISTER name
    holding_name = next((name for func, name in SAFE_REGISTERS if func == 3), None)
    if holding_name is None:
        pytest.skip("No holding register in SAFE_REGISTERS")

    # Create mock register definition with a safe address
    mock_reg = MagicMock()
    mock_reg.address = 9998

    scanner = await _make_scanner()
    fake_transport = _make_transport()

    patched_defs = dict(REGISTER_DEFINITIONS)
    patched_defs[holding_name] = mock_reg

    with (
        patch.object(
            scanner,
            "_build_auto_tcp_attempts",
            return_value=[("tcp", fake_transport, scanner.timeout)],
        ),
        patch(
            "custom_components.thessla_green_modbus.scanner.core.REGISTER_DEFINITIONS",
            patched_defs,
        ),
    ):
        await scanner.verify_connection()

    fake_transport.read_holding_registers.assert_called()


# ---------------------------------------------------------------------------
# Lines 770-776: verify_connection RTU path with serial_port set
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_verify_connection_rtu_no_serial_port_raises():
    """Line 771: RTU path in verify_connection raises when serial_port is empty."""
    scanner = await _make_scanner(connection_type=CONNECTION_TYPE_RTU, serial_port="")

    with pytest.raises(ConnectionException, match="Serial port not configured"):
        await scanner.verify_connection()


@pytest.mark.asyncio
async def test_verify_connection_rtu_with_serial_port():
    """Lines 770, 772-776: RTU path in verify_connection creates RtuModbusTransport."""
    scanner = await _make_scanner(
        connection_type=CONNECTION_TYPE_RTU,
        serial_port="/dev/ttyUSB0",
    )
    fake_transport = _make_transport(ensure_side_effect=asyncio.CancelledError())

    with (
        patch(
            "custom_components.thessla_green_modbus.scanner.core.RtuModbusTransport",
            return_value=fake_transport,
        ),
        pytest.raises(asyncio.CancelledError),
    ):
        await scanner.verify_connection()


# ---------------------------------------------------------------------------
# Lines 1271, 1275: full_register_scan coil alias path and unknown address
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_full_register_scan_discrete_unknown_addr():
    """Line 1296: full_register_scan discrete with address not in _registers[2]."""
    scanner = await _make_scanner(full_register_scan=True, retry=1)
    scanner._client = AsyncMock()
    # discrete_max=2, only addr=2 is registered; addrs 0,1 are unknown
    scanner._registers = {4: {}, 3: {}, 1: {}, 2: {2: "fake_discrete"}}
    scanner._names_by_address[2] = {2: {"fake_discrete"}}

    async def discrete_mock(*args, **kw):
        count = 1
        for a in reversed(args):
            if isinstance(a, int):
                count = a
                break
        return [True] * count

    with (
        patch.object(scanner, "_read_input_block", AsyncMock(return_value=[])),
        patch.object(scanner, "_read_holding_block", AsyncMock(return_value=[])),
        patch.object(scanner, "_read_input", AsyncMock(return_value=None)),
        patch.object(scanner, "_read_holding", AsyncMock(return_value=None)),
        patch.object(scanner, "_read_coil", AsyncMock(return_value=None)),
        patch.object(scanner, "_read_discrete", side_effect=discrete_mock),
    ):
        result = await scanner.scan()

    assert 0 in result["unknown_registers"]["discrete_inputs"]


# ---------------------------------------------------------------------------
# Lines 1339-1340: input probe returns invalid value (fixed mock)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_scan_input_probe_returns_invalid_value_v2():
    """Lines 1339-1340: batch fails, probe returns 65535 (invalid) — fixed mock."""
    scanner = await _make_scanner(retry=1)
    scanner._client = AsyncMock()
    scanner._registers = {4: {9999: "fake_input"}, 3: {}, 1: {}, 2: {}}
    scanner._names_by_address[4] = {9999: {"fake_input"}}

    async def smart_read_input(*args, **kwargs):
        skip_cache = kwargs.get("skip_cache", False)
        # Determine address from args
        addr = None
        if len(args) >= 2:
            # Could be (client, addr, count) or (addr, count)
            for a in args:
                if isinstance(a, int):
                    addr = a
                    break
        # Firmware registers are at low addresses; only intercept addr=9999
        if addr == 9999:
            if not skip_cache:
                # This is the batch read — fail it
                return None
            else:
                # This is the probe — return invalid value
                return [65535]
        # All other reads (firmware fallback) return None
        return None

    with (
        patch.object(scanner, "_read_input_block", AsyncMock(return_value=[])),
        patch.object(scanner, "_read_holding_block", AsyncMock(return_value=[])),
        patch.object(scanner, "_read_input", side_effect=smart_read_input),
        patch.object(scanner, "_read_holding", AsyncMock(return_value=None)),
        patch.object(scanner, "_read_coil", AsyncMock(return_value=None)),
        patch.object(scanner, "_read_discrete", AsyncMock(return_value=None)),
    ):
        result = await scanner.scan()

    assert 9999 in result["failed_addresses"]["invalid_values"]["input_registers"]


# ---------------------------------------------------------------------------
# Line 1754: _load_registers continue when reg.name is empty
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_load_registers_empty_name():
    """Line 1754: _load_registers skips registers with empty name."""
    scanner = await _make_scanner()

    reg_empty = MagicMock()
    reg_empty.name = ""
    reg_empty.function = 3
    reg_empty.address = 9999
    reg_empty.min = None
    reg_empty.max = None

    reg_valid = MagicMock()
    reg_valid.name = "valid_reg"
    reg_valid.function = 4
    reg_valid.address = 100
    reg_valid.min = None
    reg_valid.max = None

    with patch(
        "custom_components.thessla_green_modbus.scanner.core.async_get_all_registers",
        AsyncMock(return_value=[reg_empty, reg_valid]),
    ):
        result = await scanner._load_registers()

    register_map, _register_ranges = result
    # Empty name register skipped, valid one added
    assert 9999 not in register_map[3]
    assert 100 in register_map[4]


# ---------------------------------------------------------------------------
# Line 1824: _mark_input_supported partial range overlap
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_mark_input_supported_partial_range():
    """Line 1824: _mark_input_supported splits range when start < address."""
    scanner = await _make_scanner()
    # Add existing range (0, 10)
    scanner._unsupported_input_ranges[(0, 10)] = 2
    # Mark address=5 as supported: should create (0,4) and (6,10)
    scanner._mark_input_supported(5)
    assert (0, 4) in scanner._unsupported_input_ranges
    assert (6, 10) in scanner._unsupported_input_ranges
    assert (0, 10) not in scanner._unsupported_input_ranges


# ---------------------------------------------------------------------------
# Lines 2404-2405: coil transport reconnect ensure_connected raises
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_read_coil_transport_reconnect_ensure_raises():
    """Lines 2404-2405: except Exception: pass when ensure_connected raises."""
    scanner = await _make_scanner(retry=2)
    mock_transport = MagicMock()
    mock_transport.ensure_connected = AsyncMock(side_effect=OSError("reconnect fail"))
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
    ):
        result = await scanner._read_coil(mock_client, 0, 1)

    # Despite ensure_connected raising, the second attempt succeeds
    assert result == [True]
    mock_transport.ensure_connected.assert_called()


# ---------------------------------------------------------------------------
# Lines 2507-2508: discrete transport reconnect ensure_connected raises
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_read_discrete_transport_reconnect_ensure_raises():
    """Lines 2507-2508: except Exception: pass when ensure_connected raises for discrete."""
    scanner = await _make_scanner(retry=2)
    mock_transport = MagicMock()
    mock_transport.ensure_connected = AsyncMock(side_effect=OSError("reconnect fail"))
    scanner._transport = mock_transport

    mock_client = AsyncMock()
    scanner._client = mock_client

    bit_resp = _make_bit_response([True])
    call_count = {"n": 0}

    async def call_side_effect(*args, **kwargs):
        call_count["n"] += 1
        if call_count["n"] == 1:
            raise ModbusException("connection lost")
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
