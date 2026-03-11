"""Targeted coverage tests for scanner_core.py uncovered lines."""

import asyncio
import logging
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from custom_components.thessla_green_modbus.const import (
    CONNECTION_TYPE_RTU,
    DEFAULT_BAUD_RATE,
    DEFAULT_PARITY,
    DEFAULT_STOP_BITS,
    SENSOR_UNAVAILABLE,
)
from custom_components.thessla_green_modbus.modbus_exceptions import (
    ConnectionException,
    ModbusException,
    ModbusIOException,
)
from custom_components.thessla_green_modbus.scanner_core import (
    ThesslaGreenDeviceScanner,
    _build_register_maps,
)

pytestmark = pytest.mark.asyncio


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


def _make_transport(*, raises_on_close=None, ensure_side_effect=None,
                    input_response=None, holding_response=None):
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
    """Call _build_register_maps() directly to cover lines 245-247."""
    _build_register_maps()
    from custom_components.thessla_green_modbus.scanner_core import REGISTER_DEFINITIONS
    assert isinstance(REGISTER_DEFINITIONS, dict)


async def test_maybe_retry_yield_backoff_positive():
    """Cover line 145: backoff > 0 causes early return without sleeping."""
    from custom_components.thessla_green_modbus.scanner_core import _maybe_retry_yield

    with patch("asyncio.sleep", AsyncMock()) as mock_sleep:
        # backoff > 0 → early return, no sleep
        await _maybe_retry_yield(backoff=0.1, attempt=0, retry=3)
        mock_sleep.assert_not_called()


async def test_call_modbus_compat_type_error_reraise():
    """Cover line 182: TypeError with non-'unexpected keyword' message is re-raised."""
    from custom_components.thessla_green_modbus.scanner_core import _call_modbus_compat

    async def raise_other_type_error(*args, **kwargs):
        raise TypeError("something unrelated to keyword")

    with patch(
        "custom_components.thessla_green_modbus.scanner_core._call_modbus",
        side_effect=raise_other_type_error,
    ):
        with pytest.raises(TypeError, match="something unrelated"):
            await _call_modbus_compat(
                MagicMock(), 1, 0,
                count=1, attempt=1, retry=1, timeout=5, backoff=0.0, backoff_jitter=None,
            )


# ---------------------------------------------------------------------------
# Group E: Parameter coercion in __init__ (lines 446-501)
# ---------------------------------------------------------------------------

async def test_param_coerce_backoff_invalid():
    """Lines 446-447: backoff='invalid' falls back to 0.0."""
    scanner = await _make_scanner(backoff="invalid")
    assert scanner.backoff == 0.0


async def test_param_coerce_backoff_jitter_string_valid():
    """Lines 451-452: backoff_jitter='3.14' parsed to float."""
    scanner = await _make_scanner(backoff_jitter="3.14")
    assert scanner.backoff_jitter == pytest.approx(3.14)


async def test_param_coerce_backoff_jitter_string_invalid():
    """Lines 453-454: backoff_jitter='bad' → jitter=None."""
    scanner = await _make_scanner(backoff_jitter="bad")
    assert scanner.backoff_jitter is None


async def test_param_coerce_backoff_jitter_list():
    """Lines 455-458: backoff_jitter=[1.0, 2.0] → tuple."""
    scanner = await _make_scanner(backoff_jitter=[1.0, 2.0])
    assert scanner.backoff_jitter == (1.0, 2.0)


async def test_param_coerce_backoff_jitter_list_invalid():
    """Lines 458-459: backoff_jitter=[None, 'x'] → jitter=None."""
    scanner = await _make_scanner(backoff_jitter=[None, "x"])
    assert scanner.backoff_jitter is None


async def test_param_coerce_backoff_jitter_zero():
    """Lines 462-463: backoff_jitter=0 → jitter=0.0."""
    scanner = await _make_scanner(backoff_jitter=0)
    assert scanner.backoff_jitter == 0.0


async def test_param_coerce_max_registers_string():
    """Lines 472-473: max_registers_per_request='16' parsed to int."""
    scanner = await _make_scanner(max_registers_per_request="16")
    assert scanner.effective_batch == 16


async def test_param_coerce_max_registers_zero():
    """Lines 475-476: max_registers_per_request=0 → effective_batch=1."""
    scanner = await _make_scanner(max_registers_per_request=0)
    assert scanner.effective_batch == 1


async def test_param_coerce_baud_rate_none():
    """Lines 490-491: baud_rate=None → DEFAULT_BAUD_RATE."""
    scanner = await _make_scanner(baud_rate=None)
    assert scanner.baud_rate == DEFAULT_BAUD_RATE


async def test_param_coerce_parity_invalid():
    """Lines 493-494: parity='xyz' → DEFAULT_PARITY."""
    scanner = await _make_scanner(parity="xyz")
    assert scanner.parity == DEFAULT_PARITY.lower()


async def test_param_coerce_stop_bits_invalid():
    """Lines 500-501: stop_bits=99 → DEFAULT_STOP_BITS."""
    scanner = await _make_scanner(stop_bits=99)
    assert scanner.stop_bits == DEFAULT_STOP_BITS


# ---------------------------------------------------------------------------
# Group F: close() exception handling (lines 686-687, 697-698)
# ---------------------------------------------------------------------------

async def test_close_transport_raises_oserror():
    """Lines 686-687: OSError from transport.close() is caught and logged."""
    scanner = await _make_scanner()
    scanner._transport = _make_transport(raises_on_close=OSError("boom"))
    # Should not raise
    await scanner.close()
    assert scanner._transport is None


async def test_close_transport_raises_connection_exception():
    """Lines 686-687: ConnectionException from transport.close() is caught."""
    scanner = await _make_scanner()
    scanner._transport = _make_transport(raises_on_close=ConnectionException("err"))
    await scanner.close()
    assert scanner._transport is None


async def test_close_client_raises_oserror():
    """Lines 697-698: OSError from client.close() is caught and logged."""
    scanner = await _make_scanner()
    scanner._transport = None
    mock_client = MagicMock()
    mock_client.close = MagicMock(side_effect=OSError("client boom"))
    scanner._client = mock_client
    await scanner.close()
    assert scanner._client is None


async def test_close_client_raises_modbus_io_exception():
    """Lines 697-698: ModbusIOException from client.close() is caught."""
    scanner = await _make_scanner()
    scanner._transport = None
    mock_client = MagicMock()
    mock_client.close = MagicMock(side_effect=ModbusIOException("io err"))
    scanner._client = mock_client
    await scanner.close()
    assert scanner._client is None


# ---------------------------------------------------------------------------
# Group G: verify_connection safe holding registers (lines 824-829)
# ---------------------------------------------------------------------------

async def test_verify_connection_safe_holding_registers():
    """Lines 824-829: safe_holding is non-empty when date_time_rrmm is in REGISTER_DEFINITIONS."""
    from custom_components.thessla_green_modbus.scanner_core import REGISTER_DEFINITIONS

    scanner = await _make_scanner()
    # date_time_rrmm is a holding register in SAFE_REGISTERS
    if "date_time_rrmm" not in REGISTER_DEFINITIONS:
        pytest.skip("date_time_rrmm not in REGISTER_DEFINITIONS")

    fake_transport = _make_transport()
    with patch.object(scanner, "_build_tcp_transport", return_value=fake_transport):
        await scanner.verify_connection()

    fake_transport.read_holding_registers.assert_called()


# ---------------------------------------------------------------------------
# Group H: verify_connection exception paths (lines 844-865)
# ---------------------------------------------------------------------------

async def test_verify_connection_cancelled_error_reraises():
    """Line 845: asyncio.CancelledError is re-raised."""
    scanner = await _make_scanner()
    fake_transport = _make_transport(ensure_side_effect=asyncio.CancelledError())
    with patch.object(scanner, "_build_tcp_transport", return_value=fake_transport):
        with pytest.raises(asyncio.CancelledError):
            await scanner.verify_connection()


async def test_verify_connection_modbus_io_cancelled_raises_timeout():
    """Lines 847-850: ModbusIOException with 'cancelled' raises TimeoutError."""
    scanner = await _make_scanner()
    exc = ModbusIOException("Request cancelled outside pymodbus")
    fake_transport = _make_transport(ensure_side_effect=exc)
    with patch.object(scanner, "_build_tcp_transport", return_value=fake_transport):
        with pytest.raises(TimeoutError):
            await scanner.verify_connection()


async def test_verify_connection_timeout_error_logs_warning(caplog):
    """Lines 852-853: TimeoutError logs a warning."""
    scanner = await _make_scanner()
    fake_transport = _make_transport(ensure_side_effect=TimeoutError("timed out"))

    with patch.object(scanner, "_build_tcp_transport", return_value=fake_transport):
        with caplog.at_level(logging.WARNING):
            with pytest.raises(TimeoutError):
                await scanner.verify_connection()

    assert "Timeout during verify_connection" in caplog.text


async def test_verify_connection_transport_close_exception_in_finally(caplog):
    """Lines 862-865: Exception during transport.close() in finally is logged."""
    scanner = await _make_scanner()
    fake_transport = MagicMock()
    fake_transport.ensure_connected = AsyncMock(side_effect=ConnectionException("fail"))
    fake_transport.close = MagicMock(side_effect=OSError("close fail"))

    with patch.object(scanner, "_build_tcp_transport", return_value=fake_transport):
        with caplog.at_level(logging.DEBUG):
            with pytest.raises((ConnectionException, Exception)):
                await scanner.verify_connection()

    assert "Error closing Modbus transport during verify_connection" in caplog.text


# ---------------------------------------------------------------------------
# Group I: _is_valid_register_value BCD time (lines 889, 897)
# ---------------------------------------------------------------------------

async def test_is_valid_temperature_sensor_unavailable():
    """Line 889: temperature register with SENSOR_UNAVAILABLE is invalid."""
    scanner = await _make_scanner()
    scanner._register_ranges = {}
    # A register with 'temperature' but NOT in SENSOR_UNAVAILABLE_REGISTERS
    result = scanner._is_valid_register_value("coolant_temperature_extra", SENSOR_UNAVAILABLE)
    assert result is False


async def test_is_valid_bcd_time_invalid_value():
    """Lines 895-897: schedule register with invalid BCD time is invalid."""
    scanner = await _make_scanner()
    scanner._register_ranges = {}
    # 0x2500 → hours=25, invalid BCD and decimal 9472//100=94 also invalid
    result = scanner._is_valid_register_value("schedule_weekly_1", 0x2500)
    assert result is False


async def test_is_valid_bcd_time_valid_value():
    """Lines 895-897: schedule register with valid BCD time passes."""
    scanner = await _make_scanner()
    scanner._register_ranges = {}
    # 0x0800 → BCD 08:00, valid
    result = scanner._is_valid_register_value("schedule_weekly_1", 0x0800)
    assert result is True


# ---------------------------------------------------------------------------
# Group J: safe_scan=True forces single-register batches (line 994)
# ---------------------------------------------------------------------------

async def test_safe_scan_group_registers():
    """Line 994: safe_scan=True → single-register batches."""
    scanner = await _make_scanner(safe_scan=True)
    result = scanner._group_registers_for_batch_read([0, 1, 5, 10])
    assert result == [(0, 1), (1, 1), (5, 1), (10, 1)]


# ---------------------------------------------------------------------------
# Group K: scan() raises ConnectionException without transport/client
# ---------------------------------------------------------------------------

async def test_scan_raises_without_transport_and_client():
    """Lines 1027-1028: transport=None and client=None raises ConnectionException."""
    scanner = await _make_scanner()
    scanner._transport = None
    scanner._client = None
    with pytest.raises(ConnectionException, match="Transport not connected"):
        await scanner.scan()


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


# ---------------------------------------------------------------------------
# Group W: _read_input timeout/CancelledError/OSError (lines 1983-2041)
# ---------------------------------------------------------------------------

async def test_read_input_modbus_io_cancelled(caplog):
    """Lines 1983-1985: ModbusIOException with 'cancelled' aborts."""
    scanner = await _make_scanner(retry=2)
    mock_client = AsyncMock()
    exc = ModbusIOException("Request cancelled outside pymodbus")

    with (
        patch(
            "custom_components.thessla_green_modbus.scanner_core._call_modbus",
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
            "custom_components.thessla_green_modbus.scanner_core._call_modbus",
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
            "custom_components.thessla_green_modbus.scanner_core._call_modbus",
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

async def test_read_input_block_no_client():
    """Line 2075: when active_client=None, delegates to _read_input(chunk_start, chunk_count)."""
    scanner = await _make_scanner()
    scanner._client = None
    scanner._transport = None

    with patch.object(
        scanner, "_read_input", AsyncMock(return_value=[10, 20])
    ) as mock_ri:
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


# ---------------------------------------------------------------------------
# Group Y: _read_holding_block two-arg forms (lines 2090-2106)
# ---------------------------------------------------------------------------

async def test_read_holding_block_no_client():
    """Lines 2105-2106: when active_client=None, delegates to _read_holding."""
    scanner = await _make_scanner()
    scanner._client = None
    scanner._transport = None

    with patch.object(
        scanner, "_read_holding", AsyncMock(return_value=[30, 40])
    ) as mock_rh:
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


# ---------------------------------------------------------------------------
# Group Z: _read_holding two-arg forms (lines 2129-2136)
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# Group AA: Holding failure counter skips (lines 2157-2161)
# ---------------------------------------------------------------------------

async def test_read_holding_skips_when_failures_exceed_retry():
    """Lines 2158-2161: When failures >= retry, skip register immediately."""
    scanner = await _make_scanner(retry=2)
    scanner._holding_failures[10] = 2  # equals retry
    mock_client = AsyncMock()

    with patch(
        "custom_components.thessla_green_modbus.scanner_core._call_modbus",
        AsyncMock(),
    ) as mock_call:
        result = await scanner._read_holding(mock_client, 10, 1)

    assert result is None
    mock_call.assert_not_called()


# ---------------------------------------------------------------------------
# Group AB: Holding success clears failure counter (line 2217)
# ---------------------------------------------------------------------------

async def test_read_holding_success_clears_failure_counter():
    """Line 2217: Successful read removes address from _holding_failures."""
    scanner = await _make_scanner(retry=3)
    scanner._holding_failures[5] = 1  # partial failure
    mock_client = AsyncMock()

    ok_resp = _make_ok_response([42])
    with (
        patch(
            "custom_components.thessla_green_modbus.scanner_core._call_modbus",
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

async def test_read_holding_cancelled_error_reraises():
    """Lines 2286-2293: asyncio.CancelledError is re-raised."""
    scanner = await _make_scanner(retry=1)
    mock_client = AsyncMock()

    with (
        patch(
            "custom_components.thessla_green_modbus.scanner_core._call_modbus",
            AsyncMock(side_effect=asyncio.CancelledError()),
        ),
        patch("asyncio.sleep", AsyncMock()),
    ):
        with pytest.raises(asyncio.CancelledError):
            await scanner._read_holding(mock_client, 0, 1)


async def test_read_holding_oserror_breaks(caplog):
    """Lines 2294-2302: OSError breaks retry loop."""
    scanner = await _make_scanner(retry=2)
    mock_client = AsyncMock()

    with (
        patch(
            "custom_components.thessla_green_modbus.scanner_core._call_modbus",
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

async def test_read_coil_two_arg_count_none():
    """Lines 2340-2343: _read_coil(address, count) — count=None path uses self._client."""
    scanner = await _make_scanner(retry=1)
    mock_client = AsyncMock()
    scanner._client = mock_client

    bit_resp = _make_bit_response([True])
    with (
        patch(
            "custom_components.thessla_green_modbus.scanner_core._call_modbus",
            AsyncMock(return_value=bit_resp),
        ),
    ):
        result = await scanner._read_coil(0, 1)

    assert result == [True]


async def test_read_coil_two_arg_int_address():
    """Lines 2344-2347: _read_coil(int, count, count) — int address path."""
    scanner = await _make_scanner(retry=1)
    mock_client = AsyncMock()
    scanner._client = mock_client

    bit_resp = _make_bit_response([False])
    with (
        patch(
            "custom_components.thessla_green_modbus.scanner_core._call_modbus",
            AsyncMock(return_value=bit_resp),
        ),
    ):
        result = await scanner._read_coil(0, 1, 1)

    assert result == [False]


# ---------------------------------------------------------------------------
# Group AE: _read_coil client None raises (line 2352-2353)
# ---------------------------------------------------------------------------

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

async def test_read_coil_timeout_error(caplog):
    """Lines 2381-2388: TimeoutError logged, retries exhausted → None."""
    scanner = await _make_scanner(retry=2)
    mock_client = AsyncMock()
    scanner._client = mock_client

    with (
        patch(
            "custom_components.thessla_green_modbus.scanner_core._call_modbus",
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
            "custom_components.thessla_green_modbus.scanner_core._call_modbus",
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

async def test_read_coil_cancelled_error_reraises():
    """Lines 2406-2412: asyncio.CancelledError is re-raised."""
    scanner = await _make_scanner(retry=1)
    mock_client = AsyncMock()
    scanner._client = mock_client

    with (
        patch(
            "custom_components.thessla_green_modbus.scanner_core._call_modbus",
            AsyncMock(side_effect=asyncio.CancelledError()),
        ),
    ):
        with pytest.raises(asyncio.CancelledError):
            await scanner._read_coil(mock_client, 0, 1)


async def test_read_coil_oserror_breaks(caplog):
    """Lines 2413-2421: OSError breaks retry loop."""
    scanner = await _make_scanner(retry=2)
    mock_client = AsyncMock()
    scanner._client = mock_client

    with (
        patch(
            "custom_components.thessla_green_modbus.scanner_core._call_modbus",
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

async def test_read_discrete_two_arg_count_none():
    """Lines 2443-2446: _read_discrete(address, count) — count=None path."""
    scanner = await _make_scanner(retry=1)
    mock_client = AsyncMock()
    scanner._client = mock_client

    bit_resp = _make_bit_response([True])
    with (
        patch(
            "custom_components.thessla_green_modbus.scanner_core._call_modbus",
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
            "custom_components.thessla_green_modbus.scanner_core._call_modbus",
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


# ---------------------------------------------------------------------------
# Group AJ: _read_discrete TimeoutError/exceptions (lines 2484-2524)
# ---------------------------------------------------------------------------

async def test_read_discrete_timeout_error(caplog):
    """Lines 2484-2491: TimeoutError logged."""
    scanner = await _make_scanner(retry=2)
    mock_client = AsyncMock()
    scanner._client = mock_client

    with (
        patch(
            "custom_components.thessla_green_modbus.scanner_core._call_modbus",
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
            "custom_components.thessla_green_modbus.scanner_core._call_modbus",
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
            "custom_components.thessla_green_modbus.scanner_core._call_modbus",
            AsyncMock(side_effect=asyncio.CancelledError()),
        ),
    ):
        with pytest.raises(asyncio.CancelledError):
            await scanner._read_discrete(mock_client, 0, 1)


async def test_read_discrete_oserror_breaks(caplog):
    """Lines 2516-2524: OSError breaks retry loop."""
    scanner = await _make_scanner(retry=2)
    mock_client = AsyncMock()
    scanner._client = mock_client

    with (
        patch(
            "custom_components.thessla_green_modbus.scanner_core._call_modbus",
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


async def _run_minimal_scan(scanner, *, input_return=None, holding_return=None,
                             coil_return=None, discrete_return=None):
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

async def test_scan_skip_known_missing_input_register():
    """Line 1302-1303: skip_known_missing=True skips 'compilation_days'."""
    scanner = await _make_scanner(skip_known_missing=True)
    scanner._client = AsyncMock()

    from custom_components.thessla_green_modbus.scanner_core import INPUT_REGISTERS
    if "compilation_days" not in INPUT_REGISTERS:
        pytest.skip("compilation_days not in INPUT_REGISTERS")

    result = await _run_minimal_scan(scanner, input_return=[1])
    # compilation_days should not appear in missing registers (was skipped)
    missing = result.get("missing_registers", {}).get("input_registers", {})
    assert "compilation_days" not in missing


async def test_scan_input_batch_fail_probe_success():
    """Lines 1313-1341: batch read fails, probe individual succeeds."""
    scanner = await _make_scanner(retry=1)
    scanner._client = AsyncMock()

    from custom_components.thessla_green_modbus.scanner_core import INPUT_REGISTERS
    if "version_major" not in INPUT_REGISTERS:
        pytest.skip("version_major not in INPUT_REGISTERS")

    addr = INPUT_REGISTERS["version_major"]
    scanner._registers = {4: {addr: "version_major"}, 3: {}, 1: {}, 2: {}}

    batch_call_count = {"n": 0}

    async def mock_read_input(*args, **kwargs):
        batch_call_count["n"] += 1
        if batch_call_count["n"] <= 2:  # firmware block reads return empty
            return []
        count = args[-1] if len(args) > 1 else kwargs.get("count", 1)
        if count > 1:
            return None  # batch fails
        return [4]  # individual probe succeeds

    with (
        patch.object(scanner, "_read_input_block", AsyncMock(return_value=[])),
        patch.object(scanner, "_read_holding_block", AsyncMock(return_value=[])),
        patch.object(scanner, "_read_input", side_effect=mock_read_input),
        patch.object(scanner, "_read_holding", AsyncMock(return_value=None)),
        patch.object(scanner, "_read_coil", AsyncMock(return_value=None)),
        patch.object(scanner, "_read_discrete", AsyncMock(return_value=None)),
    ):
        result = await scanner.scan()

    assert "available_registers" in result


async def test_scan_input_batch_fail_probe_fail(caplog):
    """Lines 1332-1334: batch fails, individual probe returns falsy → warning."""
    scanner = await _make_scanner(retry=1)
    scanner._client = AsyncMock()

    from custom_components.thessla_green_modbus.scanner_core import INPUT_REGISTERS
    if "version_major" not in INPUT_REGISTERS:
        pytest.skip("version_major not in INPUT_REGISTERS")

    addr = INPUT_REGISTERS["version_major"]
    scanner._registers = {4: {addr: "version_major"}, 3: {}, 1: {}, 2: {}}

    async def mock_read_input(*args, **kwargs):
        count = args[-1] if len(args) > 1 else 1
        if isinstance(count, int) and count > 1:
            return None  # batch fails
        return None  # probe also fails

    with (
        patch.object(scanner, "_read_input_block", AsyncMock(return_value=[])),
        patch.object(scanner, "_read_holding_block", AsyncMock(return_value=[])),
        patch.object(scanner, "_read_input", side_effect=mock_read_input),
        patch.object(scanner, "_read_holding", AsyncMock(return_value=None)),
        patch.object(scanner, "_read_coil", AsyncMock(return_value=None)),
        patch.object(scanner, "_read_discrete", AsyncMock(return_value=None)),
        caplog.at_level(logging.WARNING),
    ):
        await scanner.scan()

    assert "Failed to read input_registers register" in caplog.text


# ---------------------------------------------------------------------------
# Group P: Holding batch failure recovery (lines 1368-1410)
# ---------------------------------------------------------------------------

async def test_scan_holding_batch_fail_probe_success():
    """Lines 1373-1400: holding batch fails, probe succeeds."""
    scanner = await _make_scanner(retry=1)
    scanner._client = AsyncMock()

    from custom_components.thessla_green_modbus.scanner_core import HOLDING_REGISTERS
    if "mode" not in HOLDING_REGISTERS:
        pytest.skip("mode not in HOLDING_REGISTERS")

    addr = HOLDING_REGISTERS["mode"]
    scanner._registers = {4: {}, 3: {addr: "mode"}, 1: {}, 2: {}}

    async def mock_read_holding(*args, **kwargs):
        count = args[-1] if len(args) > 1 else 1
        if isinstance(count, int) and count > 1:
            return None  # batch fails
        return [1]  # probe succeeds with valid value

    with (
        patch.object(scanner, "_read_input_block", AsyncMock(return_value=[])),
        patch.object(scanner, "_read_holding_block", AsyncMock(return_value=[])),
        patch.object(scanner, "_read_input", AsyncMock(return_value=None)),
        patch.object(scanner, "_read_holding", side_effect=mock_read_holding),
        patch.object(scanner, "_read_coil", AsyncMock(return_value=None)),
        patch.object(scanner, "_read_discrete", AsyncMock(return_value=None)),
    ):
        result = await scanner.scan()

    assert "available_registers" in result


# ---------------------------------------------------------------------------
# Group Q: deep_scan=True (line 1548)
# ---------------------------------------------------------------------------

async def test_deep_scan_skips_none_result():
    """Line 1548: deep_scan=True with None read results → continue."""
    scanner = await _make_scanner(deep_scan=True)
    scanner._client = AsyncMock()

    with (
        patch.object(scanner, "_read_input_block", AsyncMock(return_value=[])),
        patch.object(scanner, "_read_holding_block", AsyncMock(return_value=[])),
        patch.object(scanner, "_read_input", AsyncMock(return_value=None)),
        patch.object(scanner, "_read_holding", AsyncMock(return_value=None)),
        patch.object(scanner, "_read_coil", AsyncMock(return_value=None)),
        patch.object(scanner, "_read_discrete", AsyncMock(return_value=None)),
    ):
        result = await scanner.scan()

    assert "raw_registers" in result
    assert result["raw_registers"] == {}


async def test_deep_scan_collects_values():
    """Line 1547-1550: deep_scan=True with data collects raw_registers."""
    scanner = await _make_scanner(deep_scan=True)
    scanner._client = AsyncMock()

    with (
        patch.object(scanner, "_read_input_block", AsyncMock(return_value=[])),
        patch.object(scanner, "_read_holding_block", AsyncMock(return_value=[])),
        patch.object(scanner, "_read_input", AsyncMock(return_value=[42])),
        patch.object(scanner, "_read_holding", AsyncMock(return_value=None)),
        patch.object(scanner, "_read_coil", AsyncMock(return_value=None)),
        patch.object(scanner, "_read_discrete", AsyncMock(return_value=None)),
    ):
        result = await scanner.scan()

    assert "raw_registers" in result
    assert len(result["raw_registers"]) > 0


# ---------------------------------------------------------------------------
# Group M: full_register_scan with invalid holding values (lines 1229-1253)
# ---------------------------------------------------------------------------

async def test_full_register_scan_input_returns_none():
    """Lines 1198-1202: full_register_scan input read returns None."""
    scanner = await _make_scanner(full_register_scan=True, retry=1)
    scanner._client = AsyncMock()
    scanner._registers = {4: {0: "version_major"}, 3: {0: "mode"}, 1: {}, 2: {}}

    with (
        patch.object(scanner, "_read_input_block", AsyncMock(return_value=[])),
        patch.object(scanner, "_read_holding_block", AsyncMock(return_value=[])),
        patch.object(scanner, "_read_input", AsyncMock(return_value=None)),
        patch.object(scanner, "_read_holding", AsyncMock(return_value=None)),
        patch.object(scanner, "_read_coil", AsyncMock(return_value=None)),
        patch.object(scanner, "_read_discrete", AsyncMock(return_value=None)),
    ):
        result = await scanner.scan()

    assert result["failed_addresses"]["modbus_exceptions"]["input_registers"]


async def test_full_register_scan_holding_invalid_value():
    """Lines 1248-1253: full_register_scan holding has invalid value (65535)."""
    scanner = await _make_scanner(full_register_scan=True, retry=1)
    scanner._client = AsyncMock()
    scanner._registers = {4: {0: "version_major"}, 3: {0: "mode"}, 1: {}, 2: {}}

    with (
        patch.object(scanner, "_read_input_block", AsyncMock(return_value=[])),
        patch.object(scanner, "_read_holding_block", AsyncMock(return_value=[])),
        patch.object(scanner, "_read_input", AsyncMock(return_value=[1])),
        patch.object(scanner, "_read_holding", AsyncMock(return_value=[65535])),
        patch.object(scanner, "_read_coil", AsyncMock(return_value=None)),
        patch.object(scanner, "_read_discrete", AsyncMock(return_value=None)),
    ):
        result = await scanner.scan()

    # 65535 is invalid → should appear in failed_addresses
    assert result["failed_addresses"]["invalid_values"].get("holding_registers") or \
           result["unknown_registers"]["holding_registers"]


# ---------------------------------------------------------------------------
# Group N: full_register_scan coil/discrete (lines 1258-1296)
# ---------------------------------------------------------------------------

async def test_full_register_scan_coil_returns_none():
    """Lines 1261-1265: full_register_scan coil read returns None."""
    scanner = await _make_scanner(full_register_scan=True, retry=1)
    scanner._client = AsyncMock()
    scanner._registers = {4: {0: "version_major"}, 3: {}, 1: {0: "some_coil"}, 2: {}}

    with (
        patch.object(scanner, "_read_input_block", AsyncMock(return_value=[])),
        patch.object(scanner, "_read_holding_block", AsyncMock(return_value=[])),
        patch.object(scanner, "_read_input", AsyncMock(return_value=[1])),
        patch.object(scanner, "_read_holding", AsyncMock(return_value=None)),
        patch.object(scanner, "_read_coil", AsyncMock(return_value=None)),
        patch.object(scanner, "_read_discrete", AsyncMock(return_value=None)),
    ):
        result = await scanner.scan()

    assert result["failed_addresses"]["modbus_exceptions"]["coil_registers"]


async def test_full_register_scan_discrete_returns_value():
    """Lines 1280-1296: full_register_scan discrete reads a value."""
    scanner = await _make_scanner(full_register_scan=True, retry=1)
    scanner._client = AsyncMock()
    scanner._registers = {4: {}, 3: {}, 1: {}, 2: {0: "some_discrete"}}

    with (
        patch.object(scanner, "_read_input_block", AsyncMock(return_value=[])),
        patch.object(scanner, "_read_holding_block", AsyncMock(return_value=[])),
        patch.object(scanner, "_read_input", AsyncMock(return_value=None)),
        patch.object(scanner, "_read_holding", AsyncMock(return_value=None)),
        patch.object(scanner, "_read_coil", AsyncMock(return_value=None)),
        patch.object(scanner, "_read_discrete", AsyncMock(return_value=[True])),
    ):
        result = await scanner.scan()

    # discrete read returned [True] — the register at addr 0 should be in
    # available_registers (possibly under the global alias name)
    assert result["available_registers"]["discrete_inputs"]


# ---------------------------------------------------------------------------
# Group S: RTU in scan_device (lines 1669-1675)
# ---------------------------------------------------------------------------

async def test_scan_device_rtu_no_serial_port_raises():
    """Line 1669-1670: scan_device with RTU and no serial_port raises."""
    scanner = await _make_scanner(connection_type=CONNECTION_TYPE_RTU)
    scanner.serial_port = ""

    with pytest.raises(ConnectionException, match="Serial port not configured"):
        await scanner.scan_device()


async def test_scan_device_rtu_creates_transport():
    """Lines 1671-1684: scan_device with RTU creates RtuModbusTransport."""
    scanner = await _make_scanner(connection_type=CONNECTION_TYPE_RTU, serial_port="/dev/ttyUSB0")

    mock_client = AsyncMock()
    mock_transport = _make_transport()
    mock_transport.ensure_connected = AsyncMock()
    mock_transport.client = mock_client

    with patch(
        "custom_components.thessla_green_modbus.scanner_core.RtuModbusTransport",
        return_value=mock_transport,
    ) as mock_rtu:
        with (
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

async def test_scan_device_auto_detect_all_fail():
    """Lines 1721-1724: all auto-detect attempts fail → ConnectionException."""
    scanner = await _make_scanner(connection_mode="auto")

    failing_transport = MagicMock()
    failing_transport.ensure_connected = AsyncMock(side_effect=ConnectionException("no"))
    failing_transport.close = AsyncMock()

    with patch.object(
        scanner,
        "_build_auto_tcp_attempts",
        return_value=[
            ("tcp", failing_transport, 1.0),
        ],
    ):
        with pytest.raises(ConnectionException, match="Auto-detect Modbus transport failed"):
            await scanner.scan_device()


# ---------------------------------------------------------------------------
# Group R: scan_device legacy compat path (line 1663)
# ---------------------------------------------------------------------------

async def test_scan_device_scan_returns_non_dict_raises():
    """Line 1663: scan() returning non-dict raises TypeError (legacy compat path)."""
    scanner = await _make_scanner()

    # Patch scan at class level with a regular coroutine function so that
    # scan_method.__func__ IS ThesslaGreenDeviceScanner.scan (bypassing first branch).
    # Then in the legacy compat path, scan() returns non-dict → TypeError.
    async def fake_scan(self_arg):
        return "not_a_dict"

    mock_ctor = MagicMock()
    mock_client = MagicMock()
    mock_client.connect.return_value = True
    mock_ctor.return_value = mock_client

    with patch.object(ThesslaGreenDeviceScanner, "scan", fake_scan):
        with patch(
            "custom_components.thessla_green_modbus.scanner_core.importlib.import_module"
        ) as mock_import:
            mock_mod = MagicMock()
            mock_mod.ModbusTcpClient = mock_ctor
            mock_import.return_value = mock_mod

            with patch.object(scanner, "close", AsyncMock()):
                with pytest.raises(TypeError, match="scan\\(\\) must return a dict"):
                    await scanner.scan_device()
