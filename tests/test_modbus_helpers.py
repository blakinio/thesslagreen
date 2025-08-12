import logging
import pytest

from custom_components.thessla_green_modbus.modbus_helpers import _call_modbus

pytestmark = pytest.mark.asyncio


async def func_slave(*args, slave, **kwargs):
    return slave


async def func_unit(*args, unit, **kwargs):
    return unit


async def func_no_kw(*args, **kwargs):
    assert "slave" not in kwargs and "unit" not in kwargs
    return kwargs.get("value")


async def test_call_modbus_slave(caplog):
    caplog.set_level(logging.DEBUG)
    result = await _call_modbus(func_slave, 7)
    assert result == 7
    assert "with slave keyword" in caplog.text


async def test_call_modbus_unit(caplog):
    caplog.set_level(logging.DEBUG)
    result = await _call_modbus(func_unit, 9)
    assert result == 9
    assert "with unit keyword" in caplog.text


async def test_call_modbus_no_keyword(caplog):
    caplog.set_level(logging.DEBUG)
    result = await _call_modbus(func_no_kw, 5, value=21)
    assert result == 21
    assert "without address keyword" in caplog.text
