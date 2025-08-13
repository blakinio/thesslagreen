"""Tests for the Modbus helper utilities."""

import pytest

from custom_components.thessla_green_modbus.modbus_helpers import _call_modbus

pytestmark = pytest.mark.asyncio


async def test_call_modbus_supports_unit_keyword():
    """Functions expecting ``unit`` should be handled."""

    async def func(address, *, count, unit=None):
        return address, count, unit

    result = await _call_modbus(func, 1, 10, 2)
    assert result == (10, 2, 1)  # nosec B101


async def test_call_modbus_supports_slave_keyword():
    """Functions expecting ``slave`` should be handled."""

    async def func(address, *, count, slave=None):
        return address, count, slave

    result = await _call_modbus(func, 1, 20, 3)
    assert result == (20, 3, 1)  # nosec B101


async def test_call_modbus_supports_no_slave_or_unit():
    """Functions expecting neither keyword should be handled."""

    async def func(address, *, count):
        return address, count

    result = await _call_modbus(func, 1, 30, 4)
    assert result == (30, 4)  # nosec B101
