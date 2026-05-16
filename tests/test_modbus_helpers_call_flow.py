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

from custom_components.thessla_green_modbus.modbus.call import (
    _KWARG_CACHE,
    _LOGGER,
    _SIG_CACHE,
    _apply_attempt_delay,
    _calculate_batch_size,
    _call_modbus,
    _classify_modbus_exception,
    _log_call_attempt,
    _prepare_modbus_call,
    _PreparedCall,
    _raise_mapped_call_exception,
)
from custom_components.thessla_green_modbus.modbus.client_close import async_close_client
from custom_components.thessla_green_modbus.registers.read_planner import group_reads
from pymodbus.exceptions import ModbusIOException

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


def test_calculate_backoff_jitter_tuple_inverted():
    """Jitter tuple with max < min is automatically swapped."""
    from custom_components.thessla_green_modbus.modbus.call import _calculate_backoff_delay

    # Inverted: (1.0, 0.0) should be treated as (0.0, 1.0)
    delay = _calculate_backoff_delay(base=1.0, attempt=2, jitter=(1.0, 0.0))
    assert delay >= 1.0  # base delay for attempt=2 is 1.0


def test_calculate_backoff_jitter_float():
    """Jitter as scalar float adds random component."""
    from custom_components.thessla_green_modbus.modbus.call import _calculate_backoff_delay

    delay = _calculate_backoff_delay(base=1.0, attempt=2, jitter=0.5)
    assert delay >= 1.0


def test_calculate_batch_size_prefers_count():
    """Count keyword takes precedence for logging batch size."""
    assert _calculate_batch_size({"count": 7, "values": [1, 2]}) == 7


def test_calculate_batch_size_uses_values_length():
    """Values length is used when count is absent."""
    assert _calculate_batch_size({"values": [1, 2, 3]}) == 3


def test_calculate_batch_size_defaults_to_one():
    """Empty kwargs defaults to one request item."""
    assert _calculate_batch_size({}) == 1


@pytest.mark.asyncio
async def test_apply_attempt_delay_zero_does_not_sleep(monkeypatch):
    """Zero delay exits early without calling asyncio.sleep."""
    called = False

    async def fake_sleep(_delay):
        nonlocal called
        called = True

    monkeypatch.setattr(asyncio, "sleep", fake_sleep)
    await _apply_attempt_delay(
        delay=0.0, func_name="read_holding_registers", attempt=1, max_attempts=2
    )
    assert called is False  # nosec B101


def test_raise_mapped_call_exception_timeout():
    """Timeout errors are wrapped with the helper message."""
    with pytest.raises(TimeoutError, match="Modbus request timed out"):
        try:
            raise TimeoutError("inner timeout")
        except TimeoutError as err:
            _raise_mapped_call_exception(
                err,
                func_name="read_input_registers",
                attempt=1,
                max_attempts=3,
            )


@pytest.mark.asyncio
async def test_prepare_modbus_call_metadata_uses_detected_keyword():
    """Prepared metadata should keep argument normalization and unit-detection."""

    async def func(address, *, count, unit=None):
        return address, count, unit

    kwargs = {}
    positional, kwarg, func_name, batch_size, delay = _prepare_modbus_call(
        func,
        (11, 5),
        kwargs,
        attempt=1,
        backoff=0.1,
        backoff_jitter=None,
        apply_backoff=True,
    )

    assert positional == [11]
    assert kwargs == {"count": 5}
    assert kwarg == "unit"
    assert func_name == "func"
    assert batch_size == 5
    assert delay == 0.0


@pytest.mark.asyncio
async def test_prepare_modbus_call_metadata_disables_backoff():
    """Prepared metadata should skip delay when backoff is disabled."""

    async def func(address, *, count, slave=None):
        return address, count, slave

    positional, kwarg, _func_name, _batch_size, delay = _prepare_modbus_call(
        func,
        (2, 3),
        {},
        attempt=3,
        backoff=1.0,
        backoff_jitter=None,
        apply_backoff=False,
    )

    assert positional == [2]
    assert kwarg == "slave"
    assert delay == 0.0


def test_classify_modbus_exception_cancelled():
    """Cancelled request exceptions are classified as cancelled."""
    err = ModbusIOException("Request cancelled by remote peer")
    assert _classify_modbus_exception(err) == "cancelled"


def test_classify_modbus_exception_failed():
    """Non-cancelled exceptions are classified as failed."""
    assert _classify_modbus_exception(ValueError("bad")) == "failed"


def test_calculate_backoff_no_jitter_zero_attempt():
    """Zero attempt returns 0."""
    from custom_components.thessla_green_modbus.modbus.call import _calculate_backoff_delay

    assert _calculate_backoff_delay(base=1.0, attempt=1, jitter=None) == 0.0


def test_calculate_backoff_zero_base():
    from custom_components.thessla_green_modbus.modbus.call import _calculate_backoff_delay

    assert _calculate_backoff_delay(base=0.0, attempt=5, jitter=None) == 0.0


# ---------------------------------------------------------------------------
# _get_signature — TypeError/ValueError path (lines 37-38)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_async_maybe_await_close_none():
    """obj=None returns immediately without error (line 96)."""
    from custom_components.thessla_green_modbus.modbus.client_close import async_maybe_await_close

    await async_maybe_await_close(None)  # must not raise


@pytest.mark.asyncio
async def test_async_maybe_await_close_no_close_attr():
    """obj without a close attribute returns immediately (line 100)."""
    from custom_components.thessla_green_modbus.modbus.client_close import async_maybe_await_close

    class NoCLose:
        pass

    await async_maybe_await_close(NoCLose())  # must not raise


@pytest.mark.asyncio
async def test_async_maybe_await_close_non_callable_close():
    """obj with non-callable close returns immediately (line 100)."""
    from custom_components.thessla_green_modbus.modbus.client_close import async_maybe_await_close

    class BadClose:
        close = "not_callable"

    await async_maybe_await_close(BadClose())  # must not raise


# ---------------------------------------------------------------------------
# chunk_register_range — count<=0, max=None, max<1 (lines 418, 421, 424)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_call_modbus_no_signature_positional():
    """When _get_signature returns None, args are passed as positional (line 262)."""
    from unittest.mock import patch

    import custom_components.thessla_green_modbus.modbus.call as call_mod

    received = []

    async def func(*args, **kwargs):
        received.append((args, kwargs))
        return type("R", (), {"isError": lambda self: False})()

    with patch.object(call_mod, "_get_signature", return_value=None):
        await _call_modbus(func, 1, 100, 2)

    assert len(received) == 1  # nosec B101
    # 100 and 2 should have been forwarded as positional args
    assert 100 in received[0][0]  # nosec B101
    assert 2 in received[0][0]  # nosec B101


# ---------------------------------------------------------------------------
# get_rtu_framer coverage (lines 82-89)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_call_modbus_stop_iteration_extra_args_beyond_params():
    """Extra args beyond param count are appended to positional (lines 253-255)."""
    calls = []

    async def three_param_func(a, b, *rest):
        calls.append((a, b, rest))
        return type("R", (), {"isError": lambda self: False})()

    # 3 params (a, b, *rest); pass 4 args → 4th triggers StopIteration
    await _call_modbus(three_param_func, 1, "x1", "x2", "x3", "x4")
    assert calls  # nosec B101
    assert calls[0][2] == ("x3", "x4")  # rest got extra args  # nosec B101


# ---------------------------------------------------------------------------
# _call_modbus ModbusIOException "request cancelled" (line 350)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_call_modbus_modbus_io_exception_request_cancelled(caplog):
    """ModbusIOException with 'request cancelled' text triggers debug log (line 350)."""
    import logging

    from pymodbus.exceptions import ModbusIOException

    async def cancel_func(slave):
        raise ModbusIOException("Request Cancelled by device")

    with pytest.raises(ModbusIOException):
        with caplog.at_level(logging.DEBUG, logger=_LOGGER.name):
            await _call_modbus(cancel_func, 1)

    assert any("cancelled" in r.message.lower() for r in caplog.records)  # nosec B101


# ---------------------------------------------------------------------------
# _call_modbus response logging paths (lines 369, 373-374)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_call_modbus_debug_logs_response_object_when_no_encode(caplog):
    """DEBUG mode logs response object when encode gives empty bytes (line 369)."""
    import logging

    class NoEncodeResponse:
        pass  # no encode method → hasattr False → encoded = b""

    async def func_no_encode(slave):
        return NoEncodeResponse()

    with caplog.at_level(logging.DEBUG, logger="custom_components.thessla_green_modbus.modbus"):
        await _call_modbus(func_no_encode, 1)

    assert any("Received from" in r.message for r in caplog.records)  # nosec B101


@pytest.mark.asyncio
async def test_call_modbus_non_debug_encode_exception_sets_empty(monkeypatch):
    """encode() exception at non-DEBUG level is silently caught (lines 373-374)."""
    import logging

    class BadEncodeResponse:
        def encode(self):
            raise TypeError("cannot encode this")

    async def func_bad_encode(slave):
        return BadEncodeResponse()

    original_level = _LOGGER.level
    _LOGGER.setLevel(logging.WARNING)
    try:
        result = await _call_modbus(func_bad_encode, 1)
    finally:
        _LOGGER.setLevel(original_level)

    assert isinstance(result, BadEncodeResponse)  # returned successfully  # nosec B101


# ---------------------------------------------------------------------------
# Phase 9 — _call_modbus backoff / debug logging paths
# ---------------------------------------------------------------------------

import logging as _logging

import custom_components.thessla_green_modbus.modbus.call as _mh


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

    with caplog.at_level(_logging.DEBUG, logger="custom_components.thessla_green_modbus.modbus"):
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

    with caplog.at_level(_logging.DEBUG, logger="custom_components.thessla_green_modbus.modbus"):
        result = await _call_modbus(bad_func, 1)
    assert isinstance(result, BadResponse)
    assert any("Failed to encode" in r.message for r in caplog.records)


# ---------------------------------------------------------------------------
# _log_call_attempt — direct tests
# ---------------------------------------------------------------------------


def _make_prepared(
    func_name: str = "read_registers",
    batch_size: int = 4,
    positional: list | None = None,
    kwarg: str = "slave",
    delay: float = 0.0,
) -> _PreparedCall:
    return _PreparedCall(
        positional=positional if positional is not None else [10],
        kwarg=kwarg,
        func_name=func_name,
        batch_size=batch_size,
        delay=delay,
    )


def test_log_call_attempt_emits_calling_message(caplog):
    """_log_call_attempt logs the 'Calling ... on slave ...' summary."""
    prepared = _make_prepared(func_name="read_holding_registers", batch_size=3)
    with caplog.at_level(_logging.DEBUG, logger=_mh._LOGGER.name):
        _log_call_attempt(prepared, slave_id=5, attempt=1, max_attempts=3, kwargs={})
    messages = [r.message for r in caplog.records]
    assert any("read_holding_registers" in m and "slave 5" in m for m in messages)


def test_log_call_attempt_emits_request_frame_when_known(caplog):
    """_log_call_attempt logs a masked request frame for known function names."""
    prepared = _make_prepared(func_name="read_input_registers", positional=[20], batch_size=2)
    with caplog.at_level(_logging.DEBUG, logger="custom_components.thessla_green_modbus.modbus"):
        _log_call_attempt(prepared, slave_id=1, attempt=1, max_attempts=1, kwargs={"count": 2})
    messages = [r.message for r in caplog.records]
    assert any("Modbus request" in m for m in messages)


def test_log_call_attempt_includes_attempt_context(caplog):
    """_log_call_attempt includes attempt/max_attempts in the summary message."""
    prepared = _make_prepared(func_name="write_register", batch_size=1)
    with caplog.at_level(_logging.DEBUG, logger=_mh._LOGGER.name):
        _log_call_attempt(prepared, slave_id=2, attempt=2, max_attempts=4, kwargs={})
    messages = [r.message for r in caplog.records]
    assert any("2/4" in m for m in messages)
