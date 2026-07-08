"""Tests for the shared low-level read helpers (now in core/read_batches.py)."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from custom_components.thessla_green_modbus.core.read_batches import (
    execute_read_call,
    is_illegal_data_address_response,
    is_transient_error_response,
    raise_for_error_response,
)
from custom_components.thessla_green_modbus.core.retry import _PermanentModbusError
from pymodbus.exceptions import ModbusIOException


def _response(*, is_error: bool = True, exception_code=None):
    r = MagicMock()
    r.isError.return_value = is_error
    r.exception_code = exception_code
    return r


# ---------------------------------------------------------------------------
# is_illegal_data_address_response
# ---------------------------------------------------------------------------


def test_illegal_data_address_true_for_code_2():
    assert is_illegal_data_address_response(_response(exception_code=2)) is True


def test_illegal_data_address_false_for_code_3():
    assert is_illegal_data_address_response(_response(exception_code=3)) is False


def test_illegal_data_address_false_for_none_code():
    assert is_illegal_data_address_response(_response(exception_code=None)) is False


def test_illegal_data_address_false_for_plain_object():
    assert is_illegal_data_address_response(object()) is False


# ---------------------------------------------------------------------------
# is_transient_error_response
# ---------------------------------------------------------------------------


def test_transient_true_when_exception_code_is_none():
    assert is_transient_error_response(_response(exception_code=None)) is True


def test_transient_true_when_exception_code_is_other():
    assert is_transient_error_response(_response(exception_code=3)) is True


def test_transient_false_when_illegal_data_address():
    assert is_transient_error_response(_response(exception_code=2)) is False


# ---------------------------------------------------------------------------
# raise_for_error_response
# ---------------------------------------------------------------------------


def test_raise_noop_when_not_error():
    r = _response(is_error=False)
    raise_for_error_response(MagicMock(), r, register_type="input_registers", start_address=0)


def test_raise_permanent_error_for_illegal_data_address():
    r = _response(is_error=True, exception_code=2)
    with pytest.raises(_PermanentModbusError, match="Illegal data address"):
        raise_for_error_response(MagicMock(), r, register_type="input_registers", start_address=10)


def test_raise_modbus_io_exception_for_transient_error():
    r = _response(is_error=True, exception_code=3)
    with pytest.raises(ModbusIOException, match="Transient error"):
        raise_for_error_response(MagicMock(), r, register_type="holding_registers", start_address=5)


def test_raise_includes_register_type_in_message():
    r = _response(is_error=True, exception_code=2)
    with pytest.raises(_PermanentModbusError, match="holding_registers"):
        raise_for_error_response(MagicMock(), r, register_type="holding_registers", start_address=0)


# ---------------------------------------------------------------------------
# execute_read_call
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_execute_read_call_awaits_coroutine_result():
    resp = MagicMock()
    dc = SimpleNamespace(slave_id=1, _call_modbus=AsyncMock())
    read_method = AsyncMock(return_value=resp)

    result = await execute_read_call(dc, read_method, 0, 10, 1)

    assert result is resp
    read_method.assert_called_once_with(1, 0, count=10, attempt=1)


@pytest.mark.asyncio
async def test_execute_read_call_fallback_to_call_modbus_when_none():
    fallback = MagicMock()
    dc = SimpleNamespace(slave_id=2, _call_modbus=AsyncMock(return_value=fallback))

    def read_method(slave_id, addr, *, count, attempt):
        return None

    result = await execute_read_call(dc, read_method, 5, 3, 0)

    assert result is fallback
    dc._call_modbus.assert_called_once()


@pytest.mark.asyncio
async def test_execute_read_call_passes_correct_args():
    dc = SimpleNamespace(slave_id=7, _call_modbus=AsyncMock())
    call_args = {}

    async def read_method(slave_id, addr, *, count, attempt):
        call_args.update(slave_id=slave_id, addr=addr, count=count, attempt=attempt)
        return MagicMock()

    await execute_read_call(dc, read_method, 100, 25, 2)

    assert call_args == {"slave_id": 7, "addr": 100, "count": 25, "attempt": 2}
