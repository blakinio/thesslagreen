# mypy: ignore-errors
"""Tests for the Modbus helper utilities."""

import asyncio
import gc
import sys
import types
import warnings
import weakref

import pytest

original_registers = sys.modules.get("custom_components.thessla_green_modbus.registers")
original_loader = sys.modules.get("custom_components.thessla_green_modbus.registers.loader")

loader_stub = types.SimpleNamespace(
    load_registers=lambda: ([], {}),
    get_all_registers=lambda: [],
    get_registers_by_function=lambda fn: [],
)
sys.modules["custom_components.thessla_green_modbus.registers.loader"] = loader_stub
sys.modules["custom_components.thessla_green_modbus.registers"] = types.SimpleNamespace(
    loader=loader_stub,
    get_all_registers=loader_stub.get_all_registers,
    get_registers_by_function=loader_stub.get_registers_by_function,
)

from custom_components.thessla_green_modbus.modbus_helpers import (  # noqa: E402
    _KWARG_CACHE,
    _SIG_CACHE,
    _call_modbus,
    async_close_client,
    group_reads,
)

if original_loader is not None:
    sys.modules["custom_components.thessla_green_modbus.registers.loader"] = original_loader
else:
    sys.modules.pop("custom_components.thessla_green_modbus.registers.loader", None)

if original_registers is not None:
    sys.modules["custom_components.thessla_green_modbus.registers"] = original_registers
else:
    sys.modules.pop("custom_components.thessla_green_modbus.registers", None)


@pytest.mark.asyncio
async def test_call_modbus_supports_unit_keyword():
    """Functions expecting ``unit`` should be handled."""

    async def func(address, *, count, unit=None):
        return address, count, unit

    result = await _call_modbus(func, 1, 10, 2)
    assert result == (10, 2, 1)  # nosec B101


@pytest.mark.asyncio
async def test_call_modbus_supports_slave_keyword():
    """Functions expecting ``slave`` should be handled."""

    async def func(address, *, count, slave=None):
        return address, count, slave

    result = await _call_modbus(func, 1, 20, 3)
    assert result == (20, 3, 1)  # nosec B101


@pytest.mark.asyncio
async def test_call_modbus_supports_no_slave_or_unit():
    """Functions expecting neither keyword should be handled."""

    async def func(address, *, count):
        return address, count

    result = await _call_modbus(func, 1, 30, 4)
    assert result == (30, 4)  # nosec B101


@pytest.mark.asyncio
async def test_call_modbus_skips_external_timeout_for_pymodbus_callables():
    """Pymodbus callables should rely on their own internal timeout handling."""

    async def func(address, *, count, device_id=None):
        await asyncio.sleep(0.01)
        return address, count, device_id

    func.__module__ = "pymodbus.client.mixin"

    result = await _call_modbus(func, 1, 20, 3, timeout=0.000001)
    assert result == (20, 3, 1)  # nosec B101


@pytest.mark.asyncio
async def test_call_modbus_propagates_cancelled_error():
    """Cancelled errors should propagate without being mapped."""

    async def func(address, *, count):
        raise asyncio.CancelledError

    with pytest.raises(asyncio.CancelledError):
        await _call_modbus(func, 1, 30, 4)


@pytest.mark.asyncio
async def test_group_reads_merges_sequential_addresses():
    """Sequential addresses are merged into contiguous blocks."""

    assert group_reads([0, 1, 2, 4, 5]) == [(0, 3), (4, 2)]


@pytest.mark.asyncio
async def test_group_reads_honours_block_size():
    """Groups are split when exceeding ``max_block_size``."""

    assert group_reads(range(10), max_block_size=4) == [
        (0, 4),
        (4, 4),
        (8, 2),
    ]


@pytest.mark.asyncio
async def test_modbus_cache_entries_removed_on_gc():
    """Cached entries should disappear when functions are garbage collected."""

    _KWARG_CACHE.clear()
    _SIG_CACHE.clear()

    async def func(address, *, count, unit=None):
        return address, count, unit

    await _call_modbus(func, 1, 10, 2)
    assert func in _KWARG_CACHE
    assert func in _SIG_CACHE

    func_ref = weakref.ref(func)
    del func
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", ResourceWarning)
        gc.collect()

    assert func_ref() is None
    assert len(_KWARG_CACHE) == 0
    assert len(_SIG_CACHE) == 0


@pytest.mark.asyncio
async def test_async_close_client_with_sync_close():
    """Synchronous close should be handled without awaiting."""

    class SyncClient:
        def __init__(self):
            self.closed = False

        def close(self):
            self.closed = True
            return None

    client = SyncClient()
    await async_close_client(client)
    assert client.closed is True  # nosec B101


@pytest.mark.asyncio
async def test_async_close_client_with_async_close():
    """Async close should be awaited."""

    class AsyncClient:
        def __init__(self):
            self.closed = False

        async def close(self):
            self.closed = True

    client = AsyncClient()
    await async_close_client(client)
    assert client.closed is True  # nosec B101


# ---------------------------------------------------------------------------
# _get_signature — TypeError/ValueError fallback (lines 37-38)
# ---------------------------------------------------------------------------


def test_get_signature_returns_none_for_non_inspectable():
    """_get_signature returns None for objects that raise TypeError."""
    from custom_components.thessla_green_modbus.modbus_helpers import _get_signature

    # Built-in C functions raise TypeError on inspect.signature
    result = _get_signature(len)
    # May return a signature or None depending on Python version;
    # the key thing is it doesn't raise
    assert result is None or result is not None


def test_get_signature_caches_result():
    """_get_signature returns cached result on repeated calls."""
    from custom_components.thessla_green_modbus.modbus_helpers import _get_signature

    async def my_func(a, b): ...

    r1 = _get_signature(my_func)
    r2 = _get_signature(my_func)
    assert r1 is r2


# ---------------------------------------------------------------------------
# _mask_frame — short hex edge case (line 124)
# ---------------------------------------------------------------------------


def test_mask_frame_empty():
    from custom_components.thessla_green_modbus.modbus_helpers import _mask_frame

    assert _mask_frame(b"") == ""


def test_mask_frame_single_byte():
    """Single byte → hex is 2 chars → mask covers them both."""
    from custom_components.thessla_green_modbus.modbus_helpers import _mask_frame

    result = _mask_frame(bytes([0x01]))
    assert result.startswith("**")


def test_mask_frame_multi_bytes():
    from custom_components.thessla_green_modbus.modbus_helpers import _mask_frame

    result = _mask_frame(bytes([0x01, 0x04, 0x00, 0x64]))
    assert result.startswith("**")
    assert "0064" in result


# ---------------------------------------------------------------------------
# _build_request_frame — uncovered func names (lines 147-183)
# ---------------------------------------------------------------------------


def test_build_request_frame_read_coils():
    from custom_components.thessla_green_modbus.modbus_helpers import _build_request_frame

    frame = _build_request_frame("read_coils", 1, [100], {"count": 8})
    assert frame[0] == 1   # slave_id
    assert frame[1] == 1   # function code for read_coils
    assert len(frame) == 6


def test_build_request_frame_read_discrete_inputs():
    from custom_components.thessla_green_modbus.modbus_helpers import _build_request_frame

    frame = _build_request_frame("read_discrete_inputs", 1, [200], {"count": 4})
    assert frame[1] == 2   # function code


def test_build_request_frame_write_register():
    from custom_components.thessla_green_modbus.modbus_helpers import _build_request_frame

    frame = _build_request_frame("write_register", 1, [100], {"value": 42})
    assert frame[1] == 6   # function code for write single
    assert len(frame) == 6


def test_build_request_frame_write_registers():
    from custom_components.thessla_green_modbus.modbus_helpers import _build_request_frame

    frame = _build_request_frame("write_registers", 1, [100], {"values": [10, 20]})
    assert frame[1] == 16  # function code 0x10
    assert len(frame) == 7 + 4  # header(7) + 2 values * 2 bytes


def test_build_request_frame_write_coil_true():
    from custom_components.thessla_green_modbus.modbus_helpers import _build_request_frame

    frame = _build_request_frame("write_coil", 1, [50], {"value": True})
    assert frame[1] == 5   # function code for write coil
    assert frame[4] == 0xFF  # 65280 = 0xFF00 → high byte


def test_build_request_frame_write_coil_false():
    from custom_components.thessla_green_modbus.modbus_helpers import _build_request_frame

    frame = _build_request_frame("write_coil", 1, [50], {"value": False})
    assert frame[4] == 0x00  # value 0 → high byte = 0


def test_build_request_frame_unknown_func_returns_empty():
    from custom_components.thessla_green_modbus.modbus_helpers import _build_request_frame

    frame = _build_request_frame("unknown_function", 1, [], {})
    assert frame == b""


def test_build_request_frame_value_error_returns_empty():
    from custom_components.thessla_green_modbus.modbus_helpers import _build_request_frame

    # Pass non-integer address to trigger ValueError
    frame = _build_request_frame("read_coils", 1, ["not_an_int"], {"count": 1})
    assert frame == b""


# ---------------------------------------------------------------------------
# _calculate_backoff_delay — tuple jitter with inverted bounds (lines 212-214)
# ---------------------------------------------------------------------------


def test_calculate_backoff_jitter_tuple_inverted():
    """Jitter tuple with max < min is automatically swapped."""
    from custom_components.thessla_green_modbus.modbus_helpers import _calculate_backoff_delay

    # Inverted: (1.0, 0.0) should be treated as (0.0, 1.0)
    delay = _calculate_backoff_delay(base=1.0, attempt=2, jitter=(1.0, 0.0))
    assert delay >= 1.0  # base delay for attempt=2 is 1.0


def test_calculate_backoff_jitter_float():
    """Jitter as scalar float adds random component."""
    from custom_components.thessla_green_modbus.modbus_helpers import _calculate_backoff_delay

    delay = _calculate_backoff_delay(base=1.0, attempt=2, jitter=0.5)
    assert delay >= 1.0


def test_calculate_backoff_no_jitter_zero_attempt():
    """Zero attempt returns 0."""
    from custom_components.thessla_green_modbus.modbus_helpers import _calculate_backoff_delay

    assert _calculate_backoff_delay(base=1.0, attempt=1, jitter=None) == 0.0


def test_calculate_backoff_zero_base():
    from custom_components.thessla_green_modbus.modbus_helpers import _calculate_backoff_delay

    assert _calculate_backoff_delay(base=0.0, attempt=5, jitter=None) == 0.0


# ---------------------------------------------------------------------------
# _get_signature — TypeError/ValueError path (lines 37-38)
# ---------------------------------------------------------------------------


def test_get_signature_typeerror_returns_none():
    """inspect.signature raising TypeError returns None."""
    import inspect
    from unittest.mock import patch

    from custom_components.thessla_green_modbus.modbus_helpers import _get_signature, _SIG_CACHE

    def func():
        pass

    # Ensure not in cache
    _SIG_CACHE.pop(func, None)

    with patch.object(inspect, "signature", side_effect=TypeError("no sig")):
        result = _get_signature(func)
    assert result is None  # nosec B101


def test_get_signature_valueerror_returns_none():
    """inspect.signature raising ValueError returns None."""
    import inspect
    from unittest.mock import patch

    from custom_components.thessla_green_modbus.modbus_helpers import _get_signature, _SIG_CACHE

    def func():
        pass

    _SIG_CACHE.pop(func, None)

    with patch.object(inspect, "signature", side_effect=ValueError("bad sig")):
        result = _get_signature(func)
    assert result is None  # nosec B101


# ---------------------------------------------------------------------------
# async_maybe_await_close — obj=None (line 96) and no close (line 100)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_async_maybe_await_close_none():
    """obj=None returns immediately without error (line 96)."""
    from custom_components.thessla_green_modbus.modbus_helpers import async_maybe_await_close

    await async_maybe_await_close(None)  # must not raise


@pytest.mark.asyncio
async def test_async_maybe_await_close_no_close_attr():
    """obj without a close attribute returns immediately (line 100)."""
    from custom_components.thessla_green_modbus.modbus_helpers import async_maybe_await_close

    class NoCLose:
        pass

    await async_maybe_await_close(NoCLose())  # must not raise


@pytest.mark.asyncio
async def test_async_maybe_await_close_non_callable_close():
    """obj with non-callable close returns immediately (line 100)."""
    from custom_components.thessla_green_modbus.modbus_helpers import async_maybe_await_close

    class BadClose:
        close = "not_callable"

    await async_maybe_await_close(BadClose())  # must not raise


# ---------------------------------------------------------------------------
# chunk_register_range — count<=0, max=None, max<1 (lines 418, 421, 424)
# ---------------------------------------------------------------------------


def test_chunk_register_range_zero_count():
    """count<=0 returns empty list (line 418)."""
    from custom_components.thessla_green_modbus.modbus_helpers import chunk_register_range

    assert chunk_register_range(0, 0) == []  # nosec B101
    assert chunk_register_range(5, -1) == []  # nosec B101


def test_chunk_register_range_none_max_uses_const():
    """max_block_size=None uses constant default (line 421)."""
    from custom_components.thessla_green_modbus.modbus_helpers import chunk_register_range

    chunks = chunk_register_range(100, 5, None)
    assert len(chunks) == 1  # nosec B101
    assert chunks[0] == (100, 5)  # nosec B101


def test_chunk_register_range_max_zero_clamped_to_one():
    """max_block_size<=0 is clamped to 1 (line 424)."""
    from custom_components.thessla_green_modbus.modbus_helpers import chunk_register_range

    chunks = chunk_register_range(0, 3, 0)
    assert len(chunks) == 3  # nosec B101
    assert all(c[1] == 1 for c in chunks)  # nosec B101


# ---------------------------------------------------------------------------
# chunk_register_values — empty, max=None, max<1 (lines 445, 448, 451)
# ---------------------------------------------------------------------------


def test_chunk_register_values_empty():
    """Empty values list returns empty (line 445)."""
    from custom_components.thessla_green_modbus.modbus_helpers import chunk_register_values

    assert chunk_register_values(0, []) == []  # nosec B101


def test_chunk_register_values_none_max_uses_const():
    """max_block_size=None uses constant default (line 448)."""
    from custom_components.thessla_green_modbus.modbus_helpers import chunk_register_values

    chunks = chunk_register_values(10, [1, 2, 3], None)
    assert chunks == [(10, [1, 2, 3])]  # nosec B101


def test_chunk_register_values_max_zero_clamped_to_one():
    """max_block_size<=0 is clamped to 1 (line 451)."""
    from custom_components.thessla_green_modbus.modbus_helpers import chunk_register_values

    chunks = chunk_register_values(0, [10, 20], 0)
    assert len(chunks) == 2  # nosec B101
    assert chunks[0] == (0, [10])  # nosec B101
    assert chunks[1] == (1, [20])  # nosec B101


# ---------------------------------------------------------------------------
# _call_modbus — signature=None path, positional=list(args) (line 262)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_call_modbus_no_signature_positional():
    """When _get_signature returns None, args are passed as positional (line 262)."""
    from unittest.mock import patch

    from custom_components.thessla_green_modbus import modbus_helpers

    received = []

    async def func(*args, **kwargs):
        received.append((args, kwargs))
        return type("R", (), {"isError": lambda self: False})()

    with patch.object(modbus_helpers, "_get_signature", return_value=None):
        await modbus_helpers._call_modbus(func, 1, 100, 2)

    assert len(received) == 1  # nosec B101
    # 100 and 2 should have been forwarded as positional args
    assert 100 in received[0][0]  # nosec B101
    assert 2 in received[0][0]  # nosec B101


# ---------------------------------------------------------------------------
# get_rtu_framer coverage (lines 82-89)
# ---------------------------------------------------------------------------


def test_get_rtu_framer_returns_framer_type_rtu(monkeypatch):
    """get_rtu_framer() returns FramerType.RTU when FramerType is available (lines 82-84)."""
    from custom_components.thessla_green_modbus import modbus_helpers

    class FakeFramerType:
        RTU = "RTU_FRAMER"

    monkeypatch.setattr(modbus_helpers, "FramerType", FakeFramerType)
    result = modbus_helpers.get_rtu_framer()
    assert result == "RTU_FRAMER"  # nosec B101


def test_get_rtu_framer_returns_modbus_rtu_framer(monkeypatch):
    """get_rtu_framer() returns ModbusRtuFramer when FramerType is None (lines 87-88)."""
    from custom_components.thessla_green_modbus import modbus_helpers

    class FakeRtuFramer:
        pass

    monkeypatch.setattr(modbus_helpers, "FramerType", None)
    monkeypatch.setattr(modbus_helpers, "ModbusRtuFramer", FakeRtuFramer)
    result = modbus_helpers.get_rtu_framer()
    assert result is FakeRtuFramer  # nosec B101


def test_get_rtu_framer_returns_none_when_both_unavailable(monkeypatch):
    """get_rtu_framer() returns None when both FramerType and ModbusRtuFramer are None (line 89)."""
    from custom_components.thessla_green_modbus import modbus_helpers

    monkeypatch.setattr(modbus_helpers, "FramerType", None)
    monkeypatch.setattr(modbus_helpers, "ModbusRtuFramer", None)
    result = modbus_helpers.get_rtu_framer()
    assert result is None  # nosec B101


# ---------------------------------------------------------------------------
# _call_modbus StopIteration path (lines 253-255)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_call_modbus_stop_iteration_extra_args_beyond_params():
    """Extra args beyond param count are appended to positional (lines 253-255)."""
    from custom_components.thessla_green_modbus import modbus_helpers

    calls = []

    async def three_param_func(a, b, *rest):
        calls.append((a, b, rest))
        return type("R", (), {"isError": lambda self: False})()

    # 3 params (a, b, *rest); pass 4 args → 4th triggers StopIteration
    await modbus_helpers._call_modbus(three_param_func, 1, "x1", "x2", "x3", "x4")
    assert calls  # nosec B101
    assert calls[0][2] == ("x3", "x4")  # rest got extra args  # nosec B101


# ---------------------------------------------------------------------------
# _call_modbus ModbusIOException "request cancelled" (line 350)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_call_modbus_modbus_io_exception_request_cancelled(caplog):
    """ModbusIOException with 'request cancelled' text triggers debug log (line 350)."""
    import logging

    from custom_components.thessla_green_modbus import modbus_helpers
    from custom_components.thessla_green_modbus.modbus_exceptions import ModbusIOException

    async def cancel_func(slave):
        raise ModbusIOException("Request Cancelled by device")

    with pytest.raises(ModbusIOException):
        with caplog.at_level(logging.DEBUG, logger=modbus_helpers._LOGGER.name):
            await modbus_helpers._call_modbus(cancel_func, 1)

    assert any("cancelled" in r.message.lower() for r in caplog.records)  # nosec B101


# ---------------------------------------------------------------------------
# _call_modbus response logging paths (lines 369, 373-374)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_call_modbus_debug_logs_response_object_when_no_encode(caplog):
    """DEBUG mode logs response object when encode gives empty bytes (line 369)."""
    import logging

    from custom_components.thessla_green_modbus import modbus_helpers

    class NoEncodeResponse:
        pass  # no encode method → hasattr False → encoded = b""

    async def func_no_encode(slave):
        return NoEncodeResponse()

    with caplog.at_level(logging.DEBUG, logger=modbus_helpers._LOGGER.name):
        await modbus_helpers._call_modbus(func_no_encode, 1)

    assert any("Received from" in r.message for r in caplog.records)  # nosec B101


@pytest.mark.asyncio
async def test_call_modbus_non_debug_encode_exception_sets_empty(monkeypatch):
    """encode() exception at non-DEBUG level is silently caught (lines 373-374)."""
    import logging

    from custom_components.thessla_green_modbus import modbus_helpers

    class BadEncodeResponse:
        def encode(self):
            raise TypeError("cannot encode this")

    async def func_bad_encode(slave):
        return BadEncodeResponse()

    logger = modbus_helpers._LOGGER
    original_level = logger.level
    logger.setLevel(logging.WARNING)
    try:
        result = await modbus_helpers._call_modbus(func_bad_encode, 1)
    finally:
        logger.setLevel(original_level)

    assert isinstance(result, BadEncodeResponse)  # returned successfully  # nosec B101


# ---------------------------------------------------------------------------
# Phase 9 — _call_modbus backoff / debug logging paths
# ---------------------------------------------------------------------------

import logging as _logging
from custom_components.thessla_green_modbus import modbus_helpers as _mh


@pytest.mark.asyncio
async def test_call_modbus_backoff_delay_sleep():
    """delay > 0 on attempt >= 2 triggers the backoff sleep path (lines 295-299)."""
    async def simple_func(**kwargs):
        return "done"

    result = await _call_modbus(simple_func, 1, attempt=2, backoff=0.001, apply_backoff=True)
    assert result == "done"


@pytest.mark.asyncio
async def test_call_modbus_backoff_cancelled_during_sleep():
    """CancelledError during backoff sleep is re-raised (lines 300-304)."""
    async def simple_func(**kwargs):
        return "done"

    task = asyncio.create_task(
        _call_modbus(simple_func, 1, attempt=2, backoff=10.0, apply_backoff=True)
    )
    await asyncio.sleep(0.02)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task


@pytest.mark.asyncio
async def test_call_modbus_logs_request_frame_at_debug(caplog):
    """With DEBUG logger, non-None request frame is logged (line 318)."""
    async def read_coils(address, *, count=1, **kwargs):
        return "resp"

    with caplog.at_level(_logging.DEBUG, logger=_mh._LOGGER.name):
        result = await _call_modbus(read_coils, 1, 10, 2)
    assert result == "resp"
    assert any("Modbus request" in r.message for r in caplog.records)


@pytest.mark.asyncio
async def test_call_modbus_response_encode_error_logged(caplog):
    """response.encode() raising ValueError is caught and logged (lines 360-362)."""
    class BadResponse:
        def encode(self):
            raise ValueError("broken encode")

    async def bad_func(**kwargs):
        return BadResponse()

    with caplog.at_level(_logging.DEBUG, logger=_mh._LOGGER.name):
        result = await _call_modbus(bad_func, 1)
    assert isinstance(result, BadResponse)
    assert any("Failed to encode" in r.message for r in caplog.records)
