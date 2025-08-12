import pytest

from custom_components.thessla_green_modbus.modbus_helpers import _call_modbus


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
