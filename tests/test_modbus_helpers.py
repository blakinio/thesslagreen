codex/refactor-modbus_helpers-to-support-keyword-only
=======
import logging
 main
import pytest

from custom_components.thessla_green_modbus.modbus_helpers import _call_modbus

 codex/refactor-modbus_helpers-to-support-keyword-only

@pytest.mark.asyncio
async def test_call_modbus_keyword_only_count_unit():
    async def func(address, *, count, unit=None):
        return address, count, unit

    result = await _call_modbus(func, 1, 10, 2)
    assert result == (10, 2, 1)


@pytest.mark.asyncio
async def test_call_modbus_keyword_only_count_slave():
    async def func(address, *, count, slave=None):
        return address, count, slave

    result = await _call_modbus(func, 1, 20, 3)
    assert result == (20, 3, 1)
=======
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
 main
